"""Prometheus v2 – Soft-target (STAB) state-change forecaster.

This module provides a simple, Markov-chain based forecaster for
soft-target state-change risk, analogous to the Regime state-change
forecaster. It uses empirical transition frequencies between
:class:`SoftTargetClass` values in the ``soft_target_classes`` table to
estimate multi-step transition probabilities.

The initial v1 implementation focuses on answering questions of the
form:

- Given an entity's current soft-target class, what is the probability
  that it will *worsen* over the next H steps?
- What is the probability of ending up in TARGETABLE or BREAKER?

These summaries can be used as features for risk engines, universe
construction, or Meta/Kronos analysis, without committing to a specific
use-site in the live pipeline yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np

from prometheus.core.logging import get_logger
from prometheus.stability.storage import StabilityStorage
from prometheus.stability.types import SoftTargetClass, SoftTargetState


logger = get_logger(__name__)


_SOFT_TARGET_ORDER: Dict[SoftTargetClass, int] = {
    SoftTargetClass.STABLE: 0,
    SoftTargetClass.WATCH: 1,
    SoftTargetClass.FRAGILE: 2,
    SoftTargetClass.TARGETABLE: 3,
    SoftTargetClass.BREAKER: 4,
}


@dataclass(frozen=True)
class SoftTargetChangeRisk:
    """Summary of soft-target state-change risk for an entity.

    Attributes:
        as_of_date: Date of the latest observed soft-target state.
        entity_type: Logical entity type (e.g. "INSTRUMENT").
        entity_id: Identifier of the entity.
        current_class: Current soft-target class at ``as_of_date``.
        horizon_steps: Forecast horizon in discrete steps.
        p_worsen_any: Probability of ending in a strictly more fragile
            class after ``horizon_steps``.
        p_to_targetable_or_breaker: Probability of being in
            TARGETABLE or BREAKER after ``horizon_steps``.
        p_to_breaker: Probability of being in BREAKER after
            ``horizon_steps``.
        p_improve_any: Probability of ending in a strictly *less*
            fragile class.
        distribution: Full probability distribution over
            :class:`SoftTargetClass` at the horizon.
        risk_score: Convenience scalar in [0, 1], currently equal to
            ``p_to_targetable_or_breaker``.
    """

    as_of_date: "date"
    entity_type: str
    entity_id: str
    current_class: SoftTargetClass
    horizon_steps: int
    p_worsen_any: float
    p_to_targetable_or_breaker: float
    p_to_breaker: float
    p_improve_any: float
    distribution: Dict[SoftTargetClass, float]
    risk_score: float


@dataclass
class StabilityStateChangeForecaster:
    """Markov-chain based forecaster for soft-target state changes.

    This class relies on :class:`StabilityStorage.get_transition_matrix`
    to obtain empirical one-step transition probabilities between
    :class:`SoftTargetClass` values for a given ``entity_type``.

    It does not perform any DB writes and is intended for research
    and integration experiments; the live pipeline can inject this
    forecaster into universe or risk components when appropriate.
    """

    storage: StabilityStorage
    entity_type: str = "INSTRUMENT"

    def forecast(self, entity_id: str, horizon_steps: int = 1) -> SoftTargetChangeRisk | None:
        """Forecast soft-target change risk for an entity over ``horizon_steps``.

        Returns ``None`` if there is no stored soft-target state for the
        entity. In that case, callers should fall back to neutral
        assumptions.
        """

        if horizon_steps <= 0:
            raise ValueError("horizon_steps must be a positive integer")

        current: SoftTargetState | None = self.storage.get_latest_state(
            self.entity_type,
            entity_id,
        )
        if current is None:
            logger.warning(
                "StabilityStateChangeForecaster: no soft-target state for %s:%s",
                self.entity_type,
                entity_id,
            )
            return None

        matrix_dict = self.storage.get_transition_matrix(self.entity_type)
        if not matrix_dict:
            logger.warning(
                "StabilityStateChangeForecaster: empty transition matrix for entity_type=%s",
                self.entity_type,
            )
            return None

        P, index_by_class = _build_transition_matrix(matrix_dict)

        try:
            P_h = np.linalg.matrix_power(P, horizon_steps)
        except ValueError as exc:  # pragma: no cover - defensive
            raise RuntimeError("Failed to compute matrix power for soft-target transitions") from exc

        labels = list(index_by_class.keys())
        current_idx = index_by_class[current.soft_target_class]
        row = P_h[current_idx, :]

        distribution: Dict[SoftTargetClass, float] = {
            label: float(row[index_by_class[label]]) for label in labels
        }

        # Compute worsen/improve probabilities based on the ordinal
        # ordering of SoftTargetClass values.
        current_rank = _SOFT_TARGET_ORDER[current.soft_target_class]
        p_worsen_any = 0.0
        p_improve_any = 0.0
        p_to_targetable_or_breaker = 0.0
        p_to_breaker = 0.0

        for label, prob in distribution.items():
            rank = _SOFT_TARGET_ORDER[label]
            if rank > current_rank:
                p_worsen_any += prob
            elif rank < current_rank:
                p_improve_any += prob

            if label in (SoftTargetClass.TARGETABLE, SoftTargetClass.BREAKER):
                p_to_targetable_or_breaker += prob
            if label == SoftTargetClass.BREAKER:
                p_to_breaker += prob

        # Clamp to [0, 1] defensively.
        def _clamp(x: float) -> float:
            return float(max(0.0, min(1.0, x)))

        p_worsen_any = _clamp(p_worsen_any)
        p_improve_any = _clamp(p_improve_any)
        p_to_targetable_or_breaker = _clamp(p_to_targetable_or_breaker)
        p_to_breaker = _clamp(p_to_breaker)

        risk_score = p_to_targetable_or_breaker

        return SoftTargetChangeRisk(
            as_of_date=current.as_of_date,
            entity_type=current.entity_type,
            entity_id=current.entity_id,
            current_class=current.soft_target_class,
            horizon_steps=horizon_steps,
            p_worsen_any=p_worsen_any,
            p_to_targetable_or_breaker=p_to_targetable_or_breaker,
            p_to_breaker=p_to_breaker,
            p_improve_any=p_improve_any,
            distribution=distribution,
            risk_score=risk_score,
        )


def _build_transition_matrix(
    matrix_dict: Dict[str, Dict[str, float]],
) -> tuple[np.ndarray, Dict[SoftTargetClass, int]]:
    """Convert a nested mapping into a row-stochastic transition matrix.

    The returned matrix ``P`` has shape ``(n_labels, n_labels)`` where
    labels are ordered according to ``list(SoftTargetClass)``. Any labels
    missing from ``matrix_dict`` receive an identity row (no-change).
    """

    labels = list(SoftTargetClass)
    n = len(labels)
    index_by_class: Dict[SoftTargetClass, int] = {label: i for i, label in enumerate(labels)}

    P = np.zeros((n, n), dtype=float)

    for from_label_str, to_mapping in matrix_dict.items():
        try:
            from_label = SoftTargetClass(from_label_str)
        except ValueError:
            logger.warning("Unknown from soft_target_class in transition matrix: %s", from_label_str)
            continue

        i = index_by_class[from_label]
        for to_label_str, prob in to_mapping.items():
            try:
                to_label = SoftTargetClass(to_label_str)
            except ValueError:
                logger.warning("Unknown to soft_target_class in transition matrix: %s", to_label_str)
                continue
            j = index_by_class[to_label]
            P[i, j] = float(prob)

    # Ensure rows are valid probability vectors. For any row that sums to
    # zero (no data), fall back to an identity row.
    row_sums = P.sum(axis=1, keepdims=True)
    zero_mask = row_sums.squeeze() <= 0.0

    if np.any(zero_mask):
        P[zero_mask, :] = 0.0
        for idx in np.where(zero_mask)[0]:
            P[idx, idx] = 1.0
        row_sums = P.sum(axis=1, keepdims=True)

    P /= row_sums

    return P, index_by_class
