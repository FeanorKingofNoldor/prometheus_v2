"""Integration test for a sleeve backtest using the full engine pipeline.

This test exercises a sleeve-level backtest that wires together:

* STAB (StabilityEngine + BasicPriceStabilityModel)
* AssessmentEngine + BasicAssessmentModel
* UniverseEngine + BasicUniverseModel (with Assessment integration)
* PortfolioEngine + BasicLongOnlyPortfolioModel
* BacktestBroker + MarketSimulator + TimeMachine
* BacktestRunner + BasicSleevePipeline

It validates that the backtest:

* Produces instrument scores and universe membership decisions.
* Builds target portfolios and converts them into positions.
* Writes results into the backtesting tables ``backtest_runs``,
  ``backtest_trades``, and ``backtest_daily_equity``.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List, Tuple

import pytest

from prometheus.core.config import get_config
from prometheus.core.database import DatabaseManager, get_db_manager
from prometheus.core.ids import generate_uuid
from prometheus.core.time import TradingCalendar, US_EQ
from prometheus.data.types import PriceBar
from prometheus.data.writer import DataWriter
from prometheus.data.reader import DataReader
from prometheus.execution.time_machine import TimeMachine
from prometheus.execution.market_simulator import FillConfig, MarketSimulator
from prometheus.execution.backtest_broker import BacktestBroker
from prometheus.backtest import BacktestRunner, EquityCurveAnalyzer, SleeveConfig
from prometheus.backtest.sleeve_pipeline import build_basic_sleeve_target_fn


def _ensure_market(db_manager: DatabaseManager, market_id: str = "US_EQ") -> None:
    """Ensure a market row exists for the given market_id."""

    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO markets (market_id, name, region, timezone)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (market_id) DO NOTHING
                """,
                (market_id, "US Equities", "US", "America/New_York"),
            )
            conn.commit()
        finally:
            cursor.close()


def _insert_issuer_and_instrument(
    db_manager: DatabaseManager,
    symbol: str,
    name: str,
) -> Tuple[str, str]:
    issuer_id = f"SLV_PIPE_ISS_{generate_uuid()[:8]}"
    instrument_id = f"SLV_PIPE_INST_{generate_uuid()[:8]}"
    market_id = "US_EQ"

    _ensure_market(db_manager, market_id)

    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO issuers (issuer_id, issuer_type, name)
                VALUES (%s, %s, %s)
                """,
                (issuer_id, "COMPANY", name),
            )
            cursor.execute(
                """
                INSERT INTO instruments (
                    instrument_id,
                    issuer_id,
                    market_id,
                    asset_class,
                    symbol,
                    currency
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (instrument_id, issuer_id, market_id, "EQUITY", symbol, "USD"),
            )
            conn.commit()
        finally:
            cursor.close()

    return issuer_id, instrument_id


def _insert_price_history(
    db_manager: DatabaseManager,
    instrument_id: str,
    pattern: str,
) -> List[date]:
    """Insert synthetic price history with a given pattern.

    pattern:
        - "strong_up": strong uptrend.
        - "mild_up": gentler uptrend.
    """

    calendar = TradingCalendar()
    start = date(2024, 1, 1)
    trading_days = calendar.trading_days_between(start, start + timedelta(days=120))
    trading_days = trading_days[:70]

    writer = DataWriter(db_manager=db_manager)
    price = 100.0
    bars: List[PriceBar] = []
    for d in trading_days:
        if pattern == "strong_up":
            price *= 1.01
        elif pattern == "mild_up":
            price *= 1.003
        close = price
        bars.append(
            PriceBar(
                instrument_id=instrument_id,
                trade_date=d,
                open=close,
                high=close * 1.01,
                low=close * 0.99,
                close=close,
                adjusted_close=close,
                volume=600_000.0,
                currency="USD",
                metadata={"source": "iter_sleeve_pipeline"},
            )
        )

    writer.write_prices(bars)
    return trading_days


