"""Prometheus v2 – Fragility Alpha core types.

This module defines in-memory representations for fragility measures and
position templates produced by the Fragility Alpha Engine. The shapes
are aligned with spec 135 but intentionally minimal for the first
implementation iteration.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Dict


class FragilityClass(str, Enum):
    """Discrete fragility classification for an entity.

    The scale is ordered from least to most concerning:

    - NONE: No material fragility detected.
    - WATCHLIST: Elevated risk that merits monitoring.
    - SHORT_CANDIDATE: Attractive candidate for downside/convex
      positioning.
    - CRISIS: Entity appears to be in or on the verge of crisis.
    """

    NONE = "NONE"
    WATCHLIST = "WATCHLIST"
    SHORT_CANDIDATE = "SHORT_CANDIDATE"
    CRISIS = "CRISIS"


@dataclass(frozen=True)
class FragilityMeasure:
    """Scalar fragility score and diagnostics for an entity.

    Attributes:
        entity_type: Logical entity type (e.g. "INSTRUMENT", "ISSUER").
        entity_id: Identifier of the entity.
        as_of_date: Date for which the measure is computed.
        fragility_score: Scalar summary in [0, 1], where higher values
            indicate greater fragility.
        class_label: Discrete fragility class derived from
            ``fragility_score`` and components.
        scenario_losses: Optional mapping from scenario identifiers to
            tail-loss metrics.
        components: Individual component scores used to construct the
            fragility score (e.g. soft_target_score, instability,
            complacent_pricing).
        metadata: Free-form diagnostics and model identifiers.
    """

    entity_type: str
    entity_id: str
    as_of_date: date
    fragility_score: float
    class_label: FragilityClass
    scenario_losses: Dict[str, float]
    components: Dict[str, float]
    metadata: Dict[str, object]


@dataclass(frozen=True)
class PositionTemplate:
    """Lightweight trade template for Portfolio & Risk Engine.

    Attributes:
        entity_id: Logical entity the trade is associated with.
        instrument_id: Instrument identifier to trade.
        as_of_date: Date the template is issued.
        direction: "LONG" or "SHORT".
        kind: Instrument kind (e.g. "EQUITY", "FUTURE", "OPTION").
        notional_hint: Approximate notional or fraction of capital the
            position template suggests.
        horizon_days: Intended holding horizon in trading days.
        rationale: Structured rationale linking back to fragility
            components and classes.
    """

    entity_id: str
    instrument_id: str
    as_of_date: date
    direction: str
    kind: str
    notional_hint: float
    horizon_days: int
    rationale: Dict[str, object]
