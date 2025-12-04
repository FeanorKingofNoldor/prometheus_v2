"""Prometheus v2 – Monitoring Status API.

This module provides REST endpoints for the Prometheus C2 UI to query
system status, engine states, and real-time pipeline information.

Currently returns mock/template data to enable UI development. Will be
progressively wired to real engines and runtime DB as they mature.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Mapping

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from prometheus.core.database import get_db_manager
from prometheus.core.logging import get_logger

# Local copy of region→market mapping to avoid importing heavy pipeline tasks
# (which pull in meta/backtest and cause circular imports during test
# collection). Keep in sync with ``prometheus.pipeline.tasks.MARKETS_BY_REGION``.
MARKETS_BY_REGION: Dict[str, tuple[str, ...]] = {
    "US": ("US_EQ",),
    "EU": ("EU_EQ",),
    "ASIA": ("ASIA_EQ",),
}


router = APIRouter(prefix="/api/status", tags=["monitoring"])
logger = get_logger(__name__)


# ============================================================================
# Response Models
# ============================================================================


class SystemOverview(BaseModel):
    """Global system KPIs and alerts."""

    timestamp: datetime = Field(default_factory=datetime.now)
    pnl_today: float = 0.0
    pnl_mtd: float = 0.0
    pnl_ytd: float = 0.0
    max_drawdown: float = 0.0
    net_exposure: float = 0.0
    gross_exposure: float = 0.0
    leverage: float = 0.0
    global_stability_index: float = 0.85
    regimes: List[Dict[str, Any]] = Field(default_factory=list)
    alerts: List[Dict[str, Any]] = Field(default_factory=list)


class PipelineStatus(BaseModel):
    """Per-market pipeline and DAG status."""

    market_id: str
    market_state: str = "SESSION"
    jobs: List[Dict[str, Any]] = Field(default_factory=list)


class RegimeStatus(BaseModel):
    """Regime history and current state."""

    region: str
    as_of_date: Optional[date] = None
    current_regime: str = "STABLE_EXPANSION"
    confidence: float = 0.82
    history: List[Dict[str, Any]] = Field(default_factory=list)


class StabilityStatus(BaseModel):
    """Stability metrics over time."""

    region: str
    as_of_date: Optional[date] = None
    current_index: float = 0.85
    liquidity_component: float = 0.88
    volatility_component: float = 0.82
    contagion_component: float = 0.85
    history: List[Dict[str, Any]] = Field(default_factory=list)


class FragilityStatus(BaseModel):
    """Fragility entities table."""

    region: str
    entity_type: str
    as_of_date: Optional[date] = None
    entities: List[Dict[str, Any]] = Field(default_factory=list)


class FragilityDetail(BaseModel):
    """Detailed fragility info for a single entity."""

    entity_id: str
    entity_type: str
    soft_target_score: float
    fragility_alpha: float
    fragility_class: str
    history: List[Dict[str, Any]] = Field(default_factory=list)
    scenarios: List[Dict[str, Any]] = Field(default_factory=list)
    positions: List[Dict[str, Any]] = Field(default_factory=list)


class AssessmentStatus(BaseModel):
    """Assessment engine output for a strategy."""

    strategy_id: str
    as_of_date: Optional[date] = None
    instruments: List[Dict[str, Any]] = Field(default_factory=list)


class UniverseStatus(BaseModel):
    """Universe membership and scores."""

    strategy_id: str
    as_of_date: Optional[date] = None
    candidates: List[Dict[str, Any]] = Field(default_factory=list)


class PortfolioStatus(BaseModel):
    """Current portfolio state and P&L."""

    portfolio_id: str
    as_of_date: Optional[date] = None
    positions: List[Dict[str, Any]] = Field(default_factory=list)
    pnl: Dict[str, float] = Field(default_factory=dict)
    exposures: Dict[str, Any] = Field(default_factory=dict)


class PortfolioRiskStatus(BaseModel):
    """Portfolio risk metrics and scenarios."""

    portfolio_id: str
    as_of_date: Optional[date] = None
    volatility: float = 0.0
    var_95: float = 0.0
    expected_shortfall: float = 0.0
    max_drawdown: float = 0.0
    scenarios: List[Dict[str, Any]] = Field(default_factory=list)


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/overview", response_model=SystemOverview)
async def get_status_overview() -> SystemOverview:
    """Return global system KPIs and current state.

    This implementation derives aggregate exposure metrics from the
    latest ``portfolio_risk_reports`` rows and a simple global stability
    index from the most recent ``stability_vectors`` snapshot. P&L
    fields remain placeholders until a dedicated P&L aggregation path is
    implemented.
    """

    db_manager = get_db_manager()

    # Aggregate exposure metrics from the latest portfolio_risk_reports
    # snapshot (if any).
    net_exposure = 0.0
    gross_exposure = 0.0
    leverage = 0.0

    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT MAX(as_of_date) FROM portfolio_risk_reports")
            row = cursor.fetchone()
            latest_date = row[0] if row is not None else None
            if latest_date is not None:
                cursor.execute(
                    """
                    SELECT AVG(net_exposure), AVG(gross_exposure), AVG(leverage)
                    FROM portfolio_risk_reports
                    WHERE as_of_date = %s
                    """,
                    (latest_date,),
                )
                exp_row = cursor.fetchone()
                if exp_row is not None:
                    net_exposure = float(exp_row[0] or 0.0)
                    gross_exposure = float(exp_row[1] or 0.0)
                    leverage = float(exp_row[2] or 0.0)
        finally:
            cursor.close()

    # Global stability index: 1 - normalised mean overall_score from
    # stability_vectors (0..100) for the most recent date.
    global_stability_index = 0.0
    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT MAX(as_of_date) FROM stability_vectors")
            row = cursor.fetchone()
            stab_date = row[0] if row is not None else None
            if stab_date is not None:
                cursor.execute(
                    """
                    SELECT AVG(overall_score)
                    FROM stability_vectors
                    WHERE as_of_date = %s
                    """,
                    (stab_date,),
                )
                avg_row = cursor.fetchone()
                if avg_row is not None and avg_row[0] is not None:
                    mean_score = float(avg_row[0])
                    global_stability_index = max(0.0, min(1.0, 1.0 - mean_score / 100.0))
        finally:
            cursor.close()

    # Latest regime snapshot per core region.
    regimes: List[Dict[str, Any]] = []
    regions = ("US", "EU", "ASIA")
    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            for region in regions:
                cursor.execute(
                    """
                    SELECT regime_label, confidence
                    FROM regimes
                    WHERE region = %s
                    ORDER BY as_of_date DESC
                    LIMIT 1
                    """,
                    (region,),
                )
                row = cursor.fetchone()
                if row is None:
                    continue
                regimes.append(
                    {
                        "region": region,
                        "regime_label": str(row[0]),
                        "confidence": float(row[1] or 0.0),
                    }
                )
        finally:
            cursor.close()

    return SystemOverview(
        pnl_today=0.0,
        pnl_mtd=0.0,
        pnl_ytd=0.0,
        max_drawdown=0.0,
        net_exposure=net_exposure,
        gross_exposure=gross_exposure,
        leverage=leverage,
        global_stability_index=global_stability_index,
        regimes=regimes,
        alerts=[],  # Detailed alerting will be added in a later iteration.
    )


@router.get("/pipeline", response_model=PipelineStatus)
async def get_pipeline_status(
    market_id: str = Query(..., description="Market identifier (e.g. US_EQ)")
) -> PipelineStatus:
    """Return per-market pipeline and DAG job status.

    Used by the Live System panel to show current job states.
    """
    return PipelineStatus(
        market_id=market_id,
        market_state="SESSION",
        jobs=[
            {
                "job_name": "regime_compute",
                "last_run_status": "SUCCESS",
                "last_run_time": "2024-11-28T09:30:00Z",
                "latency_ms": 1250,
                "slo_ms": 2000,
                "next_run": "2024-11-28T10:00:00Z",
            },
            {
                "job_name": "stability_compute",
                "last_run_status": "SUCCESS",
                "last_run_time": "2024-11-28T09:31:00Z",
                "latency_ms": 890,
                "slo_ms": 1500,
                "next_run": "2024-11-28T10:01:00Z",
            },
            {
                "job_name": "assessment_run",
                "last_run_status": "RUNNING",
                "last_run_time": "2024-11-28T09:32:00Z",
                "latency_ms": None,
                "slo_ms": 3000,
                "next_run": None,
            },
        ],
    )


@router.get("/regime", response_model=RegimeStatus)
async def get_regime_status(
    region: str = Query("US", description="Region identifier"),
    as_of_date: Optional[date] = Query(None, description="As-of date for historical view"),
) -> RegimeStatus:
    """Return regime state and history for a region from the ``regimes`` table."""

    db_manager = get_db_manager()
    region_norm = region.upper()

    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            if as_of_date is None:
                cursor.execute(
                    "SELECT MAX(as_of_date) FROM regimes WHERE region = %s",
                    (region_norm,),
                )
                row = cursor.fetchone()
                latest_date = row[0] if row is not None else None
                if latest_date is None:
                    return RegimeStatus(region=region_norm, as_of_date=None, current_regime="UNKNOWN", confidence=0.0, history=[])
                end_date = latest_date
            else:
                end_date = as_of_date

            start_date = end_date - timedelta(days=90)

            cursor.execute(
                """
                SELECT as_of_date, regime_label, confidence
                FROM regimes
                WHERE region = %s
                  AND as_of_date BETWEEN %s AND %s
                ORDER BY as_of_date ASC
                """,
                (region_norm, start_date, end_date),
            )
            rows = cursor.fetchall()
        finally:
            cursor.close()

    if not rows:
        return RegimeStatus(
            region=region_norm,
            as_of_date=end_date,
            current_regime="UNKNOWN",
            confidence=0.0,
            history=[],
        )

    history: List[Dict[str, Any]] = []
    for as_of_db, label_db, conf_db in rows:
        history.append(
            {
                "date": as_of_db.isoformat(),
                "regime": str(label_db),
                "confidence": float(conf_db or 0.0),
            }
        )

    last_date, last_label, last_conf = rows[-1]

    return RegimeStatus(
        region=region_norm,
        as_of_date=end_date,
        current_regime=str(last_label),
        confidence=float(last_conf or 0.0),
        history=history,
    )


@router.get("/stability", response_model=StabilityStatus)
async def get_stability_status(
    region: str = Query("US", description="Region identifier"),
    as_of_date: Optional[date] = Query(None, description="As-of date for historical view"),
) -> StabilityStatus:
    """Return stability metrics and history for a region.

    The current implementation aggregates ``stability_vectors`` for
    ``entity_type='INSTRUMENT'`` over instruments whose ``market_id``
    maps to the requested region (via ``MARKETS_BY_REGION``). Metrics are
    based on the mean ``overall_score`` and component scores from the
    basic STAB model.
    """

    db_manager = get_db_manager()
    region_norm = region.upper()

    markets = MARKETS_BY_REGION.get(region_norm)

    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            if as_of_date is None:
                cursor.execute("SELECT MAX(as_of_date) FROM stability_vectors")
                row = cursor.fetchone()
                latest_date = row[0] if row is not None else None
                if latest_date is None:
                    return StabilityStatus(
                        region=region_norm,
                        as_of_date=None,
                        current_index=0.0,
                        liquidity_component=0.0,
                        volatility_component=0.0,
                        contagion_component=0.0,
                        history=[],
                    )
                end_date = latest_date
            else:
                end_date = as_of_date

            start_date = end_date - timedelta(days=90)

            if markets:
                cursor.execute(
                    """
                    SELECT sv.as_of_date,
                           sv.overall_score,
                           sv.vector_components
                    FROM stability_vectors AS sv
                    JOIN instruments AS i ON i.instrument_id = sv.entity_id
                    WHERE sv.entity_type = 'INSTRUMENT'
                      AND i.market_id = ANY(%s)
                      AND sv.as_of_date BETWEEN %s AND %s
                    """,
                    (list(markets), start_date, end_date),
                )
            else:
                cursor.execute(
                    """
                    SELECT as_of_date,
                           overall_score,
                           vector_components
                    FROM stability_vectors
                    WHERE entity_type = 'INSTRUMENT'
                      AND as_of_date BETWEEN %s AND %s
                    """,
                    (start_date, end_date),
                )

            rows = cursor.fetchall()
        finally:
            cursor.close()

    if not rows:
        return StabilityStatus(
            region=region_norm,
            as_of_date=end_date,
            current_index=0.0,
            liquidity_component=0.0,
            volatility_component=0.0,
            contagion_component=0.0,
            history=[],
        )

    # Aggregate by date.
    by_date: Dict[date, Dict[str, Any]] = {}
    for as_of_db, overall_score, components in rows:
        bucket = by_date.setdefault(
            as_of_db,
            {
                "overall_sum": 0.0,
                "count": 0,
                "vol_sum": 0.0,
                "dd_sum": 0.0,
            },
        )
        bucket["overall_sum"] += float(overall_score or 0.0)
        bucket["count"] += 1
        comp = components or {}
        try:
            bucket["vol_sum"] += float(comp.get("vol_score", 0.0) or 0.0)
        except Exception:
            pass
        try:
            bucket["dd_sum"] += float(comp.get("dd_score", 0.0) or 0.0)
        except Exception:
            pass

    # Build time series sorted by date.
    dates_sorted = sorted(by_date.keys())
    history: List[Dict[str, Any]] = []
    current_index = 0.0
    liquidity_component = 0.0
    volatility_component = 0.0
    contagion_component = 0.0

    for d in dates_sorted:
        bucket = by_date[d]
        count = max(bucket["count"], 1)
        mean_overall = bucket["overall_sum"] / count
        mean_vol = bucket["vol_sum"] / count
        mean_dd = bucket["dd_sum"] / count

        idx = max(0.0, min(1.0, 1.0 - mean_overall / 100.0))
        vol_comp = max(0.0, min(1.0, 1.0 - mean_vol / 100.0))
        dd_comp = max(0.0, min(1.0, 1.0 - mean_dd / 100.0))

        history.append(
            {
                "date": d.isoformat(),
                "index": idx,
                "liquidity": 1.0,  # Placeholder until a dedicated liquidity metric exists.
                "volatility": vol_comp,
                "contagion": dd_comp,
            }
        )

        if d == dates_sorted[-1]:
            current_index = idx
            liquidity_component = 1.0
            volatility_component = vol_comp
            contagion_component = dd_comp

    return StabilityStatus(
        region=region_norm,
        as_of_date=end_date,
        current_index=current_index,
        liquidity_component=liquidity_component,
        volatility_component=volatility_component,
        contagion_component=contagion_component,
        history=history,
    )


@router.get("/fragility", response_model=FragilityStatus)
async def get_fragility_status(
    region: str = Query("GLOBAL", description="Region filter"),
    entity_type: str = Query("ANY", description="Entity type filter"),
    as_of_date: Optional[date] = Query(None, description="As-of date"),
) -> FragilityStatus:
    """Return fragility entities table derived from ``fragility_measures``.

    For this iteration we focus on instrument-level fragility
    (``entity_type='INSTRUMENT'``). Region filters are applied by mapping
    regions to market_ids via ``MARKETS_BY_REGION`` and joining to the
    ``instruments`` table.
    """

    db_manager = get_db_manager()
    region_norm = region.upper()

    # We currently expose only instrument-level fragility. Other
    # higher-level entity types (COMPANY, SOVEREIGN, etc.) can be added
    # later by aggregating over issuers/sectors.
    _ = entity_type  # kept for API compatibility; unused for now.

    markets = None
    if region_norm != "GLOBAL":
        markets = MARKETS_BY_REGION.get(region_norm)

    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            if as_of_date is None:
                cursor.execute(
                    "SELECT MAX(as_of_date) FROM fragility_measures WHERE entity_type = 'INSTRUMENT'",
                )
                row = cursor.fetchone()
                eff_date = row[0] if row is not None else None
                if eff_date is None:
                    return FragilityStatus(
                        region=region_norm,
                        entity_type="INSTRUMENT",
                        as_of_date=None,
                        entities=[],
                    )
            else:
                # Use the most recent fragility snapshot up to the
                # requested as_of_date.
                cursor.execute(
                    """
                    SELECT MAX(as_of_date)
                    FROM fragility_measures
                    WHERE entity_type = 'INSTRUMENT'
                      AND as_of_date <= %s
                    """,
                    (as_of_date,),
                )
                row = cursor.fetchone()
                eff_date = row[0] if row is not None else None
                if eff_date is None:
                    return FragilityStatus(
                        region=region_norm,
                        entity_type="INSTRUMENT",
                        as_of_date=as_of_date,
                        entities=[],
                    )

            if markets:
                cursor.execute(
                    """
                    SELECT fm.entity_id,
                           fm.fragility_score,
                           fm.metadata,
                           st.soft_target_score,
                           st.soft_target_class
                    FROM fragility_measures AS fm
                    JOIN instruments AS i
                      ON i.instrument_id = fm.entity_id
                    LEFT JOIN soft_target_classes AS st
                      ON st.entity_type = fm.entity_type
                     AND st.entity_id = fm.entity_id
                     AND st.as_of_date = fm.as_of_date
                    WHERE fm.entity_type = 'INSTRUMENT'
                      AND fm.as_of_date = %s
                      AND i.market_id = ANY(%s)
                    ORDER BY fm.fragility_score DESC
                    LIMIT 200
                    """,
                    (eff_date, list(markets)),
                )
            else:
                cursor.execute(
                    """
                    SELECT fm.entity_id,
                           fm.fragility_score,
                           fm.metadata,
                           st.soft_target_score,
                           st.soft_target_class
                    FROM fragility_measures AS fm
                    LEFT JOIN soft_target_classes AS st
                      ON st.entity_type = fm.entity_type
                     AND st.entity_id = fm.entity_id
                     AND st.as_of_date = fm.as_of_date
                    WHERE fm.entity_type = 'INSTRUMENT'
                      AND fm.as_of_date = %s
                    ORDER BY fm.fragility_score DESC
                    LIMIT 200
                    """,
                    (eff_date,),
                )

            rows = cursor.fetchall()
        finally:
            cursor.close()

    entities: List[Dict[str, Any]] = []
    for inst_id, frag_score, metadata, soft_score, soft_class in rows:
        meta = metadata or {}
        class_str = meta.get("class_label") or "NONE"
        try:
            frag_val = float(frag_score or 0.0)
        except Exception:
            frag_val = 0.0
        try:
            soft_val = float(soft_score or 0.0) / 100.0 if soft_score is not None else 0.0
        except Exception:
            soft_val = 0.0

        entities.append(
            {
                "entity_id": str(inst_id),
                "entity_type": "INSTRUMENT",
                "soft_target_score": soft_val,
                "fragility_alpha": frag_val,
                "fragility_class": str(class_str),
            }
        )

    return FragilityStatus(
        region=region_norm,
        entity_type="INSTRUMENT",
        as_of_date=eff_date,
        entities=entities,
    )


@router.get("/fragility/{entity_id}", response_model=FragilityDetail)
async def get_fragility_detail(
    entity_id: str,
    as_of_date: Optional[date] = Query(None, description="As-of date"),
) -> FragilityDetail:
    """Return detailed fragility info for a specific instrument entity."""

    db_manager = get_db_manager()
    inst_id = str(entity_id)

    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            if as_of_date is None:
                cursor.execute(
                    """
                    SELECT as_of_date, fragility_score, metadata
                    FROM fragility_measures
                    WHERE entity_type = 'INSTRUMENT' AND entity_id = %s
                    ORDER BY as_of_date ASC
                    """,
                    (inst_id,),
                )
            else:
                cursor.execute(
                    """
                    SELECT as_of_date, fragility_score, metadata
                    FROM fragility_measures
                    WHERE entity_type = 'INSTRUMENT' AND entity_id = %s
                      AND as_of_date <= %s
                    ORDER BY as_of_date ASC
                    """,
                    (inst_id, as_of_date),
                )
            rows = cursor.fetchall()
        finally:
            cursor.close()

    if not rows:
        return FragilityDetail(
            entity_id=inst_id,
            entity_type="INSTRUMENT",
            soft_target_score=0.0,
            fragility_alpha=0.0,
            fragility_class="NONE",
            history=[],
            scenarios=[],
            positions=[],
        )

    history: List[Dict[str, Any]] = []
    last_score = 0.0
    last_class = "NONE"

    for as_of_db, frag_score, metadata in rows:
        meta = metadata or {}
        class_str = meta.get("class_label") or "NONE"
        try:
            score_val = float(frag_score or 0.0)
        except Exception:
            score_val = 0.0
        history.append(
            {
                "date": as_of_db.isoformat(),
                "score": score_val,
                "alpha": score_val,
                "class": str(class_str),
            }
        )
        last_score = score_val
        last_class = str(class_str)

    # Scenario-level losses are stored in scenario_losses metadata; we
    # expose them as a lightweight table here.
    last_metadata = rows[-1][2] or {}
    scenario_losses = (last_metadata or {}).get("scenario_losses") or None
    if scenario_losses is None:
        scenario_losses = (last_metadata or {}).get("components", {}).get("scenario_losses", {})
    scenarios: List[Dict[str, Any]] = []
    if isinstance(scenario_losses, Mapping):
        for scen_id, loss in scenario_losses.items():
            try:
                loss_val = float(loss)
            except Exception:
                continue
            scenarios.append({"scenario": str(scen_id), "pnl": -loss_val})

    # Positions: surface simple target weights from book_targets, if any.
    positions: List[Dict[str, Any]] = []
    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT book_id, as_of_date, target_weight
                FROM book_targets
                WHERE entity_type = 'INSTRUMENT' AND entity_id = %s
                ORDER BY as_of_date DESC
                LIMIT 5
                """,
                (inst_id,),
            )
            pos_rows = cursor.fetchall()
        finally:
            cursor.close()

    for book_id, as_of_db, weight in pos_rows:
        try:
            w = float(weight or 0.0)
        except Exception:
            w = 0.0
        positions.append(
            {
                "portfolio_id": str(book_id),
                "position": w,
                "market_value": w,  # Targets are expressed in NAV terms.
            }
        )

    return FragilityDetail(
        entity_id=inst_id,
        entity_type="INSTRUMENT",
        soft_target_score=0.0,  # Soft-target detail can be added later.
        fragility_alpha=last_score,
        fragility_class=last_class,
        history=history,
        scenarios=scenarios,
        positions=positions,
    )