def _cleanup(
    db_manager: DatabaseManager,
    issuer_ids: List[str],
    instrument_ids: List[str],
    run_ids: List[str],
) -> None:
    """Remove test artefacts from runtime and historical databases."""

    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            # Backtest tables
            cursor.execute(
                "DELETE FROM backtest_daily_equity WHERE run_id = ANY(%s)",
                (run_ids,),
            )
            cursor.execute(
                "DELETE FROM backtest_trades WHERE run_id = ANY(%s)",
                (run_ids,),
            )
            cursor.execute(
                "DELETE FROM backtest_runs WHERE run_id = ANY(%s)",
                (run_ids,),
            )

            # Portfolio & universe tables
            cursor.execute(
                "DELETE FROM target_portfolios WHERE portfolio_id = %s",
                ("SLV_PIPE_PORTFOLIO",),
            )
            cursor.execute(
                "DELETE FROM book_targets WHERE book_id = %s",
                ("SLV_PIPE_PORTFOLIO",),
            )
            cursor.execute(
                "DELETE FROM universe_members WHERE universe_id = %s",
                ("SLV_PIPE_UNIVERSE",),
            )

            # Assessment & STAB tables
            cursor.execute(
                "DELETE FROM instrument_scores WHERE instrument_id = ANY(%s)",
                (instrument_ids,),
            )
            cursor.execute(
                "DELETE FROM soft_target_classes WHERE entity_type = 'INSTRUMENT' AND entity_id = ANY(%s)",
                (instrument_ids,),
            )
            cursor.execute(
                "DELETE FROM stability_vectors WHERE entity_type = 'INSTRUMENT' AND entity_id = ANY(%s)",
                (instrument_ids,),
            )

            # Instruments / issuers
            cursor.execute("DELETE FROM instruments WHERE instrument_id = ANY(%s)", (instrument_ids,))
            cursor.execute("DELETE FROM issuers WHERE issuer_id = ANY(%s)", (issuer_ids,))

            conn.commit()
        finally:
            cursor.close()

    with db_manager.get_historical_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM prices_daily WHERE instrument_id = ANY(%s)", (instrument_ids,))
            conn.commit()
        finally:
            cursor.close()


