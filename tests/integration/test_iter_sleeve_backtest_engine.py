"""Integration test for the sleeve-level BacktestRunner.

This test exercises the execution/backtesting stack end-to-end for a
simple sleeve that maintains constant share holdings in two synthetic
instruments. It validates that:

* :class:`BacktestBroker` and :class:`MarketSimulator` generate fills
  based on ``prices_daily``.
* :class:`BacktestRunner` writes rows into ``backtest_runs``,
  ``backtest_trades``, and ``backtest_daily_equity``.
* Basic metrics such as cumulative return are populated in
  ``backtest_runs.metrics_json``.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List

import pytest

from prometheus.core.database import get_db_manager
from prometheus.core.ids import generate_uuid
from prometheus.core.time import TradingCalendar, US_EQ
from prometheus.data.types import PriceBar
from prometheus.data.writer import DataWriter
from prometheus.data.reader import DataReader
from prometheus.execution.time_machine import TimeMachine
from prometheus.execution.market_simulator import FillConfig, MarketSimulator
from prometheus.execution.backtest_broker import BacktestBroker
from prometheus.backtest import (
    BacktestRunner,
    EquityCurveAnalyzer,
    SleeveConfig,
)


@pytest.mark.integration
class TestSleeveBacktestEngine:
    def test_sleeve_backtest_produces_equity_curve_and_trades(self) -> None:
        db_manager = get_db_manager()

        # ------------------------------------------------------------------
        # 1) Insert synthetic price history for two instruments.
        # ------------------------------------------------------------------

        writer = DataWriter(db_manager=db_manager)
        calendar = TradingCalendar()

        start_prices_date = date(2024, 1, 1)
        trading_days = calendar.trading_days_between(
            start_prices_date,
            start_prices_date + timedelta(days=60),
        )
        # Use 40 trading days of history.
        trading_days = trading_days[:40]

        inst_a = f"BTST_A_{generate_uuid()[:8]}"
        inst_b = f"BTST_B_{generate_uuid()[:8]}"

        bars: List[PriceBar] = []

        price_a = 100.0
        price_b = 100.0
        for d in trading_days:
            # Instrument A: gentle uptrend.
            price_a *= 1.002
            # Instrument B: gentle downtrend.
            price_b *= 0.999

            bars.append(
                PriceBar(
                    instrument_id=inst_a,
                    trade_date=d,
                    open=price_a,
                    high=price_a * 1.01,
                    low=price_a * 0.99,
                    close=price_a,
                    adjusted_close=price_a,
                    volume=500_000.0,
                    currency="USD",
                    metadata={"source": "iter_sleeve_backtest"},
                )
            )
            bars.append(
                PriceBar(
                    instrument_id=inst_b,
                    trade_date=d,
                    open=price_b,
                    high=price_b * 1.01,
                    low=price_b * 0.99,
                    close=price_b,
                    adjusted_close=price_b,
                    volume=500_000.0,
                    currency="USD",
                    metadata={"source": "iter_sleeve_backtest"},
                )
            )

        writer.write_prices(bars)

        # Backtest over the last 10 trading days of the history.
        start_bt = trading_days[-10]
        end_bt = trading_days[-1]

        # ------------------------------------------------------------------
        # 2) Backtest environment: TimeMachine, MarketSimulator, Broker.
        # ------------------------------------------------------------------

        reader = DataReader(db_manager=db_manager)
        time_machine = TimeMachine(
            start_date=start_bt,
            end_date=end_bt,
            market=US_EQ,
            data_reader=reader,
            calendar=calendar,
            strict_mode=True,
        )

        initial_cash = 1_000_000.0
        simulator = MarketSimulator(
            time_machine=time_machine,
            initial_cash=initial_cash,
            fill_config=FillConfig(market_slippage_bps=0.0),
        )
        broker = BacktestBroker(time_machine=time_machine, simulator=simulator)

        # Compute constant target share holdings for both instruments based
        # on the first backtest day's close prices.
        df_start = reader.read_prices([inst_a, inst_b], start_bt, start_bt)
        price_map = {str(row["instrument_id"]): float(row["close"]) for _, row in df_start.iterrows()}
        assert inst_a in price_map and inst_b in price_map

        # Allocate capital equally between the two instruments.
        target_positions: Dict[str, float] = {}
        per_instrument_capital = initial_cash / 2.0
        for inst in (inst_a, inst_b):
            px = price_map[inst]
            target_positions[inst] = per_instrument_capital / px

        def target_fn(as_of_date: date) -> Dict[str, float]:  # noqa: D401 - tiny helper
            """Return constant target share holdings for all dates."""

            return dict(target_positions)

        # ------------------------------------------------------------------
        # 3) Run BacktestRunner.
        # ------------------------------------------------------------------

        sleeve_config = SleeveConfig(
            sleeve_id="TEST_SLEEVE",
            strategy_id="TEST_STRAT",
            market_id=US_EQ,
            universe_id="TEST_UNIVERSE",
            portfolio_id="TEST_PORTFOLIO",
            assessment_strategy_id="TEST_ASSESS",
            assessment_horizon_days=21,
        )

        analyzer = EquityCurveAnalyzer(trading_days_per_year=252)
        runner = BacktestRunner(
            db_manager=db_manager,
            broker=broker,
            equity_analyzer=analyzer,
            target_positions_fn=target_fn,
        )

        run_id = runner.run_sleeve(sleeve_config, start_bt, end_bt)

        # ------------------------------------------------------------------
        # 4) Validate DB side-effects and then clean up.
        # ------------------------------------------------------------------

        try:
            with db_manager.get_runtime_connection() as conn:
                cursor = conn.cursor()
                try:
                    # backtest_runs row exists with metrics.
                    cursor.execute(
                        """
                        SELECT strategy_id, universe_id, metrics_json
                        FROM backtest_runs
                        WHERE run_id = %s
                        """,
                        (run_id,),
                    )
                    row = cursor.fetchone()
                    assert row is not None
                    strategy_id_db, universe_id_db, metrics_json_db = row
                    assert strategy_id_db == sleeve_config.strategy_id
                    assert universe_id_db == sleeve_config.universe_id
                    assert isinstance(metrics_json_db, dict)
                    assert "cumulative_return" in metrics_json_db

                    # backtest_daily_equity has one row per trading day.
                    cursor.execute(
                        """
                        SELECT date, equity_curve_value, drawdown
                        FROM backtest_daily_equity
                        WHERE run_id = %s
                        ORDER BY date
                        """,
                        (run_id,),
                    )
                    equity_rows = cursor.fetchall()
                    assert len(equity_rows) == len(
                        [d for d in trading_days if start_bt <= d <= end_bt]
                    )
                    # Equity values should all be positive.
                    for _, eq_value, _ in equity_rows:
                        assert eq_value > 0.0

                    # backtest_trades should contain at least one trade for
                    # each instrument on the first backtest day.
                    cursor.execute(
                        """
                        SELECT ticker, direction, size, price
                        FROM backtest_trades
                        WHERE run_id = %s
                        ORDER BY trade_date, ticker
                        """,
                        (run_id,),
                    )
                    trade_rows = cursor.fetchall()
                    tickers = {row[0] for row in trade_rows}
                    assert inst_a in tickers
                    assert inst_b in tickers

                    # Execution core: orders, fills, and positions_snapshots
                    # should also be populated in BACKTEST mode for this
                    # portfolio.
                    cursor.execute(
                        """
                        SELECT COUNT(*), MIN(mode)
                        FROM orders
                        WHERE portfolio_id = %s
                          AND mode = 'BACKTEST'
                        """,
                        (sleeve_config.portfolio_id,),
                    )
                    orders_count, orders_mode = cursor.fetchone()
                    assert orders_count > 0
                    assert orders_mode == "BACKTEST"

                    cursor.execute(
                        """
                        SELECT COUNT(*), MIN(mode)
                        FROM fills
                        WHERE mode = 'BACKTEST'
                        """,
                    )
                    fills_count, fills_mode = cursor.fetchone()
                    assert fills_count > 0
                    assert fills_mode == "BACKTEST"

                    cursor.execute(
                        """
                        SELECT COUNT(*), MIN(mode)
                        FROM positions_snapshots
                        WHERE portfolio_id = %s
                          AND as_of_date BETWEEN %s AND %s
                          AND mode = 'BACKTEST'
                        """,
                        (sleeve_config.portfolio_id, start_bt, end_bt),
                    )
                    snaps_count, snaps_mode = cursor.fetchone()
                    assert snaps_count > 0
                    assert snaps_mode == "BACKTEST"

                    # executed_actions should also contain mirrored trades
                    # for this backtest run.
                    cursor.execute(
                        """
                        SELECT COUNT(*)
                        FROM executed_actions
                        WHERE run_id = %s
                        """,
                        (run_id,),
                    )
                    (actions_count,) = cursor.fetchone()
                    assert actions_count > 0
                finally:
                    cursor.close()
        finally:
            # Clean up test artefacts from both runtime and historical DBs.
            with db_manager.get_runtime_connection() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(
                        "DELETE FROM backtest_daily_equity WHERE run_id = %s",
                        (run_id,),
                    )
                    cursor.execute(
                        "DELETE FROM backtest_trades WHERE run_id = %s",
                        (run_id,),
                    )
                    cursor.execute(
                        "DELETE FROM backtest_runs WHERE run_id = %s",
                        (run_id,),
                    )
                    # Execution tables: remove any rows written for this
                    # test portfolio in BACKTEST mode.
                    cursor.execute(
                        "DELETE FROM orders WHERE portfolio_id = %s AND mode = 'BACKTEST'",
                        (sleeve_config.portfolio_id,),
                    )
                    cursor.execute(
                        "DELETE FROM fills WHERE mode = 'BACKTEST'",
                    )
                    cursor.execute(
                        "DELETE FROM positions_snapshots WHERE portfolio_id = %s AND mode = 'BACKTEST'",
                        (sleeve_config.portfolio_id,),
                    )
                    cursor.execute(
                        "DELETE FROM executed_actions WHERE run_id = %s",
                        (run_id,),
                    )
                    conn.commit()
                finally:
                    cursor.close()

            with db_manager.get_historical_connection() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(
                        "DELETE FROM prices_daily WHERE instrument_id = ANY(%s)",
                        ([inst_a, inst_b],),
                    )
                    conn.commit()
                finally:
                    cursor.close()