@router.get("/assessment", response_model=AssessmentStatus)
async def get_assessment_status(
    strategy_id: str = Query(..., description="Strategy identifier"),
    as_of_date: Optional[date] = Query(None, description="As-of date"),
) -> AssessmentStatus:
    """Return assessment output for a strategy from ``instrument_scores``."""

    db_manager = get_db_manager()
    strat_id = str(strategy_id)

    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            if as_of_date is None:
                cursor.execute(
                    "SELECT MAX(as_of_date) FROM instrument_scores WHERE strategy_id = %s",
                    (strat_id,),
                )
                row = cursor.fetchone()
                eff_date = row[0] if row is not None else None
                if eff_date is None:
                    return AssessmentStatus(strategy_id=strat_id, as_of_date=None, instruments=[])
            else:
                eff_date = as_of_date

            cursor.execute(
                """
                SELECT instrument_id, expected_return, horizon_days, confidence, alpha_components
                FROM instrument_scores
                WHERE strategy_id = %s AND as_of_date = %s
                ORDER BY expected_return DESC
                LIMIT 200
                """,
                (strat_id, eff_date),
            )
            rows = cursor.fetchall()
        finally:
            cursor.close()

    instruments: List[Dict[str, Any]] = []
    for inst_id, exp_ret, horizon_days, conf, alpha_components in rows:
        alpha = alpha_components or {}
        if not isinstance(alpha, Mapping):
            alpha = {}
        instruments.append(
            {
                "instrument_id": str(inst_id),
                "expected_return": float(exp_ret or 0.0),
                "horizon_days": int(horizon_days or 0),
                "confidence": float(conf or 0.0),
                "alpha_breakdown": alpha,
            }
        )

    return AssessmentStatus(
        strategy_id=strat_id,
        as_of_date=eff_date,
        instruments=instruments,
    )


