"""Prometheus v2 – Sleeve-level backtest runner.

This module provides :class:`BacktestRunner`, a small orchestration
helper that simulates a sleeve/book over a historical period using the
execution layer's :class:`~prometheus.execution.backtest_broker.BacktestBroker`.

The runner is intentionally narrow in scope for the first iteration:

* It operates at end-of-day frequency using :class:`TimeMachine`.
* Target positions are supplied via a user-provided callback function;
  higher-level orchestration that wires Assessment/Universe/Portfolio
  engines can be layered on top.
* It records results into the ``backtest_runs``, ``backtest_trades``, and
  ``backtest_daily_equity`` tables defined by migration 0003.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable, Dict, List, Sequence

from psycopg2.extras import Json

from prometheus.core.database import DatabaseManager
from prometheus.core.ids import generate_uuid
from prometheus.core.logging import get_logger
from prometheus.backtest.analyzers import EquityCurveAnalyzer, EquityCurvePoint
from prometheus.backtest.config import SleeveConfig
from prometheus.execution.backtest_broker import BacktestBroker
from prometheus.execution.broker_interface import Fill, Position
from prometheus.execution.api import apply_execution_plan
from prometheus.execution.executed_actions import (
    ExecutedActionContext,
    record_executed_actions_for_fills,
)
from prometheus.meta.storage import MetaStorage
from prometheus.meta.types import DecisionOutcome, EngineDecision


logger = get_logger(__name__)


TargetPositionsFn = Callable[[date], Dict[str, float]]


@dataclass
class BacktestRunner:
    """Run a simple sleeve-level backtest over a date range.

    The runner is parameterised by a :class:`BacktestBroker`, an equity
    curve analyzer, and a callback that produces per-date target
    positions. It is agnostic to how those targets are computed (they may
    come from Assessment/Universe/Portfolio engines or any other logic).
    """

    db_manager: DatabaseManager
    broker: BacktestBroker
    equity_analyzer: EquityCurveAnalyzer
    target_positions_fn: TargetPositionsFn
    # Optional callback producing per-date exposure metrics (e.g. lambda
    # and state-aware diagnostics) to be stored alongside daily equity in
    # ``backtest_daily_equity.exposure_metrics_json``. When omitted or if
    # the callback fails, an empty dict is stored.
    exposure_metrics_fn: Callable[[date], Dict[str, float]] | None = None

    def run_sleeve(self, config: SleeveConfig, start_date: date, end_date: date) -> str:
        """Run a backtest for ``config`` between ``start_date`` and ``end_date``.

        Returns the generated ``run_id`` from ``backtest_runs``.
        """

        if end_date < start_date:
            raise ValueError("end_date must be >= start_date")

        run_id = generate_uuid()
        # Single meta-level decision identifier for this sleeve backtest
        # run. This id is propagated to orders (via apply_execution_plan),
        # executed_actions, and engine_decisions/decision_outcomes so the
        # Meta-Orchestrator can join everything together cheaply.
        decision_id = generate_uuid()

        self._insert_backtest_run_stub(run_id, config, start_date, end_date)

        time_machine = self.broker.time_machine
        equity_curve: List[EquityCurvePoint] = []
        exposure_by_date: Dict[date, Dict[str, float]] = {}
        peak_equity: float | None = None
        last_fill_ts: datetime | None = None

        # Coarse progress tracking over the requested backtest window using
        # calendar days. This provides an approximate sense of completion
        # without requiring a separate pass over trading days.
        total_days = max((end_date - start_date).days + 1, 1)
        last_reported_pct = -1

        for as_of in time_machine.iter_trading_days():
            if as_of < start_date or as_of > end_date:
                continue

            # Log progress every 5% of the calendar window.
            elapsed_days = (as_of - start_date).days + 1
            pct = int(elapsed_days * 100 / total_days)
            if pct != last_reported_pct and pct % 5 == 0:
                logger.info(
                    "BacktestRunner.run_sleeve progress: sleeve=%s strategy=%s as_of=%s %d%%",
                    config.sleeve_id,
                    config.strategy_id,
                    as_of,
                    pct,
                )
                last_reported_pct = pct

            # Advance the TimeMachine and synchronise broker state.
            time_machine.set_date(as_of)

            target_positions = self.target_positions_fn(as_of)

            # Apply execution plan via the unified execution API. This
            # function is responsible for computing orders from current
            # vs target positions, submitting them via the broker, and in
            # BACKTEST mode generating fills via BacktestBroker +
            # MarketSimulator. It also persists orders, fills, and (optionally)
            # a positions snapshot into the runtime DB.
            apply_execution_plan(
                db_manager=self.db_manager,
                broker=self.broker,
                portfolio_id=config.portfolio_id,
                target_positions=target_positions,
                mode="BACKTEST",
                as_of_date=as_of,
                decision_id=decision_id,
                record_positions=True,
            )

            # After execution, inspect updated account state.
            account_state = self.broker.get_account_state()
            equity = float(account_state.get("equity", 0.0))

            if peak_equity is None or equity > peak_equity:
                peak_equity = equity
            drawdown = 0.0
            if peak_equity and peak_equity > 0.0:
                drawdown = equity / peak_equity - 1.0

            # Optional per-date exposure metrics (e.g. lambda/state-aware
            # diagnostics) that we want to persist alongside the equity
            # curve. Failures here should never abort the backtest.
            exposure_metrics: Dict[str, float] = {}
            if self.exposure_metrics_fn is not None:
                try:
                    raw = self.exposure_metrics_fn(as_of) or {}
                    exposure_metrics = {str(k): float(v) for k, v in raw.items()}
                except Exception:  # pragma: no cover - defensive
                    logger.exception(
                        "BacktestRunner.run_sleeve: exposure_metrics_fn failed for %s; using empty metrics",
                        as_of,
                    )
                    exposure_metrics = {}

            exposure_by_date[as_of] = exposure_metrics

            equity_curve.append(EquityCurvePoint(date=as_of, equity=equity))
            self._insert_daily_equity(run_id, as_of, equity, drawdown, exposure_metrics)

            # Record trades for any new fills since the previous step.
            fills = self.broker.get_fills(since=last_fill_ts)
            if fills:
                last_fill_ts = max(f.timestamp for f in fills)
                self._insert_trades_for_fills(run_id, fills, config)

                # Also mirror fills into executed_actions so that the
                # Meta-Orchestrator and monitoring layers can analyse
                # realised trades in a unified schema across modes.
                record_executed_actions_for_fills(
                    db_manager=self.db_manager,
                    fills=fills,
                    context=ExecutedActionContext(
                        run_id=run_id,
                        portfolio_id=config.portfolio_id,
                        decision_id=decision_id,
                        mode="BACKTEST",
                    ),
                )

        metrics = self.equity_analyzer.compute_metrics(equity_curve)

        # Optionally augment metrics with run-level summaries derived from
        # per-date exposure diagnostics (lambda and state-aware context).
        if exposure_by_date:
            exposure_summary = self._compute_exposure_aggregates(
                equity_curve=equity_curve,
                exposure_by_date=exposure_by_date,
            )
            if exposure_summary:
                metrics.update(exposure_summary)

        self._update_backtest_run_metrics(run_id, metrics)

        # Record a Meta-Orchestrator friendly decision and outcome for this
        # backtest run so that it becomes visible in engine_decisions and
        # decision_outcomes.
        self._record_meta_decision_and_outcome(
            run_id=run_id,
            decision_id=decision_id,
            config=config,
            start_date=start_date,
            end_date=end_date,
            metrics=metrics,
        )

        logger.info(
            "BacktestRunner.run_sleeve: run_id=%s sleeve=%s strategy=%s start=%s end=%s cumulative_return=%.4f",
            run_id,
            config.sleeve_id,
            config.strategy_id,
            start_date,
            end_date,
            float(metrics.get("cumulative_return", 0.0)),
        )

        return run_id

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _insert_backtest_run_stub(
        self,
        run_id: str,
        config: SleeveConfig,
        start_date: date,
        end_date: date,
    ) -> None:
        """Insert an initial row into ``backtest_runs`` with empty metrics."""

        payload = {
            "sleeve_id": config.sleeve_id,
            "strategy_id": config.strategy_id,
            "market_id": config.market_id,
            "universe_id": config.universe_id,
            "portfolio_id": config.portfolio_id,
            "assessment_strategy_id": config.assessment_strategy_id,
            "assessment_horizon_days": config.assessment_horizon_days,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }

        sql = """
            INSERT INTO backtest_runs (
                run_id,
                strategy_id,
                config_json,
                start_date,
                end_date,
                universe_id,
                metrics_json,
                created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, NULL, NOW())
        """

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    sql,
                    (
                        run_id,
                        config.strategy_id,
                        Json(payload),
                        start_date,
                        end_date,
                        config.universe_id,
                    ),
                )
                conn.commit()
            finally:
                cursor.close()

    def _insert_daily_equity(
        self,
        run_id: str,
        as_of_date: date,
        equity: float,
        drawdown: float,
        exposure_metrics: Dict[str, float],
    ) -> None:
        """Insert a row into ``backtest_daily_equity`` for a given date."""

        sql = """
            INSERT INTO backtest_daily_equity (
                run_id,
                date,
                equity_curve_value,
                drawdown,
                exposure_metrics_json
            ) VALUES (%s, %s, %s, %s, %s)
        """

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    sql,
                    (
                        run_id,
                        as_of_date,
                        float(equity),
                        float(drawdown),
                        Json(exposure_metrics or {}),
                    ),
                )
                conn.commit()
            finally:
                cursor.close()

    def _insert_trades_for_fills(
        self,
        run_id: str,
        fills: Sequence[Fill],
        config: SleeveConfig,
    ) -> None:
        """Insert ``backtest_trades`` rows corresponding to fills."""

        if not fills:
            return

        sql = """
            INSERT INTO backtest_trades (
                run_id,
                trade_date,
                ticker,
                direction,
                size,
                price,
                regime_id,
                universe_id,
                profile_version_id,
                decision_metadata_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                for fill in fills:
                    metadata = Json(
                        {
                            "sleeve_id": config.sleeve_id,
                            "strategy_id": config.strategy_id,
                        }
                    )
                    cursor.execute(
                        sql,
                        (
                            run_id,
                            fill.timestamp.date(),
                            fill.instrument_id,
                            fill.side.value,
                            float(fill.quantity),
                            float(fill.price),
                            None,  # regime_id (optional, not wired yet)
                            config.universe_id,
                            None,  # profile_version_id (optional, not wired yet)
                            metadata,
                        ),
                    )
                conn.commit()
            finally:
                cursor.close()

    def _update_backtest_run_metrics(self, run_id: str, metrics: Dict[str, float]) -> None:
        """Update ``backtest_runs.metrics_json`` for ``run_id``."""

        sql = """
            UPDATE backtest_runs
               SET metrics_json = %s
             WHERE run_id = %s
        """

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (Json(metrics), run_id))
                conn.commit()
            finally:
                cursor.close()

    def _compute_exposure_aggregates(
        self,
        *,
        equity_curve: Sequence[EquityCurvePoint],
        exposure_by_date: Dict[date, Dict[str, float]],
    ) -> Dict[str, float]:
        """Compute run-level aggregates from per-date exposure diagnostics.

        The input exposures are the same metrics persisted into
        ``backtest_daily_equity.exposure_metrics_json``. This helper derives
        a small number of summary statistics suitable for Meta-level
        analysis, such as average lambda exposure and performance in
        low/medium/high lambda regimes.
        """

        if not equity_curve or not exposure_by_date:
            return {}

        # Build daily returns keyed by date from the equity curve.
        curve_sorted = sorted(equity_curve, key=lambda p: p.date)
        returns_by_date: Dict[date, float] = {}
        if len(curve_sorted) >= 2:
            prev = curve_sorted[0]
            for point in curve_sorted[1:]:
                prev_eq = float(prev.equity)
                if prev_eq > 0.0:
                    returns_by_date[point.date] = float(point.equity) / prev_eq - 1.0
                prev = point

        metrics: Dict[str, float] = {}

        def _time_mean(key: str) -> float | None:
            vals: List[float] = []
            for exp in exposure_by_date.values():
                val = exp.get(key)
                if isinstance(val, (int, float)):
                    vals.append(float(val))
            if not vals:
                return None
            return float(sum(vals) / len(vals))

        # Simple time-averaged exposures.
        for src_key, dst_key in [
            ("lambda_score_mean", "lambda_score_mean_over_run"),
            ("lambda_score_coverage", "lambda_score_coverage_over_run"),
            ("stab_risk_score_mean", "stab_risk_score_mean_over_run"),
            ("stab_p_worsen_any_mean", "stab_p_worsen_any_mean_over_run"),
            ("regime_risk_score", "regime_risk_score_mean_over_run"),
            ("regime_p_change_any", "regime_p_change_any_mean_over_run"),
        ]:
            mean_val = _time_mean(src_key)
            if mean_val is not None:
                metrics[dst_key] = mean_val

        # Lambda bucketed performance: low / mid / high lambda days.
        lambda_obs: List[tuple[float, float]] = []
        for d, exp in exposure_by_date.items():
            lam = exp.get("lambda_score_mean")
            ret = returns_by_date.get(d)
            if isinstance(lam, (int, float)) and isinstance(ret, (int, float)):
                lambda_obs.append((float(lam), float(ret)))

        if lambda_obs:
            metrics["lambda_bucket_total_num_days"] = float(len(lambda_obs))

        if len(lambda_obs) >= 3:
            lambda_obs.sort(key=lambda x: x[0])
            n = len(lambda_obs)
            third = max(n // 3, 1)

            low = lambda_obs[:third]
            mid = lambda_obs[third : 2 * third]
            high = lambda_obs[2 * third :]

            if not high:
                high = lambda_obs[-third:]

            def _mean_ret(pairs: List[tuple[float, float]]) -> float | None:
                if not pairs:
                    return None
                return float(sum(r for _lam, r in pairs) / len(pairs))

            bucket_info = [
                ("low", low),
                ("mid", mid),
                ("high", high),
            ]
            for name, pairs in bucket_info:
                mean_ret = _mean_ret(pairs)
                if mean_ret is not None:
                    metrics[f"lambda_bucket_{name}_mean_daily_return"] = mean_ret
                metrics[f"lambda_bucket_{name}_num_days"] = float(len(pairs))

            low_mean = metrics.get("lambda_bucket_low_mean_daily_return")
            high_mean = metrics.get("lambda_bucket_high_mean_daily_return")
            if isinstance(low_mean, (int, float)) and isinstance(high_mean, (int, float)):
                metrics["lambda_bucket_high_minus_low_return_diff"] = float(
                    high_mean - low_mean
                )

        return metrics

    def _record_meta_decision_and_outcome(
        self,
        *,
        run_id: str,
        decision_id: str,
        config: SleeveConfig,
        start_date: date,
        end_date: date,
        metrics: Dict[str, float],
    ) -> None:
        """Record engine_decisions and decision_outcomes for a sleeve run.

        This creates a single logical Meta-Orchestrator decision for the
        backtest run and an associated outcome record for the full
        backtest window. It is intentionally minimal and focuses on
        making backtests visible to the Meta layer; more granular
        per-horizon outcomes can be added later.
        """

        # Defensive: if strategy_id is missing we still record a decision
        # with a synthetic engine_name.
        strategy_id = config.strategy_id or "UNKNOWN_STRATEGY"
        market_id = config.market_id

        # Compute an approximate horizon in calendar days; this is
        # sufficient for distinguishing short vs long backtests and can
        # be refined later.
        horizon_days = max((end_date - start_date).days, 1)

        storage = MetaStorage(db_manager=self.db_manager)

        decision = EngineDecision(
            decision_id=decision_id,
            engine_name="BACKTEST_SLEEVE_RUNNER",
            run_id=run_id,
            strategy_id=strategy_id,
            market_id=market_id,
            as_of_date=end_date,
            config_id=config.sleeve_id,
            input_refs={
                "run_id": run_id,
                "sleeve_id": config.sleeve_id,
                "portfolio_id": config.portfolio_id,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            output_refs={
                "metrics": metrics,
            },
            metadata={},
        )
        storage.save_engine_decision(decision)

        outcome = DecisionOutcome(
            decision_id=decision_id,
            horizon_days=horizon_days,
            realized_return=float(metrics.get("cumulative_return", 0.0)),
            realized_pnl=float(metrics.get("final_pnl", 0.0)) if "final_pnl" in metrics else None,
            realized_drawdown=float(metrics.get("max_drawdown", 0.0)),
            realized_vol=float(metrics.get("annualised_vol", 0.0)) if "annualised_vol" in metrics else None,
            metadata={
                "annualised_sharpe": float(metrics.get("annualised_sharpe", 0.0)),
            },
        )
        storage.save_decision_outcome(outcome)
