"""Prometheus v2: Tests for UniverseEngine infrastructure.

These tests verify that UniverseEngine correctly orchestrates a
UniverseModel and UniverseStorage without embedding any selection logic
itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List

from prometheus.universe import UniverseEngine, UniverseModel, UniverseStorage, UniverseMember


@dataclass
class _StubModel(UniverseModel):
    """Stub UniverseModel returning predefined members by (date, universe)."""

    members: dict[tuple[date, str], list[UniverseMember]]

    def build_universe(self, as_of_date: date, universe_id: str) -> list[UniverseMember]:  # type: ignore[override]
        return self.members[(as_of_date, universe_id)]


class _StubStorage(UniverseStorage):
    """In-memory stub for UniverseStorage.

    Overrides persistence methods to avoid DB access and capture calls.
    """

    def __init__(self) -> None:  # type: ignore[no-untyped-def]
        self.saved: List[UniverseMember] = []

    def save_members(self, members):  # type: ignore[override, no-untyped-def]
        self.saved.extend(members)

    def get_universe(self, as_of_date, universe_id, entity_type="INSTRUMENT", included_only=True):  # type: ignore[override, no-untyped-def]
        return [m for m in self.saved if m.as_of_date == as_of_date and m.universe_id == universe_id]


class TestUniverseEngine:
    """Tests for UniverseEngine orchestration."""

    def test_build_and_save_persists_members(self) -> None:
        as_of = date(2024, 1, 5)

        m1 = UniverseMember(as_of, "CORE_EQ", "INSTRUMENT", "A", True, 10.0, {"reason": "ok"})
        m2 = UniverseMember(as_of, "CORE_EQ", "INSTRUMENT", "B", False, 0.0, {"reason": "fragile"})

        model = _StubModel(members={(as_of, "CORE_EQ"): [m1, m2]})
        storage = _StubStorage()  # type: ignore[arg-type]
        engine = UniverseEngine(model=model, storage=storage)

        result = engine.build_and_save(as_of, "CORE_EQ")

        assert result == [m1, m2]
        assert storage.saved == [m1, m2]

    def test_get_universe_delegates_to_storage(self) -> None:
        as_of = date(2024, 1, 5)

        storage = _StubStorage()  # type: ignore[arg-type]
        storage.saved = [
            UniverseMember(as_of, "CORE_EQ", "INSTRUMENT", "A", True, 10.0, {}),
            UniverseMember(as_of, "CORE_EQ", "INSTRUMENT", "B", False, 0.0, {}),
        ]

        class _NoopModel(UniverseModel):  # type: ignore[misc]
            def build_universe(self, as_of_date: date, universe_id: str):  # type: ignore[override]
                raise RuntimeError("Should not be called in this test")

        engine = UniverseEngine(model=_NoopModel(), storage=storage)

        universe = engine.get_universe(as_of, "CORE_EQ")
        assert universe == storage.saved