@router.get("/universe", response_model=UniverseStatus)
async def get_universe_status(
    strategy_id: str = Query(..., description="Strategy identifier"),
    as_of_date: Optional[date] = Query(None, description="As-of date"),
) -> UniverseStatus:
    """Return universe membership and scores from ``universe_members``.

    The mapping from ``strategy_id`` to ``universe_id`` currently follows
    the core long equity convention used in the engine pipeline, where
    ``US_CORE_LONG_EQ`` maps to ``CORE_EQ_US``.
    """

    db_manager = get_db_manager()
    strat_id = str(strategy_id)

    # Derive region and universe_id from strategy_id; fall back to a
    # simple uppercase mapping if the expected pattern is not present.
    parts = strat_id.upper().split("_", 1)
    region_code = parts[0] if parts else strat_id.upper()
    universe_id = f"CORE_EQ_{region_code}"

    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            if as_of_date is None:
                cursor.execute(
                    "SELECT MAX(as_of_date) FROM universe_members WHERE universe_id = %s",
                    (universe_id,),
                )
                row = cursor.fetchone()
                eff_date = row[0] if row is not None else None
                if eff_date is None:
                    return UniverseStatus(strategy_id=strat_id, as_of_date=None, candidates=[])
            else:
                eff_date = as_of_date

            cursor.execute(
                """
                SELECT entity_id, included, score, reasons
                FROM universe_members
                WHERE universe_id = %s
                  AND as_of_date = %s
                  AND entity_type = 'INSTRUMENT'
                ORDER BY included DESC, score DESC, entity_id ASC
                LIMIT 500
                """,
                (universe_id, eff_date),
            )
            rows = cursor.fetchall()
        finally:
            cursor.close()

    candidates: List[Dict[str, Any]] = []
    for entity_id_db, included, score_db, reasons_db in rows:
        reasons = reasons_db or {}
        if not isinstance(reasons, Mapping):
            reasons = {}
        try:
            avg_vol = float(reasons.get("avg_volume_63d", 0.0) or 0.0)
        except Exception:
            avg_vol = 0.0
        try:
            soft_score = float(reasons.get("soft_target_score", 0.0) or 0.0)
        except Exception:
            soft_score = 0.0

        # Simple, bounded proxies for liquidity/quality.
        liquidity_score = max(0.0, min(1.0, avg_vol / 1_000_000.0))
        quality_score = max(0.0, min(1.0, 1.0 - soft_score / 100.0))

        candidates.append(
            {
                "instrument_id": str(entity_id_db),
                "in_universe": bool(included),
                "liquidity_score": liquidity_score,
                "quality_score": quality_score,
            }
        )

    return UniverseStatus(
        strategy_id=strat_id,
        as_of_date=eff_date,
        candidates=candidates,
    )


