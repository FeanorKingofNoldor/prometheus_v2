"""Prometheus v2 – Stability / Soft Target Engine types.

This module defines core enums and dataclasses used by the Stability
(STAB) engine. These types are the in-memory representations of
stability vectors and soft-target classifications persisted in the
runtime database.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Optional

from prometheus.core.types import MetadataDict


class SoftTargetClass(str, Enum):
    """Discrete soft-target classification for an entity.

    The scale is ordered from most stable to most dangerous:

    - STABLE: No material vulnerability.
    - WATCH: Early signs of instability or deterioration.
    - FRAGILE: Elevated risk that warrants caution.
    - TARGETABLE: High vulnerability; attractive soft target.
    - BREAKER: Extreme vulnerability; potential system breaker.
    """

    STABLE = "STABLE"
    WATCH = "WATCH"
    FRAGILE = "FRAGILE"
    TARGETABLE = "TARGETABLE"
    BREAKER = "BREAKER"


@dataclass(frozen=True)
class StabilityVector:
    """Continuous stability / fragility representation for an entity.

    Attributes:
        as_of_date: Date for which the vector was computed.
        entity_type: Logical entity type (e.g. "INSTRUMENT", "ISSUER", "MARKET").
        entity_id: Identifier of the entity.
        components: Named component scores (e.g. vol_score, dd_score,
            trend_score), typically scaled to [0, 100] where higher
            values indicate greater fragility.
        overall_score: Aggregated stability/fragility score in [0, 100],
            where 0 is very stable and 100 extremely fragile.
        metadata: Optional additional diagnostics.
    """

    as_of_date: date
    entity_type: str
    entity_id: str
    components: dict[str, float]
    overall_score: float
    metadata: Optional[MetadataDict] = None


@dataclass(frozen=True)
class SoftTargetState:
    """Soft-target classification and diagnostics for an entity.

    Attributes:
        as_of_date: Date for which the state was inferred.
        entity_type: Logical entity type.
        entity_id: Identifier of the entity.
        soft_target_class: Discrete soft-target classification.
        soft_target_score: Soft Target Index in [0, 100].
        weak_profile: Whether structural/profile weaknesses contributed.
        instability: Instability component (e.g. volatility-driven).
        high_fragility: Fragility component (e.g. drawdown, leverage).
        complacent_pricing: Component capturing pricing complacency.
        metadata: Optional structured metadata with additional context.
    """

    as_of_date: date
    entity_type: str
    entity_id: str
    soft_target_class: SoftTargetClass
    soft_target_score: float
    weak_profile: bool
    instability: float
    high_fragility: float
    complacent_pricing: float
    metadata: Optional[MetadataDict] = None