@pytest.mark.integration
class TestSleeveBacktestWithPipeline:
    """Integration tests for sleeve backtesting with the full engine stack."""

    def test_sleeve_backtest_with_engines(self) -> None:
        config = get_config()
        db_manager = DatabaseManager(config)

        run_id = ""

        # ------------------------------------------------------------------
        # 1) Insert instruments and price histories.
        # ------------------------------------------------------------------

        issuer_high, inst_high = _insert_issuer_and_instrument(
            db_manager, "HGH", "High Sleeve Corp"
        )
        issuer_low, inst_low = _insert_issuer_and_instrument(
            db_manager, "LOW", "Low Sleeve Corp"
        )

        issuer_ids = [issuer_high, issuer_low]
        instrument_ids = [inst_high, inst_low]

        try:
            days_high = _insert_price_history(db_manager, inst_high, pattern="strong_up")
            days_low = _insert_price_history(db_manager, inst_low, pattern="mild_up")

            as_of_start = min(days_high[-5], days_low[-5])
            as_of_end = min(days_high[-1], days_low[-1])

            calendar = TradingCalendar()
            reader = DataReader(db_manager=db_manager)

            # ------------------------------------------------------------------
            # 2) Backtest environment (TimeMachine + Broker).
            # ------------------------------------------------------------------

            time_machine = TimeMachine(
                start_date=as_of_start,
                end_date=as_of_end,
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

            # ------------------------------------------------------------------
            # 3) Sleeve configuration and target function from pipeline.
            # ------------------------------------------------------------------

            sleeve_config = SleeveConfig(
                sleeve_id="SLV_PIPE_SLEEVE",
                strategy_id="SLV_PIPE_STRAT",
                market_id=US_EQ,
                universe_id="SLV_PIPE_UNIVERSE",
                portfolio_id="SLV_PIPE_PORTFOLIO",
                assessment_strategy_id="SLV_PIPE_ASSESS",
                assessment_horizon_days=21,
            )

            target_fn = build_basic_sleeve_target_fn(
                db_manager=db_manager,
                calendar=calendar,
                config=sleeve_config,
                broker=broker,
            )

            analyzer = EquityCurveAnalyzer(trading_days_per_year=252)
            runner = BacktestRunner(
                db_manager=db_manager,
                broker=broker,
                equity_analyzer=analyzer,
                target_positions_fn=target_fn,
            )

            run_id = runner.run_sleeve(sleeve_config, as_of_start, as_of_end)

            # ------------------------------------------------------------------
            # 4) Validate DB side-effects.
            # ------------------------------------------------------------------

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

                    # Universe members created for the sleeve universe.
                    cursor.execute(
                        """
                        SELECT entity_id, included, score
                        FROM universe_members
                        WHERE universe_id = %s AND as_of_date = %s
                        """,
                        (sleeve_config.universe_id, as_of_end),
                    )
                    univ_rows = cursor.fetchall()
                    assert {r[0] for r in univ_rows} >= {inst_high, inst_low}

                    # Target portfolios exist for the sleeve portfolio.
                    cursor.execute(
                        """
                        SELECT count(*)
                        FROM target_portfolios
                        WHERE portfolio_id = %s
                        """,
                        (sleeve_config.portfolio_id,),
                    )
                    (n_portfolios,) = cursor.fetchone()
                    assert n_portfolios >= 1

                    # backtest_daily_equity has entries for the run.
                    cursor.execute(
                        """
                        SELECT date, equity_curve_value
                        FROM backtest_daily_equity
                        WHERE run_id = %s
                        ORDER BY date
                        """,
                        (run_id,),
                    )
                    equity_rows = cursor.fetchall()
                    assert len(equity_rows) > 0
                    for _d, eq_val in equity_rows:
                        assert eq_val > 0.0

                    # backtest_trades contains trades for both instruments.
                    cursor.execute(
                        """
                        SELECT ticker
                        FROM backtest_trades
                        WHERE run_id = %s
                        """,
                        (run_id,),
                    )
                    tickers = {row[0] for row in cursor.fetchall()}
                    assert inst_high in tickers
                    assert inst_low in tickers

                    # Risk Management Service should have logged actions for
                    # this sleeve strategy whenever target weights were
                    # evaluated. We only check that at least one row exists
                    # for the sleeve's strategy_id.
                    cursor.execute(
                        """
                        SELECT count(*)
                        FROM risk_actions
                        WHERE strategy_id = %s
                        """,
                        (sleeve_config.strategy_id,),
                    )
                    (n_risk_actions,) = cursor.fetchone()
                    assert n_risk_actions >= 1
                finally:
                    cursor.close()

            # Ensure that final positions exist for both instruments and
            # are non-zero. The relative sizing depends on the interaction
            # between STAB and Assessment and is validated in dedicated
            # engine-specific tests.
            positions: Dict[str, object] = broker.get_positions()
            assert inst_high in positions and inst_low in positions
            qty_high = positions[inst_high].quantity  # type: ignore[assignment]
            qty_low = positions[inst_low].quantity  # type: ignore[assignment]
            assert qty_high != 0.0
            assert qty_low != 0.0

        finally:
            # Remove any risk_actions rows written for this test sleeve
            # strategy to keep the runtime DB clean for subsequent tests.
            with db_manager.get_runtime_connection() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(
                        "DELETE FROM risk_actions WHERE strategy_id = %s",
                        (sleeve_config.strategy_id,),
                    )
                    conn.commit()
                finally:
                    cursor.close()

            _cleanup(db_manager, issuer_ids, instrument_ids, run_ids=[run_id])

    def test_sleeve_backtest_with_engines_risk_disabled_does_not_log_actions(self) -> None:
        """Backtest with apply_risk=False should not write risk_actions.

        This test mirrors the basic sleeve backtest but constructs the
        target function with ``apply_risk=False`` and verifies that no
        rows are written to the ``risk_actions`` table for the sleeve's
        strategy_id while still producing valid backtest outputs.
        """

        config = get_config()
        db_manager = DatabaseManager(config)

        run_id = ""

        issuer_high, inst_high = _insert_issuer_and_instrument(
            db_manager, "HGH2", "High Sleeve Corp Risk-Off"
        )
        issuer_low, inst_low = _insert_issuer_and_instrument(
            db_manager, "LOW2", "Low Sleeve Corp Risk-Off"
        )

        issuer_ids = [issuer_high, issuer_low]
        instrument_ids = [inst_high, inst_low]

        # Use a distinct strategy_id so we can assert cleanly on
        # risk_actions for this test.
        sleeve_strategy_id = "SLV_PIPE_STRAT_RISK_OFF"

        try:
            days_high = _insert_price_history(db_manager, inst_high, pattern="strong_up")
            days_low = _insert_price_history(db_manager, inst_low, pattern="mild_up")

            as_of_start = min(days_high[-5], days_low[-5])
            as_of_end = min(days_high[-1], days_low[-1])

            calendar = TradingCalendar()
            reader = DataReader(db_manager=db_manager)

            time_machine = TimeMachine(
                start_date=as_of_start,
                end_date=as_of_end,
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

            sleeve_config = SleeveConfig(
                sleeve_id="SLV_PIPE_SLEEVE_RISK_OFF",
                strategy_id=sleeve_strategy_id,
                market_id=US_EQ,
                universe_id="SLV_PIPE_UNIVERSE_RISK_OFF",
                portfolio_id="SLV_PIPE_PORTFOLIO_RISK_OFF",
                assessment_strategy_id="SLV_PIPE_ASSESS_RISK_OFF",
                assessment_horizon_days=21,
            )

            target_fn = build_basic_sleeve_target_fn(
                db_manager=db_manager,
                calendar=calendar,
                config=sleeve_config,
                broker=broker,
                apply_risk=False,
            )

            analyzer = EquityCurveAnalyzer(trading_days_per_year=252)
            runner = BacktestRunner(
                db_manager=db_manager,
                broker=broker,
                equity_analyzer=analyzer,
                target_positions_fn=target_fn,
            )

            run_id = runner.run_sleeve(sleeve_config, as_of_start, as_of_end)

            # Basic sanity: backtest_daily_equity has rows and equity>0.
            with db_manager.get_runtime_connection() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(
                        """
                        SELECT date, equity_curve_value
                        FROM backtest_daily_equity
                        WHERE run_id = %s
                        ORDER BY date
                        """,
                        (run_id,),
                    )
                    rows = cursor.fetchall()
                    assert len(rows) > 0
                    for _d, eq_val in rows:
                        assert eq_val > 0.0

                    # Risk Management Service should not have written any
                    # risk_actions for this test strategy_id when
                    # apply_risk=False.
                    cursor.execute(
                        """
                        SELECT count(*)
                        FROM risk_actions
                        WHERE strategy_id = %s
                        """,
                        (sleeve_strategy_id,),
                    )
                    (n_risk_actions,) = cursor.fetchone()
                    assert n_risk_actions == 0
                finally:
                    cursor.close()

        finally:
            # Defensive cleanup in case anything was written for this
            # strategy_id despite apply_risk=False.
            with db_manager.get_runtime_connection() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(
                        "DELETE FROM risk_actions WHERE strategy_id = %s",
                        (sleeve_strategy_id,),
                    )
                    conn.commit()
                finally:
                    cursor.close()

            _cleanup(db_manager, issuer_ids, instrument_ids, run_ids=[run_id])