@router.get("/portfolio", response_model=PortfolioStatus)
async def get_portfolio_status(
    portfolio_id: str = Query(..., description="Portfolio identifier"),
    as_of_date: Optional[date] = Query(None, description="As-of date"),
) -> PortfolioStatus:
    """Return portfolio targets and basic exposures for a portfolio_id.

    Positions are derived from ``target_portfolios`` weights (NAV-based
    targets). Exposures are taken from the latest corresponding
    ``portfolio_risk_reports`` row.
    """

    db_manager = get_db_manager()
    port_id = str(portfolio_id)

    # Determine effective as_of_date from portfolio_risk_reports.
    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            if as_of_date is None:
                cursor.execute(
                    "SELECT MAX(as_of_date) FROM portfolio_risk_reports WHERE portfolio_id = %s",
                    (port_id,),
                )
                row = cursor.fetchone()
                eff_date = row[0] if row is not None else None
                if eff_date is None:
                    return PortfolioStatus(portfolio_id=port_id, as_of_date=None, positions=[], pnl={}, exposures={})
            else:
                eff_date = as_of_date

            # Load target weights from target_portfolios.
            cursor.execute(
                """
                SELECT target_positions
                FROM target_portfolios
                WHERE portfolio_id = %s AND as_of_date = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (port_id, eff_date),
            )
            row = cursor.fetchone()
            target_positions = row[0] if row is not None else None

            # Load risk report row for exposures.
            cursor.execute(
                """
                SELECT risk_metrics, exposures_by_sector, exposures_by_factor, metadata
                FROM portfolio_risk_reports
                WHERE portfolio_id = %s AND as_of_date = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (port_id, eff_date),
            )
            risk_row = cursor.fetchone()
        finally:
            cursor.close()

    # Positions from target weights (NAV=1.0 convention).
    positions: List[Dict[str, Any]] = []
    weights_payload: Mapping[str, Any] | None = None
    if isinstance(target_positions, Mapping):
        weights_payload = target_positions.get("weights")  # type: ignore[index]
    if isinstance(weights_payload, Mapping):
        for inst_id, w in weights_payload.items():
            try:
                weight = float(w or 0.0)
            except Exception:
                continue
            positions.append(
                {
                    "instrument_id": str(inst_id),
                    "quantity": 0.0,
                    "market_value": weight,
                    "weight": weight,
                }
            )

    # Exposures from portfolio_risk_reports.
    exposures: Dict[str, Any] = {}
    if risk_row is not None:
        risk_metrics_db, by_sector, by_factor, metadata = risk_row
        by_sector = by_sector or {}
        if not isinstance(by_sector, Mapping):
            by_sector = {}
        by_factor = by_factor or {}
        if not isinstance(by_factor, Mapping):
            by_factor = {}
        meta = metadata or {}
        if not isinstance(meta, Mapping):
            meta = {}

        exposures["by_sector"] = by_sector
        exposures["by_factor"] = by_factor

        frag_weights = meta.get("fragility_weight_by_class", {})
        if isinstance(frag_weights, Mapping):
            exposures["by_fragility_class"] = frag_weights

    # P&L aggregation is not yet implemented in the engine; return zeros
    # for now.
    pnl = {"today": 0.0, "mtd": 0.0, "ytd": 0.0}

    return PortfolioStatus(
        portfolio_id=port_id,
        as_of_date=eff_date,
        positions=positions,
        pnl=pnl,
        exposures=exposures,
    )


