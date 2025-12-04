"""Tests for the soft-target (STAB) risk backfill helper.

These tests focus on the pure computation function
``_compute_soft_target_risk_series`` used by the
``backfill_stability_change_risk`` CLI, using an in-memory stub storage
that avoids any database access.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Sequence

import numpy as np

from prometheus.scripts.backfill_stability_change_risk import (
    SoftTargetRiskPoint,
    _compute_soft_target_risk_series,
)
from prometheus.stability.types import SoftTargetClass, SoftTargetState


@dataclass
class _StubStorage:
    """In-memory stub for StabilityStorage used by the backfill tests.

    Only the methods required by ``_compute_soft_target_risk_series`` are
    implemented.
    """

    transition_matrix: Dict[str, Dict[str, float]]
    histories: Dict[tuple[str, str], List[SoftTargetState]]

    def get_transition_matrix(self, entity_type: str) -> Dict[str, Dict[str, float]]:  # noqa: ARG002
        return self.transition_matrix

    def get_history(
        self,
        entity_type: str,
        entity_id: str,
        start_date: date,  # noqa: ARG002
        end_date: date,  # noqa: ARG002
    ) -> List[SoftTargetState]:
        return self.histories.get((entity_type, entity_id), [])


def _make_state(label: SoftTargetClass) -> SoftTargetState:
    return SoftTargetState(
        as_of_date=date(2024, 1, 1),
        entity_type="INSTRUMENT",
        entity_id="ABC",
        soft_target_class=label,
        soft_target_score=50.0,
        weak_profile=False,
        instability=0.5,
        high_fragility=0.5,
        complacent_pricing=0.5,
    )


class TestComputeSoftTargetRiskSeries:
    def test_simple_two_state_world_matches_expectations(self) -> None:
        # Two-state world with STABLE and BREAKER.
        matrix = {
            SoftTargetClass.STABLE.value: {
                SoftTargetClass.STABLE.value: 0.8,
                SoftTargetClass.BREAKER.value: 0.2,
            },
            SoftTargetClass.BREAKER.value: {
                SoftTargetClass.BREAKER.value: 1.0,
            },
        }

        histories: Dict[tuple[str, str], List[SoftTargetState]] = {
            ("INSTRUMENT", "ABC"): [_make_state(SoftTargetClass.STABLE)],
        }

        storage = _StubStorage(transition_matrix=matrix, histories=histories)

        points = _compute_soft_target_risk_series(
            storage,
            entity_type="INSTRUMENT",
            entity_ids=["ABC"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 1),
            horizon_steps=1,
        )

        assert len(points) == 1
        p = points[0]
        assert isinstance(p, SoftTargetRiskPoint)
        assert p.current_soft_target_class == SoftTargetClass.STABLE.value

        # From STABLE, 80% chance to stay STABLE and 20% to go to BREAKER,
        # so worsening/targetable/breaker risk is 0.2.
        assert np.isclose(p.p_worsen_any, 0.2)
        assert np.isclose(p.p_to_targetable_or_breaker, 0.2)
        assert np.isclose(p.p_to_breaker, 0.2)
        assert np.isclose(p.stability_risk_score, 0.2)

    def test_identity_behaviour_when_transition_matrix_empty(self) -> None:
        # When the transition matrix is empty, _build_transition_matrix
        # effectively falls back to identity transitions. This should
        # result in zero worsening/improvement probabilities.
        matrix: Dict[str, Dict[str, float]] = {}
        histories: Dict[tuple[str, str], List[SoftTargetState]] = {
            ("INSTRUMENT", "ABC"): [_make_state(SoftTargetClass.STABLE)],
        }

        storage = _StubStorage(transition_matrix=matrix, histories=histories)

        points = _compute_soft_target_risk_series(
            storage,
            entity_type="INSTRUMENT",
            entity_ids=["ABC"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 1),
            horizon_steps=1,
        )

        assert len(points) == 1
        p = points[0]
        assert np.isclose(p.p_worsen_any, 0.0)
        assert np.isclose(p.p_improve_any, 0.0)
        assert np.isclose(p.stability_risk_score, 0.0)
