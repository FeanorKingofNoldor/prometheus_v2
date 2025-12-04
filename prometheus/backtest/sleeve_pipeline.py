"""Prometheus v2 – Basic sleeve pipeline for backtesting.

This module provides a thin orchestration layer that wires together the
STAB, Assessment, Universe, and Portfolio & Risk engines in order to
produce target *positions* (instrument quantities) for a single sleeve.

It is intentionally simple and focused on Iteration 1 backtests:

* Uses the existing BasicPriceStabilityModel, BasicAssessmentModel,
  BasicUniverseModel, and BasicLongOnlyPortfolioModel.
* Operates at end-of-day frequency; intraday behaviour is not modelled.
* Converts portfolio weights into share quantities using the simulated
  account equity from :class:`BacktestBroker` and close prices at the
  current ``as_of_date``.

Higher-level orchestration (multiple sleeves, Meta-Orchestrator, regime-
conditioned budgets) can be layered on top of this building block.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Sequence

from prometheus.core.database import DatabaseManager
from prometheus.core.logging import get_logger
from prometheus.core.time import TradingCalendar
from prometheus.data.reader import DataReader
from prometheus.data.types import PriceBar
from prometheus.stability import (
    StabilityEngine,
    StabilityStorage,
    BasicPriceStabilityModel,
    StabilityStateChangeForecaster,
)
from prometheus.regime import RegimeStorage
from prometheus.regime.state_change import RegimeStateChangeForecaster
from prometheus.assessment import AssessmentEngine
from prometheus.assessment.model_basic import BasicAssessmentModel
from prometheus.assessment.model_context import ContextAssessmentModel
from prometheus.assessment.storage import InstrumentScoreStorage
from prometheus.universe import (
    UniverseEngine,
    UniverseStorage,
    BasicUniverseModel,
)
from prometheus.portfolio import (
    PortfolioConfig,
    PortfolioEngine,
    PortfolioStorage,
    BasicLongOnlyPortfolioModel,
)
from prometheus.risk import apply_risk_constraints
from prometheus.execution.backtest_broker import BacktestBroker
from prometheus.execution.broker_interface import Position
from prometheus.execution.time_machine import TimeMachine
from prometheus.backtest.config import SleeveConfig
from prometheus.backtest.runner import TargetPositionsFn


logger = get_logger(__name__)


@dataclass
class BasicSleevePipeline:
    """Wire STAB, Assessment, Universe, and Portfolio for a single sleeve.

    The pipeline is configured for a particular :class:`SleeveConfig` and a
    backtest environment consisting of a :class:`DatabaseManager`,
    :class:`TradingCalendar`, and :class:`BacktestBroker`. It exposes a
    small method :meth:`target_positions_for_date` suitable for use as the
    ``target_positions_fn`` argument to :class:`BacktestRunner`.

    The ``apply_risk`` flag controls whether the Risk Management Service is
    invoked to post-process portfolio weights before converting them into
    target positions. This allows risk-on vs risk-off backtests using the
    same sleeve pipeline.
    """

    db_manager: DatabaseManager
    calendar: TradingCalendar
    config: SleeveConfig
    broker: BacktestBroker

    # Core shared infrastructure
    data_reader: DataReader
    time_machine: TimeMachine

    # Engines
    stab_engine: StabilityEngine
    assessment_engine: AssessmentEngine
    universe_engine: UniverseEngine
    portfolio_engine: PortfolioEngine

    # Cached instrument universe for the sleeve's markets. This is purely
    # an optimisation; we recompute STAB/Assessment/Universe per date.
    instrument_ids: List[str]

    # Whether to apply the Risk Management Service (per-name caps, etc.)
    # when turning portfolio weights into target positions.
    apply_risk: bool = True

    def target_positions_for_date(self, as_of_date: date) -> Dict[str, float]:
        """Return target share quantities for the sleeve on ``as_of_date``.

        The sequence of operations mirrors the design in
        ``backtesting_and_books_pipeline.md`` for a single sleeve:

        1. Ensure STAB soft-target states exist for all candidate
           instruments.
        2. Run Assessment to score those instruments and persist scores
           into ``instrument_scores``.
        3. Build a universe via :class:`UniverseEngine` and
           :class:`BasicUniverseModel`.
        4. Run :class:`PortfolioEngine` with a long-only model to obtain
           a :class:`TargetPortfolio` of weights.
        5. Convert weights into share quantities using the current
           account equity and close prices at ``as_of_date``.
        """

        if not self.instrument_ids:
            return {}

        # 1) STAB – compute stability / soft-target state for each
        # instrument using only history up to as_of_date.
        for instrument_id in self.instrument_ids:
            try:
                self.stab_engine.score_entity(as_of_date, "INSTRUMENT", instrument_id)
            except ValueError:
                # Instruments with insufficient history are excluded later
                # by the Universe model via a "no_stab_state" reason.
                continue

        # 2) Assessment – score instruments for the sleeve's assessment
        # strategy and horizon. Scores are persisted into
        # ``instrument_scores`` via InstrumentScoreStorage.
        try:
            self.assessment_engine.score_universe(
                strategy_id=self.config.assessment_strategy_id,
                market_id=self.config.market_id,
                instrument_ids=self.instrument_ids,
                as_of_date=as_of_date,
                horizon_days=self.config.assessment_horizon_days,
            )
        except Exception:  # pragma: no cover - defensive
            logger.exception(
                "BasicSleevePipeline: AssessmentEngine.score_universe failed for %s on %s",
                self.config.assessment_strategy_id,
                as_of_date,
            )

        # 3) Universe – build a sleeve-specific universe and persist
        # decisions into ``universe_members``.
        members = self.universe_engine.build_and_save(as_of_date, self.config.universe_id)
        included = [m for m in members if m.included]
        if not included:
            logger.info(
                "BasicSleevePipeline: no included universe members for sleeve=%s on %s",
                self.config.sleeve_id,
                as_of_date,
            )
            return {}

        # 4) Portfolio – construct a long-only target portfolio from the
        # universe and persist into book_targets and target_portfolios
        # tables.
        target = self.portfolio_engine.optimize_and_save(self.config.portfolio_id, as_of_date)
        if not target.weights:
            logger.info(
                "BasicSleevePipeline: empty TargetPortfolio for sleeve=%s on %s",
                self.config.sleeve_id,
                as_of_date,
            )
            return {}

        # Optionally apply basic Risk Management constraints to portfolio
        # weights before converting them into share quantities. When
        # ``apply_risk`` is False we simply use the raw optimizer weights,
        # which is useful for "risk-off" baseline backtests.
        if self.apply_risk:
            decisions = [
                {"instrument_id": inst_id, "target_weight": float(weight)}
                for inst_id, weight in target.weights.items()
            ]
            adjusted_decisions = apply_risk_constraints(
                decisions,
                strategy_id=self.config.strategy_id,
                db_manager=self.db_manager,
            )
            weights_for_positions: Dict[str, float] = {
                str(d["instrument_id"]): float(d.get("target_weight", 0.0))
                for d in adjusted_decisions
            }
        else:
            weights_for_positions = {
                str(inst_id): float(weight) for inst_id, weight in target.weights.items()
            }

        # 5) Convert weights into share quantities based on current equity
        # and close prices for as_of_date. We use the BacktestBroker's
        # account state for equity so that the portfolio naturally scales
        # with P&L.
        account_state = self.broker.get_account_state()
        equity = float(account_state.get("equity", 0.0))
        if equity <= 0.0:
            logger.warning(
                "BasicSleevePipeline: non-positive equity %.4f for sleeve=%s on %s; returning zero targets",
                equity,
                self.config.sleeve_id,
                as_of_date,
            )
            return {}

        instrument_ids = list(weights_for_positions.keys())
        prices_df = self.data_reader.read_prices(instrument_ids, as_of_date, as_of_date)
        if prices_df.empty:
            logger.warning(
                "BasicSleevePipeline: no prices for target instruments on %s; returning zero targets",
                as_of_date,
            )
            return {}

        price_map: Dict[str, float] = {}
        for _, row in prices_df.iterrows():
            price_map[str(row["instrument_id"])] = float(row["close"])

        target_positions: Dict[str, float] = {}
        for instrument_id, weight in weights_for_positions.items():
            px = price_map.get(instrument_id)
            if px is None or px <= 0.0:
                continue
            qty = float(weight) * equity / px
            if qty != 0.0:
                target_positions[instrument_id] = qty

        return target_positions

    def exposure_metrics_for_date(self, as_of_date: date) -> Dict[str, float]:
        """Aggregate lambda/state-aware diagnostics for the sleeve on a date.

        This reads from the already-persisted ``universe_members`` for
        ``(universe_id, as_of_date)`` and computes simple cross-sectional
        averages that can be attached to ``backtest_daily_equity``
        ``exposure_metrics_json``. It is intentionally lightweight and
        purely diagnostic; failures return an empty dict.
        """

        try:
            members = self.universe_engine.get_universe(
                as_of_date,
                self.config.universe_id,
                included_only=True,
            )
        except Exception:  # pragma: no cover - defensive
            logger.exception(
                "BasicSleevePipeline: failed to load universe for exposures sleeve=%s on %s",
                self.config.sleeve_id,
                as_of_date,
            )
            return {}

        if not members:
            return {}

        n = float(len(members))
        metrics: Dict[str, float] = {"universe_size": n}

        def _mean_from_reasons(key: str) -> float | None:
            vals: List[float] = []
            for m in members:
                reasons = getattr(m, "reasons", None) or {}
                val = reasons.get(key)
                if isinstance(val, (int, float)):
                    vals.append(float(val))
            if not vals:
                return None
            return float(sum(vals) / len(vals))

        def _coverage_from_reasons(key: str) -> float | None:
            have = 0
            for m in members:
                reasons = getattr(m, "reasons", None) or {}
                val = reasons.get(key)
                if isinstance(val, (int, float)):
                    have += 1
            if have == 0:
                return None
            return float(have) / n

        # Lambda / opportunity-density exposure for the included universe.
        lambda_mean = _mean_from_reasons("lambda_score")
        if lambda_mean is not None:
            metrics["lambda_score_mean"] = lambda_mean
            cov = _coverage_from_reasons("lambda_score")
            if cov is not None:
                metrics["lambda_score_coverage"] = cov

        # STAB state-change risk exposure.
        stab_risk_mean = _mean_from_reasons("stab_risk_score")
        if stab_risk_mean is not None:
            metrics["stab_risk_score_mean"] = stab_risk_mean

        stab_p_worsen_mean = _mean_from_reasons("stab_p_worsen_any")
        if stab_p_worsen_mean is not None:
            metrics["stab_p_worsen_any_mean"] = stab_p_worsen_mean

        # Regime state-change risk is global rather than per-instrument;
        # query the universe model's forecaster once.
        model = self.universe_engine.model
        regime_forecaster = getattr(model, "regime_forecaster", None)
        if regime_forecaster is not None:
            region = getattr(model, "regime_region", "GLOBAL")
            horizon = getattr(model, "regime_risk_horizon_steps", 1)
            try:
                risk = regime_forecaster.forecast(region=region, horizon_steps=horizon)
                risk_score = getattr(risk, "risk_score", None)
                if isinstance(risk_score, (int, float)):
                    metrics["regime_risk_score"] = float(risk_score)
                p_change_any = getattr(risk, "p_change_any", None)
                if isinstance(p_change_any, (int, float)):
                    metrics["regime_p_change_any"] = float(p_change_any)
            except Exception:  # pragma: no cover - defensive
                logger.exception(
                    "BasicSleevePipeline: regime_forecaster.forecast failed for sleeve=%s on %s",
                    self.config.sleeve_id,
                    as_of_date,
                )

        return metrics


def _build_engines_for_sleeve(
    db_manager: DatabaseManager,
    calendar: TradingCalendar,
    config: SleeveConfig,
    broker: BacktestBroker,
    *,
    apply_risk: bool = True,
    lambda_provider: object | None = None,
) -> BasicSleevePipeline:
    """Construct a :class:`BasicSleevePipeline` for the given sleeve.

    This helper initialises the shared DataReader and all dependent
    engines using conservative default hyperparameters.
    """

    data_reader = DataReader(db_manager=db_manager)

    # STAB infrastructure
    stab_storage = StabilityStorage(db_manager=db_manager)
    stab_model = BasicPriceStabilityModel(
        data_reader=data_reader,
        calendar=calendar,
        window_days=63,
    )
    stab_engine = StabilityEngine(model=stab_model, storage=stab_storage)
    stab_forecaster = StabilityStateChangeForecaster(storage=stab_storage)

    # Regime state-change forecaster for region-level regime risk in the
    # sleeve's universe model.
    regime_storage = RegimeStorage(db_manager=db_manager)
    regime_forecaster = RegimeStateChangeForecaster(storage=regime_storage)

    # Assessment infrastructure – backend is configurable via SleeveConfig.
    assessment_storage = InstrumentScoreStorage(db_manager=db_manager)

    backend = getattr(config, "assessment_backend", "basic")
    use_joint_ctx = getattr(config, "assessment_use_joint_context", False)
    ctx_model_id = getattr(
        config,
        "assessment_context_model_id",
        "joint-assessment-context-v1",
    )
    assessment_model_id = getattr(config, "assessment_model_id", None)
    if assessment_model_id is None:
        # Choose a sensible default based on backend.
        if backend == "basic":
            assessment_model_id = "assessment-basic-v1"
        elif backend == "context":
            assessment_model_id = "assessment-context-v1"
        else:
            assessment_model_id = backend

    if backend == "basic":
        assessment_model = BasicAssessmentModel(
            data_reader=data_reader,
            calendar=calendar,
            stability_storage=stab_storage,
            db_manager=db_manager,
            use_assessment_context=use_joint_ctx,
            assessment_context_model_id=ctx_model_id,
        )
    elif backend == "context":
        assessment_model = ContextAssessmentModel(
            db_manager=db_manager,
            assessment_context_model_id=ctx_model_id,
        )
    else:
        raise ValueError(f"Unknown assessment_backend {backend!r} in SleeveConfig")

    assessment_engine = AssessmentEngine(
        model=assessment_model,
        storage=assessment_storage,
        model_id=assessment_model_id,
    )

    # Universe infrastructure with Assessment integration enabled.
    universe_storage = UniverseStorage(db_manager=db_manager)
    universe_model = BasicUniverseModel(
        db_manager=db_manager,
        calendar=calendar,
        data_reader=data_reader,
        profile_service=None,  # profile-aware universes can be added later
        stability_storage=stab_storage,
        market_ids=(config.market_id,),
        min_avg_volume=100_000.0,
        max_soft_target_score=90.0,
        exclude_breakers=True,
        exclude_weak_profile_when_fragile=True,
        max_universe_size=None,
        sector_max_names=None,
        min_price=0.0,
        hard_exclusion_list=(),
        issuer_exclusion_list=(),
        window_days=63,
        use_assessment_scores=True,
        assessment_strategy_id=config.assessment_strategy_id,
        assessment_horizon_days=config.assessment_horizon_days,
        assessment_score_weight=50.0,
        # Optional lambda opportunity integration for research/backtests.
        lambda_score_provider=lambda_provider,
        lambda_score_weight=config.lambda_score_weight,
        # STAB state-change risk integration consistent with pipeline
        # universes.
        stability_state_change_forecaster=stab_forecaster,
        stability_risk_alpha=config.stability_risk_alpha,
        stability_risk_horizon_steps=config.stability_risk_horizon_steps,
        # Regime state-change risk integration. As in the pipeline, this is
        # effectively disabled unless ``config.regime_risk_alpha`` is set
        # to a non-zero value.
        regime_forecaster=regime_forecaster,
        regime_region=config.market_id.split("_")[0],
        regime_risk_alpha=config.regime_risk_alpha,
        regime_risk_horizon_steps=1,
    )
    universe_engine = UniverseEngine(model=universe_model, storage=universe_storage)

    # Portfolio & Risk infrastructure – basic long-only model.
    portfolio_storage = PortfolioStorage(db_manager=db_manager)
    portfolio_config = PortfolioConfig(
        portfolio_id=config.portfolio_id,
        strategies=[config.strategy_id],
        markets=[config.market_id],
        base_currency="USD",
        risk_model_id="basic-longonly-v1",
        optimizer_type="SIMPLE_LONG_ONLY",
        risk_aversion_lambda=1.0,
        leverage_limit=1.0,
        gross_exposure_limit=1.0,
        per_instrument_max_weight=0.10,
        sector_limits={},
        country_limits={},
        factor_limits={},
        fragility_exposure_limit=1.0,
        turnover_limit=1.0,
        cost_model_id="none",
        # Optional scenario-based risk; if a scenario_risk_set_id is
        # configured on the sleeve, enable inline scenario P&L for this
        # portfolio.
        scenario_risk_scenario_set_ids=[config.scenario_risk_set_id]
        if getattr(config, "scenario_risk_set_id", None)
        else [],
    )
    portfolio_model = BasicLongOnlyPortfolioModel(
        universe_storage=universe_storage,
        config=portfolio_config,
        universe_id=config.universe_id,
    )
    portfolio_engine = PortfolioEngine(
        model=portfolio_model,
        storage=portfolio_storage,
        region="US",  # simple default region for US_EQ; can be extended later
    )

    # Determine the candidate instrument universe once based on the
    # current contents of the instruments table.
    try:
        instruments = universe_model._enumerate_instruments()  # type: ignore[attr-defined]
        # BasicUniverseModel._enumerate_instruments returns
        # (instrument_id, issuer_id, sector, market_id) tuples; we cache the
        # instrument_ids for STAB/Assessment scoring across the backtest
        # horizon.
        instrument_ids = [
            inst_id for inst_id, _issuer_id, _sector, _market_id in instruments
        ]
    except Exception:  # pragma: no cover - defensive
        logger.exception(
            "BasicSleevePipeline: failed to enumerate instruments for markets=%s",
            universe_model.market_ids,
        )
        instrument_ids = []

    return BasicSleevePipeline(
        db_manager=db_manager,
        calendar=calendar,
        config=config,
        broker=broker,
        data_reader=data_reader,
        time_machine=broker.time_machine,
        stab_engine=stab_engine,
        assessment_engine=assessment_engine,
        universe_engine=universe_engine,
        portfolio_engine=portfolio_engine,
        instrument_ids=instrument_ids,
        apply_risk=apply_risk,
    )


def build_basic_sleeve_target_fn(
    db_manager: DatabaseManager,
    calendar: TradingCalendar,
    config: SleeveConfig,
    broker: BacktestBroker,
    *,
    apply_risk: bool = True,
    lambda_provider: object | None = None,
) -> TargetPositionsFn:
    """Return a ``target_positions_fn`` suitable for :class:`BacktestRunner`.

    The returned callable closes over a :class:`BasicSleevePipeline` and
    can be passed directly as ``target_positions_fn`` when constructing a
    :class:`BacktestRunner` instance.

    Args:
        apply_risk: If ``True`` (default), invoke the Risk Management
            Service to cap per-name weights before converting them into
            target positions. If ``False``, use raw portfolio weights.
    """

    pipeline = _build_engines_for_sleeve(
        db_manager=db_manager,
        calendar=calendar,
        config=config,
        broker=broker,
        apply_risk=apply_risk,
        lambda_provider=lambda_provider,
    )

    def _fn(as_of_date: date) -> Dict[str, float]:
        return pipeline.target_positions_for_date(as_of_date)

    return _fn


def build_basic_sleeve_target_and_exposure_fns(
    db_manager: DatabaseManager,
    calendar: TradingCalendar,
    config: SleeveConfig,
    broker: BacktestBroker,
    *,
    apply_risk: bool = True,
    lambda_provider: object | None = None,
) -> tuple[TargetPositionsFn, TargetPositionsFn]:
    """Construct both ``target_positions_fn`` and ``exposure_metrics_fn``.

    This is a thin wrapper around :func:`_build_engines_for_sleeve` that
    exposes :meth:`BasicSleevePipeline.exposure_metrics_for_date` so
    :class:`BacktestRunner` can attach lambda/state-aware diagnostics to
    ``backtest_daily_equity`` rows.
    """

    pipeline = _build_engines_for_sleeve(
        db_manager=db_manager,
        calendar=calendar,
        config=config,
        broker=broker,
        apply_risk=apply_risk,
        lambda_provider=lambda_provider,
    )

    def _target(as_of_date: date) -> Dict[str, float]:
        return pipeline.target_positions_for_date(as_of_date)

    def _exposure(as_of_date: date) -> Dict[str, float]:
        return pipeline.exposure_metrics_for_date(as_of_date)

    return _target, _exposure