@router.get("/portfolio_risk", response_model=PortfolioRiskStatus)
async def get_portfolio_risk_status(
    portfolio_id: str = Query(..., description="Portfolio identifier"),
    as_of_date: Optional[date] = Query(None, description="As-of date"),
) -> PortfolioRiskStatus:
    """Return portfolio risk metrics from ``portfolio_risk_reports``."""

    db_manager = get_db_manager()
    port_id = str(portfolio_id)

    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            if as_of_date is None:
                cursor.execute(
                    "SELECT MAX(as_of_date) FROM portfolio_risk_reports WHERE portfolio_id = %s",
                    (port_id,),
                )
                row = cursor.fetchone()
                eff_date = row[0] if row is not None else None
                if eff_date is None:
                    return PortfolioRiskStatus(
                        portfolio_id=port_id,
                        as_of_date=None,
                        volatility=0.0,
                        var_95=0.0,
                        expected_shortfall=0.0,
                        max_drawdown=0.0,
                        scenarios=[],
                    )
            else:
                eff_date = as_of_date

            cursor.execute(
                """
                SELECT risk_metrics, scenario_pnl
                FROM portfolio_risk_reports
                WHERE portfolio_id = %s AND as_of_date = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (port_id, eff_date),
            )
            row = cursor.fetchone()
        finally:
            cursor.close()

    if row is None:
        return PortfolioRiskStatus(
            portfolio_id=port_id,
            as_of_date=eff_date,
            volatility=0.0,
            var_95=0.0,
            expected_shortfall=0.0,
            max_drawdown=0.0,
            scenarios=[],
        )

    risk_metrics_db, scenario_pnl_db = row
    rm = risk_metrics_db or {}
    if not isinstance(rm, Mapping):
        rm = {}
    scenario_pnl = scenario_pnl_db or {}
    if not isinstance(scenario_pnl, Mapping):
        scenario_pnl = {}

    volatility = float(rm.get("expected_volatility", 0.0) or 0.0)

    # Prefer scenario-based VaR/ES metrics when available, looking for
    # keys that contain "scenario_var_95" / "scenario_es_95".
    var_95 = 0.0
    es_95 = 0.0
    for key, value in rm.items():
        if "scenario_var_95" in str(key) and var_95 == 0.0:
            try:
                var_95 = float(value or 0.0)
            except Exception:
                continue
        if "scenario_es_95" in str(key) and es_95 == 0.0:
            try:
                es_95 = float(value or 0.0)
            except Exception:
                continue

    max_drawdown = float(rm.get("max_drawdown", 0.0) or 0.0)

    scenarios: List[Dict[str, Any]] = []
    for key, value in scenario_pnl.items():
        try:
            pnl_val = float(value or 0.0)
        except Exception:
            continue
        scenarios.append({"scenario": str(key), "pnl": pnl_val})

    return PortfolioRiskStatus(
        portfolio_id=port_id,
        as_of_date=eff_date,
        volatility=volatility,
        var_95=var_95,
        expected_shortfall=es_95,
        max_drawdown=max_drawdown,
        scenarios=scenarios,
    )


@router.get("/execution", response_model=ExecutionStatus)
async def get_execution_status(
    portfolio_id: str = Query(..., description="Portfolio identifier"),
    mode: Optional[str] = Query(
        None,
        description="Optional execution mode filter (LIVE/PAPER/BACKTEST)",
    ),
    limit_orders: int = Query(50, ge=1, le=500),
    limit_fills: int = Query(50, ge=1, le=500),
) -> ExecutionStatus:
    """Return recent execution activity for a portfolio.

    Orders are read from the ``orders`` table using ``portfolio_id`` and
    optional ``mode``. Fills are joined to orders via ``order_id`` so
    that the same filters can be applied. Positions are taken from the
    most recent ``positions_snapshots`` timestamp for the portfolio.
    """

    db_manager = get_db_manager()
    port_id = str(portfolio_id)
    mode_norm = mode.upper() if mode is not None else None

    orders: List[Dict[str, Any]] = []
    fills: List[Dict[str, Any]] = []
    positions: List[Dict[str, Any]] = []

    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            # Orders
            where_clauses = ["portfolio_id = %s"]
            params: list[object] = [port_id]
            if mode_norm is not None:
                where_clauses.append("mode = %s")
                params.append(mode_norm)
            where_sql = " WHERE " + " AND ".join(where_clauses)
            sql_orders = (
                "SELECT order_id, timestamp, instrument_id, side, order_type, "
                "quantity, status, mode "
                "FROM orders" + where_sql + " ORDER BY timestamp DESC LIMIT %s"
            )
            params.append(limit_orders)
            cursor.execute(sql_orders, tuple(params))
            order_rows = cursor.fetchall()
            for (
                order_id,
                ts,
                instrument_id,
                side,
                order_type,
                quantity,
                status,
                mode_db,
            ) in order_rows:
                orders.append(
                    {
                        "order_id": str(order_id),
                        "timestamp": ts,
                        "instrument_id": str(instrument_id),
                        "side": str(side),
                        "order_type": str(order_type),
                        "quantity": float(quantity or 0.0),
                        "status": str(status),
                        "mode": str(mode_db),
                    }
                )

            # Fills (join to orders to filter by portfolio_id)
            where_clauses_f: List[str] = ["o.portfolio_id = %s"]
            params_f: list[object] = [port_id]
            if mode_norm is not None:
                where_clauses_f.append("f.mode = %s")
                params_f.append(mode_norm)
            where_sql_f = " WHERE " + " AND ".join(where_clauses_f)
            sql_fills = (
                "SELECT f.fill_id, f.timestamp, f.instrument_id, f.side, "
                "f.quantity, f.price, f.commission, f.order_id, f.mode "
                "FROM fills f JOIN orders o ON o.order_id = f.order_id" +
                where_sql_f + " ORDER BY f.timestamp DESC LIMIT %s"
            )
            params_f.append(limit_fills)
            cursor.execute(sql_fills, tuple(params_f))
            fill_rows = cursor.fetchall()
            for (
                fill_id,
                ts_f,
                inst_id_f,
                side_f,
                qty_f,
                price_f,
                comm_f,
                order_id_f,
                mode_f,
            ) in fill_rows:
                fills.append(
                    {
                        "fill_id": str(fill_id),
                        "timestamp": ts_f,
                        "instrument_id": str(inst_id_f),
                        "side": str(side_f),
                        "quantity": float(qty_f or 0.0),
                        "price": float(price_f or 0.0),
                        "commission": float(comm_f or 0.0),
                        "order_id": str(order_id_f),
                        "mode": str(mode_f),
                    }
                )

            # Positions: latest snapshot timestamp for portfolio.
            cursor.execute(
                """
                SELECT MAX(timestamp) FROM positions_snapshots
                WHERE portfolio_id = %s
                """,
                (port_id,),
            )
            row_ts = cursor.fetchone()
            latest_ts = row_ts[0] if row_ts is not None else None
            if latest_ts is not None:
                cursor.execute(
                    """
                    SELECT instrument_id, quantity, avg_cost, market_value,
                           unrealized_pnl, mode
                    FROM positions_snapshots
                    WHERE portfolio_id = %s AND timestamp = %s
                    ORDER BY instrument_id
                    """,
                    (port_id, latest_ts),
                )
                pos_rows = cursor.fetchall()
                for (
                    inst_id_p,
                    qty_p,
                    avg_cost_p,
                    mv_p,
                    upnl_p,
                    mode_p,
                ) in pos_rows:
                    positions.append(
                        {
                            "instrument_id": str(inst_id_p),
                            "quantity": float(qty_p or 0.0),
                            "avg_cost": float(avg_cost_p or 0.0),
                            "market_value": float(mv_p or 0.0),
                            "unrealized_pnl": float(upnl_p or 0.0),
                            "mode": str(mode_p),
                        }
                    )
        finally:
            cursor.close()

    return ExecutionStatus(
        portfolio_id=port_id,
        mode=mode_norm,
        orders=orders,
        fills=fills,
        positions=positions,
    )


@router.get("/risk_actions", response_model=RiskActionsStatus)
async def get_risk_actions_status(
    strategy_id: str = Query(..., description="Strategy identifier"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of rows"),
) -> RiskActionsStatus:
    """Return recent ``risk_actions`` rows for a strategy.

    This endpoint mirrors the behaviour of the ``show_risk_actions`` CLI
    but returns structured JSON for the UI. It is primarily useful for
    inspecting how the Risk Management Service (and, in future, any
    execution-time risk wrappers) modified proposed positions.
    """

    db_manager = get_db_manager()
    strat_id = str(strategy_id)

    sql = """
        SELECT created_at, instrument_id, decision_id, action_type, details_json
        FROM risk_actions
        WHERE strategy_id = %s
        ORDER BY created_at DESC
        LIMIT %s
    """

    actions: List[RiskActionRow] = []
    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (strat_id, limit))
            rows = cursor.fetchall()
        finally:
            cursor.close()

    for created_at, instrument_id, decision_id, action_type, details in rows:
        details = details or {}
        if not isinstance(details, Mapping):
            details = {}
        orig = details.get("original_weight")
        adj = details.get("adjusted_weight")
        reason = details.get("reason")
        try:
            orig_f = float(orig) if orig is not None else None
        except Exception:
            orig_f = None
        try:
            adj_f = float(adj) if adj is not None else None
        except Exception:
            adj_f = None
        actions.append(
            RiskActionRow(
                created_at=created_at,
                instrument_id=str(instrument_id) if instrument_id is not None else None,
                decision_id=str(decision_id) if decision_id is not None else None,
                action_type=str(action_type),
                original_weight=orig_f,
                adjusted_weight=adj_f,
                reason=str(reason) if reason is not None else None,
            )
        )

    return RiskActionsStatus(strategy_id=strat_id, actions=actions)
