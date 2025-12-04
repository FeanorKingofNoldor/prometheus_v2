"""Prometheus v2: Tests for RegimeEngine infrastructure.

These tests verify that RegimeEngine correctly orchestrates a RegimeModel
and RegimeStorage without embedding any classification logic itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List

from prometheus.regime import (
    RegimeEngine,
    RegimeModel,
    RegimeStorage,
    RegimeLabel,
    RegimeState,
)


@dataclass
class _StubModel(RegimeModel):
    """Stub RegimeModel returning predefined states by (date, region)."""

    states: dict[tuple[date, str], RegimeState]

    def classify(self, as_of_date: date, region: str) -> RegimeState:  # type: ignore[override]
        return self.states[(as_of_date, region)]


class _StubStorage(RegimeStorage):
    """In-memory stub for RegimeStorage.

    Overrides persistence methods to avoid DB access and capture calls.
    """

    def __init__(self) -> None:  # type: ignore[no-untyped-def]
        self.saved: List[RegimeState] = []
        self.transitions: list[tuple[RegimeState, RegimeState]] = []
        self.transition_matrix: dict[str, dict[str, float]] = {
            "NEUTRAL": {"CRISIS": 1.0}
        }

    # RegimeStorage normally expects a DatabaseManager; for tests we
    # override the relevant methods entirely.

    def save_regime(self, state: RegimeState) -> None:  # type: ignore[override]
        self.saved.append(state)

    def get_latest_regime(self, region: str) -> RegimeState | None:  # type: ignore[override]
        for state in reversed(self.saved):
            if state.region == region:
                return state
        return None

    def record_transition(self, previous: RegimeState, current: RegimeState) -> None:  # type: ignore[override]
        self.transitions.append((previous, current))

    def get_history(self, region: str, start_date: date, end_date: date) -> list[RegimeState]:  # type: ignore[override]
        return [
            s
            for s in self.saved
            if s.region == region and start_date <= s.as_of_date <= end_date
        ]

    def get_transition_matrix(self, region: str) -> dict[str, dict[str, float]]:  # type: ignore[override]
        return self.transition_matrix


class TestRegimeEngine:
    """Tests for RegimeEngine orchestration."""

    def test_get_regime_persists_state_and_records_transitions(self) -> None:
        d1 = date(2024, 1, 5)
        d2 = date(2024, 1, 6)

        state1 = RegimeState(
            as_of_date=d1,
            region="US",
            regime_label=RegimeLabel.NEUTRAL,
            confidence=0.7,
            regime_embedding=None,
            metadata=None,
        )
        state2 = RegimeState(
            as_of_date=d2,
            region="US",
            regime_label=RegimeLabel.CRISIS,
            confidence=0.95,
            regime_embedding=None,
            metadata=None,
        )

        model = _StubModel(states={(d1, "US"): state1, (d2, "US"): state2})
        storage = _StubStorage()
        engine = RegimeEngine(model=model, storage=storage)

        # First call: should save state but no transition yet.
        r1 = engine.get_regime(d1, region="US")
        assert r1 == state1
        assert storage.saved == [state1]
        assert storage.transitions == []

        # Second call: label changes from NEUTRAL to CRISIS → transition recorded.
        r2 = engine.get_regime(d2, region="US")
        assert r2 == state2
        assert storage.saved == [state1, state2]
        assert len(storage.transitions) == 1
        prev, curr = storage.transitions[0]
        assert prev == state1
        assert curr == state2

    def test_get_history_delegates_to_storage(self) -> None:
        d1 = date(2024, 1, 5)
        d2 = date(2024, 1, 6)
        d3 = date(2024, 1, 7)

        state_us_1 = RegimeState(d1, "US", RegimeLabel.NEUTRAL, 0.7, None, None)
        state_us_2 = RegimeState(d2, "US", RegimeLabel.CRISIS, 0.9, None, None)
        state_eu = RegimeState(d3, "EU", RegimeLabel.CARRY, 0.8, None, None)

        storage = _StubStorage()
        storage.saved = [state_us_1, state_us_2, state_eu]

        class _NoopModel(RegimeModel):  # type: ignore[misc]
            def classify(self, as_of_date: date, region: str) -> RegimeState:  # type: ignore[override]
                raise RuntimeError("Should not be called in this test")

        engine = RegimeEngine(model=_NoopModel(), storage=storage)

        history = engine.get_history("US", d1, d2)
        assert history == [state_us_1, state_us_2]

    def test_get_transition_matrix_delegates_to_storage(self) -> None:
        storage = _StubStorage()

        class _NoopModel(RegimeModel):  # type: ignore[misc]
            def classify(self, as_of_date: date, region: str) -> RegimeState:  # type: ignore[override]
                raise RuntimeError("Should not be called in this test")

        engine = RegimeEngine(model=_NoopModel(), storage=storage)
        matrix = engine.get_transition_matrix("US")
        assert matrix == {"NEUTRAL": {"CRISIS": 1.0}}
