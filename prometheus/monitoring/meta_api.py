"""Prometheus v2 – Meta APIs (Kronos Chat + Geo).

This module provides:
- Kronos Chat API for LLM-powered meta-orchestration
- Geo API for world map visualization with country-level data
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Path, Query
from pydantic import BaseModel, Field


kronos_router = APIRouter(prefix="/api/kronos", tags=["kronos"])
geo_router = APIRouter(prefix="/api/geo", tags=["geo"])
meta_router = APIRouter(prefix="/api/meta", tags=["meta"])


# ============================================================================
# Kronos Chat Models
# ============================================================================


class KronosRequest(BaseModel):
    """Request to Kronos chat interface."""

    question: str
    context: Dict[str, Any] = Field(default_factory=dict)


class KronosProposal(BaseModel):
    """Action proposal from Kronos."""

    proposal_id: str
    action_type: str  # backtest, config_change, synthetic_dataset
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    risk_level: str = "LOW"


class KronosResponse(BaseModel):
    """Response from Kronos chat."""

    answer: str
    proposals: List[KronosProposal] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)


# ============================================================================
# Geo Models
# ============================================================================


class CountryStatus(BaseModel):
    """Country-level status for world map."""

    country_code: str
    country_name: str
    stability_index: float
    fragility_risk: str  # LOW, MODERATE, HIGH
    exposure: float = 0.0
    num_positions: int = 0


class CountryDetail(BaseModel):
    """Detailed country information."""

    country_code: str
    country_name: str
    stability_index: float
    fragility_risk: str
    regime: Optional[str] = None
    exposures: Dict[str, float] = Field(default_factory=dict)
    top_positions: List[Dict[str, Any]] = Field(default_factory=list)


# ============================================================================
# Meta Config Models
# ============================================================================


class EngineConfig(BaseModel):
    """Engine configuration snapshot."""

    engine_name: str
    config_version: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    last_updated: str


class EnginePerformance(BaseModel):
    """Engine performance metrics."""

    engine_name: str
    period: str
    metrics: Dict[str, float] = Field(default_factory=dict)
    by_regime: Dict[str, Dict[str, float]] = Field(default_factory=dict)


# ============================================================================
# Kronos Endpoints
# ============================================================================


@kronos_router.post("/chat", response_model=KronosResponse)
async def kronos_chat(request: KronosRequest = Body(...)) -> KronosResponse:
    """Interact with Kronos meta-orchestrator.

    Kronos can explain system behavior, propose experiments, and analyze
    engine performance. It cannot directly execute changes - all actions
    require explicit approval via the Control API.
    """
    # Simple stub response
    question_lower = request.question.lower()

    if "backtest" in question_lower or "test" in question_lower:
        return KronosResponse(
            answer=(
                "Based on recent regime stability and portfolio performance, "
                "I recommend a backtest focusing on the STABLE_EXPANSION regime "
                "over the last 6 months to validate your current strategy parameters."
            ),
            proposals=[
                KronosProposal(
                    proposal_id="prop_001",
                    action_type="backtest",
                    description="6-month STABLE_EXPANSION regime backtest",
                    parameters={
                        "strategy_id": "MAIN",
                        "start_date": "2024-06-01",
                        "end_date": "2024-11-28",
                        "market_ids": ["US_EQ", "EU_EQ"],
                    },
                    risk_level="LOW",
                )
            ],
            sources=["engine_decisions", "decision_outcomes", "regime_history"],
        )

    if "config" in question_lower or "parameter" in question_lower:
        return KronosResponse(
            answer=(
                "Current fragility alpha threshold is 0.075. Recent data suggests "
                "lowering to 0.065 could increase position count by 15% while maintaining "
                "acceptable risk levels."
            ),
            proposals=[
                KronosProposal(
                    proposal_id="prop_002",
                    action_type="config_change",
                    description="Adjust fragility alpha threshold",
                    parameters={
                        "engine_name": "fragility",
                        "config_key": "alpha_threshold",
                        "config_value": 0.065,
                        "reason": "Increase position coverage while maintaining risk",
                    },
                    risk_level="MODERATE",
                )
            ],
            sources=["meta/configs", "fragility_engine_performance"],
        )

    # Default response
    return KronosResponse(
        answer=(
            f"I understand you're asking about: '{request.question}'. "
            "I can help you analyze system performance, propose experiments, "
            "and recommend configuration changes. What specific aspect would you like to explore?"
        ),
        proposals=[],
        sources=[],
    )


# ============================================================================
# Geo Endpoints
# ============================================================================


@geo_router.get("/countries", response_model=List[CountryStatus])
async def get_countries(
    as_of_date: Optional[date] = Query(None, description="As-of date filter")
) -> List[CountryStatus]:
    """Return country-level status for world map visualization."""
    return [
        CountryStatus(
            country_code="US",
            country_name="United States",
            stability_index=0.85,
            fragility_risk="LOW",
            exposure=0.58,
            num_positions=125,
        ),
        CountryStatus(
            country_code="GB",
            country_name="United Kingdom",
            stability_index=0.78,
            fragility_risk="MODERATE",
            exposure=0.12,
            num_positions=22,
        ),
        CountryStatus(
            country_code="DE",
            country_name="Germany",
            stability_index=0.82,
            fragility_risk="LOW",
            exposure=0.08,
            num_positions=18,
        ),
        CountryStatus(
            country_code="JP",
            country_name="Japan",
            stability_index=0.88,
            fragility_risk="LOW",
            exposure=0.15,
            num_positions=35,
        ),
        CountryStatus(
            country_code="CN",
            country_name="China",
            stability_index=0.72,
            fragility_risk="HIGH",
            exposure=0.02,
            num_positions=4,
        ),
    ]


@geo_router.get("/country/{country_code}", response_model=CountryDetail)
async def get_country_detail(
    country_code: str = Path(..., description="ISO country code"),
    as_of_date: Optional[date] = Query(None, description="As-of date"),
) -> CountryDetail:
    """Return detailed country information."""
    return CountryDetail(
        country_code=country_code,
        country_name="United States" if country_code == "US" else country_code,
        stability_index=0.85,
        fragility_risk="LOW",
        regime="STABLE_EXPANSION",
        exposures={
            "equity": 0.52,
            "fixed_income": 0.04,
            "fx": 0.02,
        },
        top_positions=[
            {
                "instrument_id": "AAPL",
                "weight": 0.185,
                "market_value": 925000.0,
            },
            {
                "instrument_id": "MSFT",
                "weight": 0.230,
                "market_value": 1152000.0,
            },
        ],
    )


# ============================================================================
# Meta Config Endpoints
# ============================================================================


@meta_router.get("/configs", response_model=List[EngineConfig])
async def get_configs() -> List[EngineConfig]:
    """Return current engine configurations."""
    return [
        EngineConfig(
            engine_name="regime",
            config_version="v2.1.0",
            parameters={
                "lookback_days": 60,
                "confidence_threshold": 0.75,
                "transition_smoothing": 0.85,
            },
            last_updated="2024-11-15T10:00:00Z",
        ),
        EngineConfig(
            engine_name="stability",
            config_version="v2.0.5",
            parameters={
                "liquidity_weight": 0.35,
                "volatility_weight": 0.35,
                "contagion_weight": 0.30,
            },
            last_updated="2024-11-01T12:00:00Z",
        ),
        EngineConfig(
            engine_name="fragility",
            config_version="v1.8.2",
            parameters={
                "alpha_threshold": 0.075,
                "min_score": 0.65,
                "lookback_days": 21,
            },
            last_updated="2024-10-28T14:00:00Z",
        ),
    ]


@meta_router.get("/performance", response_model=EnginePerformance)
async def get_performance(
    engine_name: str = Query(..., description="Engine name"),
    period: str = Query("30d", description="Period (e.g. 30d, 90d, 1y)"),
) -> EnginePerformance:
    """Return engine performance metrics."""
    return EnginePerformance(
        engine_name=engine_name,
        period=period,
        metrics={
            "accuracy": 0.78,
            "sharpe": 1.42,
            "hit_rate": 0.65,
            "avg_latency_ms": 850,
        },
        by_regime={
            "STABLE_EXPANSION": {
                "accuracy": 0.82,
                "sharpe": 1.68,
                "hit_rate": 0.70,
            },
            "GROWTH_WITH_VOLATILITY": {
                "accuracy": 0.72,
                "sharpe": 1.12,
                "hit_rate": 0.58,
            },
        },
    )
