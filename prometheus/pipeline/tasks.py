"""Prometheus v2 – Pipeline phase tasks.

This module contains the concrete phase tasks used by the engine run
state machine. Each task operates on a single ``EngineRun`` and
advances it through the phases by invoking existing engines
(Regime/Profiles/STAB/Universe/Books).

The design goal is to keep each phase function **idempotent** and
stateless beyond the database. Re-running a phase for the same
(as_of_date, region) should either be a no-op or simply overwrite
previous results with the same values.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import yaml
from psycopg2.extras import Json

from prometheus.core.config import get_config
from prometheus.core.database import DatabaseManager, get_db_manager
from prometheus.core.ids import generate_uuid
from prometheus.core.logging import get_logger
from prometheus.core.time import TradingCalendar
from prometheus.data.reader import DataReader
from prometheus.profiles import (
    ProfileService,
    ProfileStorage,
    ProfileFeatureBuilder,
    BasicProfileEmbedder,
)
from prometheus.stability import (
    StabilityEngine,
    StabilityStorage,
    BasicPriceStabilityModel,
    StabilityStateChangeForecaster,
)
from prometheus.regime import RegimeStorage
from prometheus.regime.state_change import RegimeStateChangeForecaster
from prometheus.universe import (
    UniverseEngine,
    UniverseStorage,
    BasicUniverseModel,
)
from prometheus.universe.config import UniverseConfig
from prometheus.assessment import AssessmentEngine
from prometheus.portfolio import (
    PortfolioConfig,
    PortfolioEngine,
    PortfolioStorage,
    BasicLongOnlyPortfolioModel,
)
from prometheus.assessment.model_basic import BasicAssessmentModel
from prometheus.assessment.storage import InstrumentScoreStorage
from prometheus.fragility import (
    BasicFragilityAlphaModel,
    FragilityAlphaEngine,
    FragilityStorage,
)
from prometheus.pipeline.state import EngineRun, RunPhase, update_phase
from prometheus.meta import MetaStorage, MetaOrchestrator, EngineDecision
from prometheus.backtest import SleeveRunSummary, run_backtest_campaign
from prometheus.backtest.catalog import build_core_long_sleeves
from prometheus.opportunity.lambda_provider import CsvLambdaClusterScoreProvider
from prometheus.risk import apply_risk_constraints
from prometheus.scripts.backfill_portfolio_stab_scenario_metrics import (
    backfill_portfolio_stab_scenario_metrics_for_range,
)
from prometheus.scripts.backfill_backtest_stab_scenario_metrics import (
    summarise_backtest_stab_scenario_metrics,
)


logger = get_logger(__name__)

# Project root used for locating config files (e.g. configs/universe, configs/portfolio).
PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class DailyUniverseLambdaConfig:
    """Configuration for lambda-aware daily universes.

    This small config surface allows enabling lambda-based opportunity
    scores inside :func:`run_universes_for_run` without altering the
    public API. When ``predictions_csv`` is ``None`` or
    ``score_weight`` is zero, lambda integration is effectively
    disabled.
    """

    predictions_csv: str | None = None
    experiment_id: str | None = None
    score_column: str = "lambda_hat"
    score_weight: float = 0.0


@dataclass
class DailyPortfolioRiskConfig:
    """Configuration for scenario- and STAB-scenario-aware daily portfolios.

    When ``scenario_risk_set_id`` is provided, the daily
    :func:`run_books_for_run` phase will enable inline scenario P&L for
    the core long-only equity book via ``PortfolioConfig``.

    When ``stab_scenario_set_id`` is provided, the BOOKS phase will also
    compute STAB-scenario diagnostics for the daily portfolio using the
    same helper as the backtest campaign.
    """

    scenario_risk_set_id: str | None = None
    stab_scenario_set_id: str | None = None
    stab_joint_model_id: str = "joint-stab-fragility-v1"


def _load_daily_universe_lambda_config(region: str) -> DailyUniverseLambdaConfig:
    """Load lambda config for CORE_EQ_<REGION> universes from YAML.

    The expected schema is ``configs/universe/core_long_eq_daily.yaml``::

        core_long_eq:
          US:
            lambda_predictions_csv: "data/lambda_predictions_US_EQ.csv"
            lambda_experiment_id: "US_EQ_GL_POLY2_V0"
            lambda_score_column: "lambda_hat"
            lambda_score_weight: 10.0

    All keys are optional; missing files or malformed content result in
    a default config with lambda disabled.
    """

    cfg_path = PROJECT_ROOT / "configs" / "universe" / "core_long_eq_daily.yaml"
    if not cfg_path.exists():
        return DailyUniverseLambdaConfig()

    try:
        raw: Any = yaml.safe_load(cfg_path.read_text())
    except Exception:  # pragma: no cover - defensive
        logger.exception(
            "Failed to load daily universe lambda config from %s; disabling lambda for region=%s",
            cfg_path,
            region,
        )
        return DailyUniverseLambdaConfig()

    if not isinstance(raw, dict):
        logger.warning(
            "Daily universe lambda config at %s is not a mapping; disabling lambda for region=%s",
            cfg_path,
            region,
        )
        return DailyUniverseLambdaConfig()

    core_cfg = raw.get("core_long_eq")
    if not isinstance(core_cfg, dict):
        return DailyUniverseLambdaConfig()

    region_cfg = core_cfg.get(region.upper()) or {}
    if not isinstance(region_cfg, dict):
        return DailyUniverseLambdaConfig()

    predictions_csv_raw = region_cfg.get("lambda_predictions_csv")
    experiment_id_raw = region_cfg.get("lambda_experiment_id")
    score_column_raw = region_cfg.get("lambda_score_column", "lambda_hat")
    score_weight_raw = region_cfg.get("lambda_score_weight", 0.0)

    predictions_csv = (
        str(predictions_csv_raw) if isinstance(predictions_csv_raw, str) else None
    )
    experiment_id = str(experiment_id_raw) if isinstance(experiment_id_raw, str) else None
    score_column = str(score_column_raw) if isinstance(score_column_raw, str) else "lambda_hat"
    try:
        score_weight = float(score_weight_raw)
    except (TypeError, ValueError):  # pragma: no cover - defensive
        score_weight = 0.0

    return DailyUniverseLambdaConfig(
        predictions_csv=predictions_csv,
        experiment_id=experiment_id,
        score_column=score_column,
        score_weight=score_weight,
    )


def _load_daily_portfolio_risk_config(region: str) -> DailyPortfolioRiskConfig:
    """Load scenario risk config for <REGION>_CORE_LONG_EQ portfolios.

    The expected schema is ``configs/portfolio/core_long_eq_daily.yaml``::

        core_long_eq:
          US:
            scenario_risk_set_id: "US_EQ_HIST_20D_2020ON"

    Missing files or malformed content result in scenario risk being
    disabled for the given region.
    """

    cfg_path = PROJECT_ROOT / "configs" / "portfolio" / "core_long_eq_daily.yaml"
    if not cfg_path.exists():
        return DailyPortfolioRiskConfig()

    try:
        raw: Any = yaml.safe_load(cfg_path.read_text())
    except Exception:  # pragma: no cover - defensive
        logger.exception(
            "Failed to load daily portfolio risk config from %s; disabling scenario risk for region=%s",
            cfg_path,
            region,
        )
        return DailyPortfolioRiskConfig()

    if not isinstance(raw, dict):
        logger.warning(
            "Daily portfolio risk config at %s is not a mapping; disabling scenario risk for region=%s",
            cfg_path,
            region,
        )
        return DailyPortfolioRiskConfig()

    core_cfg = raw.get("core_long_eq")
    if not isinstance(core_cfg, dict):
        return DailyPortfolioRiskConfig()

    region_cfg = core_cfg.get(region.upper()) or {}
    if not isinstance(region_cfg, dict):
        return DailyPortfolioRiskConfig()

    scenario_set_raw = region_cfg.get("scenario_risk_set_id")
    stab_scenario_set_raw = region_cfg.get("stab_scenario_set_id")
    stab_joint_model_raw = region_cfg.get("stab_joint_model_id", "joint-stab-fragility-v1")

    scenario_set_id = str(scenario_set_raw) if isinstance(scenario_set_raw, str) else None
    stab_scenario_set_id = (
        str(stab_scenario_set_raw) if isinstance(stab_scenario_set_raw, str) else None
    )
    stab_joint_model_id = (
        str(stab_joint_model_raw)
        if isinstance(stab_joint_model_raw, str)
        else "joint-stab-fragility-v1"
    )

    return DailyPortfolioRiskConfig(
        scenario_risk_set_id=scenario_set_id,
        stab_scenario_set_id=stab_scenario_set_id,
        stab_joint_model_id=stab_joint_model_id,
    )


# Mapping from logical region codes to market_ids used in instruments.
# This can be extended as additional regions/markets are introduced.
MARKETS_BY_REGION: Dict[str, Tuple[str, ...]] = {
    "US": ("US_EQ",),
    "EU": ("EU_EQ",),
    "ASIA": ("ASIA_EQ",),
}


def _infer_region_from_market_id(market_id: str) -> str | None:
    """Return the logical region corresponding to a market_id, if any.

    This helper inverts MARKETS_BY_REGION for simple use cases where a
    single market maps to a single region (e.g. US_EQ -> US). If no
    mapping is found, ``None`` is returned and callers should fall back
    to explicit configuration.
    """

    for region, markets in MARKETS_BY_REGION.items():
        if market_id in markets:
            return region
    return None


def _get_region_instruments(
    db_manager: DatabaseManager,
    region: str,
) -> List[Tuple[str, str, str]]:
    """Return list of (instrument_id, issuer_id, market_id) for region.

    Instruments are filtered by ``market_id`` and ``status = 'ACTIVE'``.
    If the region is unknown or no mapping is found, an empty list is
    returned.
    """

    markets = MARKETS_BY_REGION.get(region.upper())
    if not markets:
        logger.warning("No market mapping for region %s; skipping", region)
        return []

    sql = """
        SELECT instrument_id, issuer_id, market_id
        FROM instruments
        WHERE market_id = ANY(%s)
          AND status = 'ACTIVE'
    """

    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (list(markets),))
            rows = cursor.fetchall()
        finally:
            cursor.close()

    return [(inst_id, issuer_id, market_id) for inst_id, issuer_id, market_id in rows]


def run_signals_for_run(db_manager: DatabaseManager, run: EngineRun) -> EngineRun:
    """Compute Profiles and STAB signals for the run's date/region.

    This phase currently focuses on Profiles and STAB. Regime integration
    can be added later when a concrete mapping from regions to
    representative instruments or models is finalised.
    """

    logger.info(
        "run_signals_for_run: run_id=%s as_of_date=%s region=%s",
        run.run_id,
        run.as_of_date,
        run.region,
    )

    instruments = _get_region_instruments(db_manager, run.region)
    if not instruments:
        logger.info("No instruments found for region %s; marking SIGNALS_DONE", run.region)
        return update_phase(db_manager, run.run_id, RunPhase.SIGNALS_DONE)

    instrument_ids = [row[0] for row in instruments]
    issuer_ids = sorted({row[1] for row in instruments})
    instrument_to_issuer: Dict[str, str] = {row[0]: row[1] for row in instruments}

    calendar = TradingCalendar()
    reader = DataReader(db_manager=db_manager)

    # Profiles
    profile_storage = ProfileStorage(db_manager=db_manager)
    feature_builder = ProfileFeatureBuilder(
        db_manager=db_manager,
        data_reader=reader,
        calendar=calendar,
    )
    embedder = BasicProfileEmbedder(embedding_dim=16)
    profile_service = ProfileService(
        storage=profile_storage,
        feature_builder=feature_builder,
        embedder=embedder,
    )

    for issuer_id in issuer_ids:
        try:
            profile_service.get_snapshot(issuer_id, run.as_of_date)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception(
                "Failed to build profile snapshot issuer_id=%s as_of=%s: %s",
                issuer_id,
                run.as_of_date,
                exc,
            )

    # STAB – profile-aware BasicPriceStabilityModel
    stab_storage = StabilityStorage(db_manager=db_manager)

    def _instrument_to_issuer(instrument_id: str) -> str | None:
        return instrument_to_issuer.get(instrument_id)

    stab_model = BasicPriceStabilityModel(
        data_reader=reader,
        calendar=calendar,
        window_days=63,
        profile_service=profile_service,
        instrument_to_issuer=_instrument_to_issuer,
    )
    stab_engine = StabilityEngine(model=stab_model, storage=stab_storage)

    for instrument_id in instrument_ids:
        try:
            stab_engine.score_entity(run.as_of_date, "INSTRUMENT", instrument_id)
        except ValueError as exc:
            # Insufficient history or data issues: log and continue.
            logger.warning(
                "Skipping STAB score for instrument %s on %s: %s",
                instrument_id,
                run.as_of_date,
                exc,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception(
                "Unexpected error scoring STAB for instrument %s on %s: %s",
                instrument_id,
                run.as_of_date,
                exc,
            )

    # Fragility Alpha – combine STAB soft-target state and optional
    # scenario-based losses into scalar fragility scores. For the daily
    # engine runs we start with a configuration that only uses the latest
    # STAB state (scenario_set_id=None); more advanced scenario integration
    # is handled by dedicated research/CLI workflows.
    fragility_storage = FragilityStorage(db_manager=db_manager)
    fragility_model = BasicFragilityAlphaModel(
        db_manager=db_manager,
        stability_storage=stab_storage,
        scenario_set_id=None,
    )
    fragility_engine = FragilityAlphaEngine(
        model=fragility_model,
        storage=fragility_storage,
    )

    for instrument_id in instrument_ids:
        try:
            fragility_engine.score_and_save(
                run.as_of_date,
                "INSTRUMENT",
                instrument_id,
            )
        except Exception as exc:  # pragma: no cover - defensive
            # Fragility is an overlay on top of STAB; failures here should
            # not block the rest of the signals pipeline.
            logger.exception(
                "Unexpected error scoring Fragility Alpha for instrument %s on %s: %s",
                instrument_id,
                run.as_of_date,
                exc,
            )

    # Assessment – basic price/STAB-based model.
    try:
        markets = MARKETS_BY_REGION.get(run.region.upper())
        market_id = markets[0] if markets else run.region.upper()

        assessment_storage = InstrumentScoreStorage(db_manager=db_manager)
        assessment_model = BasicAssessmentModel(
            data_reader=reader,
            calendar=calendar,
            stability_storage=stab_storage,
        )
        assessment_engine = AssessmentEngine(
            model=assessment_model,
            storage=assessment_storage,
            model_id="assessment-basic-v1",
        )

        # For now we use a simple default strategy identifier tied to the
        # region; this can be replaced by a proper strategies table lookup
        # in a later iteration.
        strategy_id = f"{run.region.upper()}_CORE_LONG_EQ"

        assessment_engine.score_universe(
            strategy_id=strategy_id,
            market_id=market_id,
            instrument_ids=instrument_ids,
            as_of_date=run.as_of_date,
            horizon_days=21,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception(
            "run_signals_for_run: Assessment Engine failed for run_id=%s: %s",
            run.run_id,
            exc,
        )

    return update_phase(db_manager, run.run_id, RunPhase.SIGNALS_DONE)


def run_universes_for_run(db_manager: DatabaseManager, run: EngineRun) -> EngineRun:
    """Build universes for the run's date/region and persist members.

    Currently constructs a single long-friendly equity universe
    ``CORE_EQ_<REGION>`` using :class:`BasicUniverseModel`.
    """

    logger.info(
        "run_universes_for_run: run_id=%s as_of_date=%s region=%s",
        run.run_id,
        run.as_of_date,
        run.region,
    )

    markets = MARKETS_BY_REGION.get(run.region.upper())
    if not markets:
        logger.warning("No market mapping for region %s; marking UNIVERSES_DONE", run.region)
        return update_phase(db_manager, run.run_id, RunPhase.UNIVERSES_DONE)

    calendar = TradingCalendar()
    reader = DataReader(db_manager=db_manager)

    # Profiles and STAB storage reused to configure the universe model.
    profile_storage = ProfileStorage(db_manager=db_manager)
    feature_builder = ProfileFeatureBuilder(
        db_manager=db_manager,
        data_reader=reader,
        calendar=calendar,
    )
    embedder = BasicProfileEmbedder(embedding_dim=16)
    profile_service = ProfileService(
        storage=profile_storage,
        feature_builder=feature_builder,
        embedder=embedder,
    )

    stab_storage = StabilityStorage(db_manager=db_manager)

    universe_storage = UniverseStorage(db_manager=db_manager)

    # STAB state-change forecaster for per-instrument fragility risk
    # integration in universes.
    stab_forecaster = StabilityStateChangeForecaster(storage=stab_storage)

    # Regime state-change forecaster for region-level regime risk. We keep
    # the regime risk alpha at its UniverseConfig default (0.0) for now so
    # that enabling regime-aware universes is an explicit configuration
    # decision rather than a behavioural surprise.
    regime_storage = RegimeStorage(db_manager=db_manager)
    regime_forecaster = RegimeStateChangeForecaster(storage=regime_storage)

    # For this iteration we construct a simple UniverseConfig in-memory
    # rather than loading it from engine_configs. The parameters are
    # conservative defaults for a long-only core equity universe.
    strategy_id = f"{run.region.upper()}_CORE_LONG_EQ"
    universe_config = UniverseConfig(
        strategy_id=strategy_id,
        markets=list(markets),
        max_universe_size=200,
        min_liquidity_adv=100_000.0,
        min_price=1.0,
        sector_max_names=0,
        universe_model_id="basic-equity-v1",
        # Start with regime risk disabled (alpha=0.0) so that turning it on
        # is an explicit config change once regime history is populated.
        regime_region=run.region.upper(),
        regime_risk_alpha=0.0,
        regime_risk_horizon_steps=1,
        stability_risk_alpha=0.5,
        stability_risk_horizon_steps=1,
    )

    # Optional lambda-aware universe configuration driven by YAML. When a
    # predictions CSV and non-zero score_weight are provided for the
    # region, we construct a CsvLambdaClusterScoreProvider and wire it
    # into BasicUniverseModel.
    lambda_cfg = _load_daily_universe_lambda_config(run.region)
    lambda_provider: object | None = None
    lambda_score_weight = 0.0
    if lambda_cfg.predictions_csv is not None and lambda_cfg.score_weight != 0.0:
        lambda_csv_path = Path(lambda_cfg.predictions_csv)
        if not lambda_csv_path.is_absolute():
            lambda_csv_path = PROJECT_ROOT / lambda_csv_path
        try:
            lambda_provider = CsvLambdaClusterScoreProvider(
                csv_path=lambda_csv_path,
                experiment_id=lambda_cfg.experiment_id,
                score_column=lambda_cfg.score_column,
            )
            lambda_score_weight = float(lambda_cfg.score_weight)
        except Exception as exc:  # pragma: no cover - defensive
            # In daily engine runs we treat lambda provider initialisation
            # failures as a non-fatal condition and simply disable lambda
            # integration for the region instead of surfacing a full
            # stack trace on every run.
            logger.warning(
                "run_universes_for_run: disabling lambda integration for region=%s due to error "
                "initialising CsvLambdaClusterScoreProvider from %s: %s",
                run.region,
                lambda_csv_path,
                exc,
            )
            lambda_provider = None
            lambda_score_weight = 0.0

    # TODO(v1-regime): once regime history is populated for the run
    # region, instantiate a RegimeStateChangeForecaster and pass it into
    # BasicUniverseModel via ``regime_forecaster``, ``regime_region``, and
    # a non-zero ``regime_risk_alpha`` to make universes explicitly
    # regime/state-aware.
    universe_model = BasicUniverseModel(
        db_manager=db_manager,
        calendar=calendar,
        data_reader=reader,
        profile_service=profile_service,
        stability_storage=stab_storage,
        market_ids=tuple(universe_config.markets),
        min_avg_volume=universe_config.min_liquidity_adv,
        max_universe_size=universe_config.max_universe_size,
        sector_max_names=universe_config.sector_max_names,
        min_price=universe_config.min_price,
        hard_exclusion_list=tuple(universe_config.hard_exclusion_list),
        issuer_exclusion_list=tuple(universe_config.issuer_exclusion_list),
        # Align Assessment strategy id with the one used in the signals
        # phase so that universe ranking can incorporate Assessment
        # scores when available.
        use_assessment_scores=True,
        assessment_strategy_id=strategy_id,
        assessment_horizon_days=21,
        # Regime risk integration remains disabled until
        # ``universe_config.regime_risk_alpha`` is set to a non-zero value
        # in configuration. The forecaster is wired so that enabling
        # regime-aware universes is a config-only change.
        regime_forecaster=regime_forecaster,
        regime_region=universe_config.regime_region or run.region.upper(),
        regime_risk_alpha=universe_config.regime_risk_alpha,
        regime_risk_horizon_steps=universe_config.regime_risk_horizon_steps,
        # STAB state-change risk integration: apply a modest multiplicative
        # penalty based on per-instrument soft-target state-change risk.
        stability_state_change_forecaster=stab_forecaster,
        stability_risk_alpha=universe_config.stability_risk_alpha,
        stability_risk_horizon_steps=universe_config.stability_risk_horizon_steps,
        # Optional lambda opportunity integration.
        lambda_score_provider=lambda_provider,
        lambda_score_weight=lambda_score_weight,
    )
    universe_engine = UniverseEngine(model=universe_model, storage=universe_storage)

    universe_id = f"CORE_EQ_{run.region.upper()}"
    universe_engine.build_and_save(run.as_of_date, universe_id)

    return update_phase(db_manager, run.run_id, RunPhase.UNIVERSES_DONE)


def run_books_for_run(
    db_manager: DatabaseManager,
    run: EngineRun,
    *,
    apply_risk: bool = True,
) -> EngineRun:
    """Run book-level strategies for the run's date/region.

    Currently implements a single core long equity book::

        <REGION>_CORE_LONG_EQ

    which uses the corresponding ``CORE_EQ_<REGION>`` universe and
    UniverseMember scores to derive target weights via the
    PortfolioEngine.
    """

    logger.info(
        "run_books_for_run: run_id=%s as_of_date=%s region=%s",
        run.run_id,
        run.as_of_date,
        run.region,
    )

    markets = MARKETS_BY_REGION.get(run.region.upper())
    if not markets:
        logger.warning("No market mapping for region %s; marking BOOKS_DONE", run.region)
        return update_phase(db_manager, run.run_id, RunPhase.BOOKS_DONE)

    universe_id = f"CORE_EQ_{run.region.upper()}"
    book_id = f"{run.region.upper()}_CORE_LONG_EQ"

    universe_storage = UniverseStorage(db_manager=db_manager)

    # Optional scenario-based risk configuration for the daily core book
    # driven by YAML. When a ``scenario_risk_set_id`` is provided for the
    # region, we enable inline scenario P&L inside the PortfolioEngine.
    risk_cfg = _load_daily_portfolio_risk_config(run.region)
    scenario_set_ids: list[str] = []
    if risk_cfg.scenario_risk_set_id is not None:
        scenario_set_ids = [risk_cfg.scenario_risk_set_id]

    # Simple, hard-coded PortfolioConfig for the core long-only equity
    # book in this iteration. This can later be sourced from
    # engine_configs.
    portfolio_config = PortfolioConfig(
        portfolio_id=book_id,
        strategies=[book_id],
        markets=list(MARKETS_BY_REGION.get(run.region.upper(), ())),
        base_currency="USD",
        risk_model_id="basic-longonly-v1",
        optimizer_type="SIMPLE_LONG_ONLY",
        risk_aversion_lambda=0.0,
        leverage_limit=1.0,
        gross_exposure_limit=1.0,
        per_instrument_max_weight=0.05,
        sector_limits={},
        country_limits={},
        factor_limits={},
        fragility_exposure_limit=0.5,
        turnover_limit=0.5,
        cost_model_id="none",
        scenario_risk_scenario_set_ids=scenario_set_ids,
    )

    portfolio_storage = PortfolioStorage(db_manager=db_manager)
    portfolio_model = BasicLongOnlyPortfolioModel(
        universe_storage=universe_storage,
        config=portfolio_config,
        universe_id=universe_id,
    )
    portfolio_engine = PortfolioEngine(
        model=portfolio_model,
        storage=portfolio_storage,
        region=run.region,
    )

    target = portfolio_engine.optimize_and_save(book_id, run.as_of_date)

    if not target.weights:
        logger.info(
            "PortfolioEngine produced empty target for %s on %s; marking BOOKS_DONE",
            book_id,
            run.as_of_date,
        )
        return update_phase(db_manager, run.run_id, RunPhase.BOOKS_DONE)

    # Optionally compute STAB-scenario diagnostics for the daily
    # portfolio when configured. This reuses the same helper as the
    # backtest campaign but restricts the range to the current as_of
    # date.
    if risk_cfg.stab_scenario_set_id is not None:
        try:
            backfill_portfolio_stab_scenario_metrics_for_range(
                db_manager=db_manager,
                portfolio_id=book_id,
                scenario_set_id=risk_cfg.stab_scenario_set_id,
                stab_model_id=risk_cfg.stab_joint_model_id,
                start=run.as_of_date,
                end=run.as_of_date,
                limit=None,
            )
        except Exception:  # pragma: no cover - defensive
            logger.exception(
                "run_books_for_run: STAB-scenario backfill failed for portfolio_id=%s as_of=%s",
                book_id,
                run.as_of_date,
            )

    # Optionally apply Risk Management constraints to the target weights in
    # order to log risk_actions for analysis. For now we do not overwrite
    # the stored target_portfolios weights; execution services can consult
    # risk_actions separately when planning orders.
    if apply_risk:
        decisions = [
            {"instrument_id": inst_id, "target_weight": float(weight)}
            for inst_id, weight in target.weights.items()
        ]
        try:
            apply_risk_constraints(
                decisions,
                strategy_id=book_id,
                db_manager=db_manager,
            )
        except Exception:  # pragma: no cover - defensive logging only
            logger.exception(
                "run_books_for_run: apply_risk_constraints failed for book_id=%s as_of_date=%s",
                book_id,
                run.as_of_date,
            )

    return update_phase(db_manager, run.run_id, RunPhase.BOOKS_DONE)


def run_meta_for_strategy(
    db_manager: DatabaseManager,
    strategy_id: str,
    as_of_date: date,
    top_k: int = 3,
) -> str | None:
    """Run Meta-Orchestrator for a strategy and record a decision.

    This helper reads all backtest runs for ``strategy_id`` via
    :class:`MetaOrchestrator`, selects the top-k sleeves based on
    backtest metrics, and inserts a single row into ``engine_decisions``
    capturing the selection.

    Args:
        db_manager: Database manager for the runtime database.
        strategy_id: Logical strategy identifier whose sleeves should be
            evaluated (e.g. "US_CORE_LONG_EQ").
        as_of_date: Date on which the meta decision is being recorded.
        top_k: Number of top sleeves to select.

    Returns:
        The generated ``decision_id`` if a decision was recorded, or
        ``None`` if no sleeves were available for the strategy.
    """

    storage = MetaStorage(db_manager=db_manager)
    orchestrator = MetaOrchestrator(storage=storage)

    evaluations = orchestrator.select_top_sleeves(strategy_id, k=top_k)
    if not evaluations:
        logger.info(
            "run_meta_for_strategy: no evaluated sleeves for strategy_id=%s; skipping decision",
            strategy_id,
        )
        return None

    decision_id = generate_uuid()

    # Derive a market_id from the first selected sleeve; if unavailable,
    # leave as None.
    first_cfg = evaluations[0].sleeve_config
    market_id = getattr(first_cfg, "market_id", None)

    input_refs = {
        "strategy_id": strategy_id,
        "top_k": top_k,
        "candidate_runs": [
            {"run_id": ev.run_id, "sleeve_id": ev.sleeve_config.sleeve_id}
            for ev in evaluations
        ],
    }

    output_refs = {
        "selected_sleeves": [
            {
                "run_id": ev.run_id,
                "sleeve_id": ev.sleeve_config.sleeve_id,
                "metrics": ev.metrics,
            }
            for ev in evaluations
        ],
    }

    decision = EngineDecision(
        decision_id=decision_id,
        engine_name="META_ORCHESTRATOR",
        run_id=None,
        strategy_id=strategy_id,
        market_id=market_id,
        as_of_date=as_of_date,
        config_id=None,
        input_refs=input_refs,
        output_refs=output_refs,
        metadata={"type": "sleeve_selection"},
    )

    storage.save_engine_decision(decision)

    logger.info(
        "run_meta_for_strategy: recorded decision_id=%s for strategy_id=%s top_k=%d",
        decision_id,
        strategy_id,
        top_k,
    )

    return decision_id


def run_backtest_campaign_and_meta_for_strategy(
    db_manager: DatabaseManager,
    strategy_id: str,
    market_id: str,
    start_date: date,
    end_date: date,
    top_k: int = 3,
    initial_cash: float = 1_000_000.0,
    *,
    apply_risk: bool = True,
    assessment_backend: str = "basic",
    assessment_use_joint_context: bool = False,
    assessment_context_model_id: str = "joint-assessment-context-v1",
    assessment_model_id: str | None = None,
    stability_risk_alpha: float | None = None,
    stability_risk_horizon_steps: int | None = None,
    regime_risk_alpha: float | None = None,
    lambda_predictions_csv: str | None = None,
    lambda_experiment_id: str | None = None,
    lambda_score_weight: float | None = None,
    scenario_risk_set_id: str | None = None,
    stab_scenario_set_id: str | None = None,
    stab_joint_model_id: str = "joint-stab-fragility-v1",
) -> tuple[list[SleeveRunSummary], str | None]:
    """Run a sleeve backtest campaign and Meta-Orchestrator for a strategy.

    This helper is a convenience for performing a full offline
    config-space sweep for a single logical strategy:

    1. Construct a small grid of core long-only sleeves for the given
       ``strategy_id`` and ``market_id``.
    2. Run a backtest campaign over ``[start_date, end_date]`` using the
       basic STAB/Assessment/Universe/Portfolio sleeve pipeline.
    3. Invoke :func:`run_meta_for_strategy` to record a Meta-Orchestrator
       decision selecting the top-k sleeves by backtest metrics.

    Returns the list of :class:`SleeveRunSummary` objects produced by the
    campaign together with the ``decision_id`` recorded by the
    Meta-Orchestrator (or ``None`` if no decision was written).
    """

    if end_date < start_date:
        raise ValueError("end_date must be >= start_date")

    # If the caller did not provide explicit lambda/scenario/STAB
    # configuration, default to the same settings used by the daily
    # UNIVERSES/BOOKS pipeline for the inferred region (when available).
    region = _infer_region_from_market_id(market_id)
    if region is not None:
        # Lambda defaults from daily universe config.
        if lambda_predictions_csv is None or lambda_score_weight is None:
            lambda_cfg = _load_daily_universe_lambda_config(region)
            if lambda_predictions_csv is None and lambda_cfg.predictions_csv is not None:
                lambda_predictions_csv = lambda_cfg.predictions_csv
            if lambda_experiment_id is None and lambda_cfg.experiment_id is not None:
                lambda_experiment_id = lambda_cfg.experiment_id
            if (
                lambda_score_weight is None
                and lambda_cfg.score_weight is not None
                and lambda_cfg.score_weight != 0.0
            ):
                lambda_score_weight = float(lambda_cfg.score_weight)

        # Scenario and STAB-scenario defaults from daily portfolio config.
        if scenario_risk_set_id is None or stab_scenario_set_id is None:
            risk_cfg = _load_daily_portfolio_risk_config(region)
            if scenario_risk_set_id is None:
                scenario_risk_set_id = risk_cfg.scenario_risk_set_id
            if stab_scenario_set_id is None:
                stab_scenario_set_id = risk_cfg.stab_scenario_set_id
            # If the caller did not override the default STAB joint model,
            # align it with the daily config as well.
            if stab_joint_model_id == "joint-stab-fragility-v1" and risk_cfg.stab_joint_model_id:
                stab_joint_model_id = risk_cfg.stab_joint_model_id

    calendar = TradingCalendar()
    sleeve_configs = build_core_long_sleeves(strategy_id=strategy_id, market_id=market_id)
    if not sleeve_configs:
        logger.info(
            "run_backtest_campaign_and_meta_for_strategy: no sleeve configs for strategy_id=%s market_id=%s",
            strategy_id,
            market_id,
        )
        return [], None

    # Apply assessment configuration to each sleeve in the campaign.
    for cfg in sleeve_configs:
        cfg.assessment_backend = assessment_backend
        cfg.assessment_use_joint_context = assessment_use_joint_context
        cfg.assessment_context_model_id = assessment_context_model_id
        if assessment_model_id is not None:
            cfg.assessment_model_id = assessment_model_id
        # Optional STAB/regime/scenario configuration for the sleeve
        if stability_risk_alpha is not None:
            cfg.stability_risk_alpha = stability_risk_alpha
        if stability_risk_horizon_steps is not None:
            cfg.stability_risk_horizon_steps = stability_risk_horizon_steps
        if regime_risk_alpha is not None:
            cfg.regime_risk_alpha = regime_risk_alpha
        if scenario_risk_set_id is not None:
            cfg.scenario_risk_set_id = scenario_risk_set_id
        if lambda_score_weight is not None:
            cfg.lambda_score_weight = lambda_score_weight

    lambda_provider = None
    if lambda_predictions_csv is not None:
        preds_path = Path(lambda_predictions_csv)
        try:
            lambda_provider = CsvLambdaClusterScoreProvider(
                csv_path=preds_path,
                experiment_id=lambda_experiment_id,
                score_column="lambda_hat",
            )
        except Exception as exc:  # pragma: no cover - defensive
            # For backtest campaigns, failure to initialise a lambda
            # provider (e.g. missing experiment_id rows) should not abort
            # the entire campaign; we log a concise warning and proceed
            # without lambda integration.
            logger.warning(
                "run_backtest_campaign_and_meta_for_strategy: disabling lambda integration from %s "
                "due to error: %s",
                preds_path,
                exc,
            )
            lambda_provider = None

    summaries = run_backtest_campaign(
        db_manager=db_manager,
        calendar=calendar,
        market_id=market_id,
        start_date=start_date,
        end_date=end_date,
        sleeve_configs=sleeve_configs,
        initial_cash=initial_cash,
        apply_risk=apply_risk,
        lambda_provider=lambda_provider,
    )

    # Optionally enrich portfolio_risk_reports and backtest_runs with
    # STAB-scenario diagnostics when a scenario set is provided. We only
    # attempt this when a real DatabaseManager instance is in use so that
    # pure wiring tests can pass in lightweight stand-ins.
    if (
        stab_scenario_set_id is not None
        and summaries
        and isinstance(db_manager, DatabaseManager)
    ):
        # Backfill portfolio-level STAB-scenario metrics for each
        # portfolio used in the campaign over the campaign window.
        portfolio_ids = sorted({cfg.portfolio_id for cfg in sleeve_configs})
        for portfolio_id in portfolio_ids:
            backfill_portfolio_stab_scenario_metrics_for_range(
                db_manager=db_manager,
                portfolio_id=portfolio_id,
                scenario_set_id=stab_scenario_set_id,
                stab_model_id=stab_joint_model_id,
                start=start_date,
                end=end_date,
                limit=None,
            )

        # Summarise those STAB-scenario metrics into backtest_runs.metrics_json
        # for each run we just created.
        for summary in summaries:
            summarise_backtest_stab_scenario_metrics(
                db_manager=db_manager,
                strategy_id=None,
                run_id=summary.run_id,
            )

    decision_id = run_meta_for_strategy(
        db_manager=db_manager,
        strategy_id=strategy_id,
        as_of_date=end_date,
        top_k=top_k,
    )

    logger.info(
        "run_backtest_campaign_and_meta_for_strategy: strategy_id=%s market_id=%s runs=%d decision_id=%s",
        strategy_id,
        market_id,
        len(summaries),
        decision_id,
    )

    return summaries, decision_id


def advance_run(db_manager: DatabaseManager, run: EngineRun) -> EngineRun:
    """Advance a run by one phase, executing the appropriate task.

    This function does **not** loop; it performs at most one phase
    transition. Callers (e.g. CLI tools or daemons) can repeatedly call
    :func:`advance_run` until the run reaches COMPLETED/FAILED.
    """

    if run.phase == RunPhase.WAITING_FOR_DATA:
        # External ingestion should flip to DATA_READY once EOD data is
        # available. We treat a call in WAITING_FOR_DATA as a no-op.
        logger.info("advance_run: run %s still WAITING_FOR_DATA", run.run_id)
        return run

    if run.phase == RunPhase.DATA_READY:
        return run_signals_for_run(db_manager, run)

    if run.phase == RunPhase.SIGNALS_DONE:
        return run_universes_for_run(db_manager, run)

    if run.phase == RunPhase.UNIVERSES_DONE:
        run_after_books = run_books_for_run(db_manager, run)
        # Finalise to COMPLETED in a separate transition for clarity.
        if run_after_books.phase == RunPhase.BOOKS_DONE:
            return update_phase(db_manager, run_after_books.run_id, RunPhase.COMPLETED)
        return run_after_books

    if run.phase in {RunPhase.BOOKS_DONE, RunPhase.COMPLETED, RunPhase.FAILED}:
        # Nothing to do; caller can decide whether to drop or inspect.
        logger.info(
            "advance_run: run %s in terminal or post-book phase %s",
            run.run_id,
            run.phase.value,
        )
        return run

    # Defensive default; should not be hit.
    logger.warning("advance_run: run %s in unexpected phase %s", run.run_id, run.phase.value)
    return run
