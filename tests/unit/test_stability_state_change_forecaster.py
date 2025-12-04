"""Tests for the soft-target (STAB) state-change forecaster.

These tests mirror the structure of the regime state-change forecaster
unit tests, but operate on :class:`SoftTargetClass` and the
``StabilityStorage`` transition matrix helper.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict

import numpy as np

from prometheus.stability.state_change import (
    StabilityStateChangeForecaster,
    SoftTargetChangeRisk,
    _build_transition_matrix,
)
from prometheus.stability.types import SoftTargetClass, SoftTargetState


@dataclass
class _StubStorage:
    """Minimal stub for StabilityStorage.

    We only implement the methods the forecaster relies on:

    - get_latest_state(entity_type, entity_id)
    - get_transition_matrix(entity_type)
    """

    latest_state: SoftTargetState | None = None
    transition_matrix: Dict[str, Dict[str, float]] | None = None

    def get_latest_state(self, entity_type: str, entity_id: str) -> SoftTargetState | None:  # noqa: ARG002
        return self.latest_state

    def get_transition_matrix(self, entity_type: str) -> Dict[str, Dict[str, float]]:  # noqa: ARG002
        return self.transition_matrix or {}


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


class TestStabilityStateChangeForecaster:
    def test_forecast_returns_none_when_no_state(self) -> None:
        storage = _StubStorage(latest_state=None, transition_matrix={})
        forecaster = StabilityStateChangeForecaster(storage=storage)

        result = forecaster.forecast(entity_id="ABC", horizon_steps=1)

        assert result is None

    def test_forecast_uses_transition_matrix_simple(self) -> None:
        # Two-state world: STABLE and BREAKER.
        matrix = {
            SoftTargetClass.STABLE.value: {
                SoftTargetClass.STABLE.value: 0.9,
                SoftTargetClass.BREAKER.value: 0.1,
            },
            SoftTargetClass.BREAKER.value: {
                SoftTargetClass.BREAKER.value: 1.0,
            },
        }

        storage = _StubStorage(latest_state=_make_state(SoftTargetClass.STABLE), transition_matrix=matrix)
        forecaster = StabilityStateChangeForecaster(storage=storage)

        risk = forecaster.forecast(entity_id="ABC", horizon_steps=1)
        assert isinstance(risk, SoftTargetChangeRisk)
        assert risk.current_class is SoftTargetClass.STABLE
        assert risk.horizon_steps == 1

        # In this simple setup, the probability of worsening from STABLE
        # is exactly the probability of jumping to BREAKER.
        assert np.isclose(risk.p_worsen_any, 0.1)
        assert np.isclose(risk.p_to_breaker, 0.1)
        assert np.isclose(risk.p_to_targetable_or_breaker, 0.1)
        assert np.isclose(risk.risk_score, 0.1)

        # The distribution should sum to ~1.
        assert np.isclose(sum(risk.distribution.values()), 1.0)

    def test_forecast_identity_fallback_when_row_missing(self) -> None:
        # Matrix only specifies a row for BREAKER; STABLE should fall back
        # to an identity row (no change), giving zero worsen probability.
        matrix = {
            SoftTargetClass.BREAKER.value: {
                SoftTargetClass.BREAKER.value: 1.0,
            },
        }

        storage = _StubStorage(latest_state=_make_state(SoftTargetClass.STABLE), transition_matrix=matrix)
        forecaster = StabilityStateChangeForecaster(storage=storage)

        risk = forecaster.forecast(entity_id="ABC", horizon_steps=1)
        assert isinstance(risk, SoftTargetChangeRisk)
        assert risk.current_class is SoftTargetClass.STABLE

        # No data for STABLE -> identity row => no worsening or
        # improvement; staying STABLE with probability 1.
        assert np.isclose(risk.p_worsen_any, 0.0)
        assert np.isclose(risk.p_improve_any, 0.0)
        assert np.isclose(risk.risk_score, 0.0)
        assert np.isclose(risk.distribution[SoftTargetClass.STABLE], 1.0)


class TestBuildTransitionMatrix:
    def test_build_transition_matrix_normalizes_and_fills_identity(self) -> None:
        matrix_dict = {
            SoftTargetClass.STABLE.value: {
                SoftTargetClass.WATCH.value: 2.0,
                SoftTargetClass.STABLE.value: 2.0,
            },
            # FRAGILE row omitted on purpose to exercise identity fallback.
        }

        P, index_by_class = _build_transition_matrix(matrix_dict)

        # All rows should sum to 1.
        row_sums = P.sum(axis=1)
        assert np.allclose(row_sums, 1.0)

        stable_idx = index_by_class[SoftTargetClass.STABLE]
        fragile_idx = index_by_class[SoftTargetClass.FRAGILE]

        # For STABLE: 50% STABLE, 50% WATCH.
        assert np.isclose(P[stable_idx, index_by_class[SoftTargetClass.STABLE]], 0.5)
        assert np.isclose(P[stable_idx, index_by_class[SoftTargetClass.WATCH]], 0.5)

        # For FRAGILE (missing row): identity fallback.
        assert np.isclose(P[fragile_idx, fragile_idx], 1.0)

    def test_build_transition_matrix_ignores_unknown_labels(self) -> None:
        matrix_dict = {
            "UNKNOWN": {SoftTargetClass.STABLE.value: 1.0},
            SoftTargetClass.STABLE.value: {"OTHER": 1.0},
        }

        P, _ = _build_transition_matrix(matrix_dict)
        # All rows should still sum to 1 thanks to identity fallback.
        row_sums = P.sum(axis=1)
        assert np.allclose(row_sums, 1.0)
