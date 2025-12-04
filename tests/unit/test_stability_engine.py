"""Prometheus v2: Tests for StabilityEngine infrastructure.

These tests verify that StabilityEngine correctly orchestrates a
StabilityModel and StabilityStorage without embedding any scoring logic
itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List

from prometheus.stability import (
    StabilityEngine,
    StabilityModel,
    StabilityStorage,
    SoftTargetClass,
    StabilityVector,
    SoftTargetState,
)


@dataclass
class _StubModel(StabilityModel):
    """Stub StabilityModel returning predefined outputs by (date, entity)."""

    vectors: dict[tuple[date, str], StabilityVector]
    states: dict[tuple[date, str], SoftTargetState]

    def score(  # type: ignore[override]
        self,
        as_of_date: date,
        entity_type: str,
        entity_id: str,
    ) -> tuple[StabilityVector, SoftTargetState]:
        key = (as_of_date, entity_id)
        return self.vectors[key], self.states[key]


class _StubStorage(StabilityStorage):
    """In-memory stub for StabilityStorage.

    Overrides persistence methods to avoid DB access and capture calls.
    """

    def __init__(self) -> None:  # type: ignore[no-untyped-def]
        self.vectors: List[StabilityVector] = []
        self.states: List[SoftTargetState] = []

    def save_stability_vector(self, vector: StabilityVector) -> None:  # type: ignore[override]
        self.vectors.append(vector)

    def save_soft_target(self, state: SoftTargetState) -> None:  # type: ignore[override]
        self.states.append(state)

    def get_latest_state(self, entity_type: str, entity_id: str) -> SoftTargetState | None:  # type: ignore[override]
        for state in reversed(self.states):
            if state.entity_type == entity_type and state.entity_id == entity_id:
                return state
        return None

    def get_history(  # type: ignore[override]
        self,
        entity_type: str,
        entity_id: str,
        start_date: date,
        end_date: date,
    ) -> list[SoftTargetState]:
        return [
            s
            for s in self.states
            if s.entity_type == entity_type
            and s.entity_id == entity_id
            and start_date <= s.as_of_date <= end_date
        ]


class TestStabilityEngine:
    """Tests for StabilityEngine orchestration."""

    def test_score_entity_persists_vector_and_state(self) -> None:
        d1 = date(2024, 1, 5)

        vector = StabilityVector(
            as_of_date=d1,
            entity_type="INSTRUMENT",
            entity_id="TEST_STAB",
            components={"vol_score": 10.0, "dd_score": 20.0, "trend_score": 5.0},
            overall_score=25.0,
            metadata=None,
        )
        state = SoftTargetState(
            as_of_date=d1,
            entity_type="INSTRUMENT",
            entity_id="TEST_STAB",
            soft_target_class=SoftTargetClass.WATCH,
            soft_target_score=25.0,
            weak_profile=False,
            instability=10.0,
            high_fragility=20.0,
            complacent_pricing=5.0,
            metadata=None,
        )

        model = _StubModel(vectors={(d1, "TEST_STAB"): vector}, states={(d1, "TEST_STAB"): state})
        storage = _StubStorage()
        engine = StabilityEngine(model=model, storage=storage)

        result = engine.score_entity(d1, "INSTRUMENT", "TEST_STAB")

        assert result == state
        assert storage.vectors == [vector]
        assert storage.states == [state]

    def test_get_latest_state_and_history_delegate_to_storage(self) -> None:
        d1 = date(2024, 1, 5)
        d2 = date(2024, 1, 6)
        d3 = date(2024, 1, 7)

        state1 = SoftTargetState(d1, "INSTRUMENT", "TEST_STAB", SoftTargetClass.STABLE, 10.0, False, 1.0, 2.0, 3.0, None)
        state2 = SoftTargetState(d2, "INSTRUMENT", "TEST_STAB", SoftTargetClass.WATCH, 30.0, False, 2.0, 3.0, 4.0, None)
        state3 = SoftTargetState(d3, "INSTRUMENT", "OTHER", SoftTargetClass.FRAGILE, 50.0, False, 3.0, 4.0, 5.0, None)

        storage = _StubStorage()
        storage.states = [state1, state2, state3]

        class _NoopModel(StabilityModel):  # type: ignore[misc]
            def score(self, as_of_date: date, entity_type: str, entity_id: str):  # type: ignore[override]
                raise RuntimeError("Should not be called in this test")

        engine = StabilityEngine(model=_NoopModel(), storage=storage)

        latest = engine.get_latest_state("INSTRUMENT", "TEST_STAB")
        assert latest == state2

        history = engine.get_history("INSTRUMENT", "TEST_STAB", d1, d2)
        assert history == [state1, state2]
