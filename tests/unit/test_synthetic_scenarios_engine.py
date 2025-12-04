"""Tests for SyntheticScenarioEngine.

These tests validate the behaviour of the historical-window generator
using a small stub DataReader and in-memory ScenarioStorage delegates.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, List

import pandas as pd

from prometheus.core.database import DatabaseManager
from prometheus.synthetic import (
    ScenarioRequest,
    ScenarioSetRef,
    ScenarioStorage,
    ScenarioPathRow,
    SyntheticScenarioEngine,
)


@dataclass
class _StubDBManager(DatabaseManager):  # type: ignore[misc]
    """Stub DatabaseManager that never talks to a real DB.

    The unit tests below patch out all methods that would use the
    connection pools, so we avoid initialising parent state.
    """

    def __init__(self) -> None:  # type: ignore[no-untyped-def]
        # Do not call parent __init__.
        pass


class _StubStorage(ScenarioStorage):  # type: ignore[misc]
    def __init__(self) -> None:  # type: ignore[no-untyped-def]
        # Do not call parent __init__.
        self.created_sets: List[ScenarioSetRef] = []
        self.saved_rows: List[tuple[str, ScenarioPathRow]] = []

    def create_scenario_set(  # type: ignore[override]
        self,
        request: ScenarioRequest,
        created_by: str | None = None,
    ) -> ScenarioSetRef:
        ref = ScenarioSetRef(
            scenario_set_id="SET1",
            name=request.name,
            category=request.category,
            horizon_days=request.horizon_days,
            num_paths=request.num_paths,
        )
        self.created_sets.append(ref)
        return ref

    def save_scenario_paths(  # type: ignore[override]
        self,
        scenario_set_id: str,
        rows: Iterable[ScenarioPathRow],
    ) -> None:
        for row in rows:
            self.saved_rows.append((scenario_set_id, row))


class _StubDataReader:
    """Stub DataReader that serves a fixed price panel.

    We emulate two instruments with deterministic prices over 6 days so
    that windows and returns can be computed without touching the
    database layer.
    """

    def __init__(self) -> None:  # type: ignore[no-untyped-def]
        idx = pd.date_range("2024-01-01", periods=6, freq="D")
        data = {
            "instrument_id": ["A", "A", "A", "A", "A", "A", "B", "B", "B", "B", "B", "B"],
            "trade_date": list(idx) + list(idx),
            "close": [
                100.0,
                101.0,
                102.0,
                103.0,
                104.0,
                105.0,
                200.0,
                202.0,
                204.0,
                206.0,
                208.0,
                210.0,
            ],
        }
        self._df = pd.DataFrame(data)

    def read_prices(self, instrument_ids, start_date, end_date):  # type: ignore[no-untyped-def]
        mask = (
            self._df["instrument_id"].isin(instrument_ids)
            & (self._df["trade_date"] >= pd.Timestamp(start_date))
            & (self._df["trade_date"] <= pd.Timestamp(end_date))
        )
        return self._df[mask].copy()


class TestSyntheticScenarioEngine:
    def test_generate_historical_scenarios_builds_rows(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        # Patch ScenarioStorage and DB access to use stubs.
        stub_db = _StubDBManager()  # type: ignore[arg-type]
        stub_reader = _StubDataReader()

        engine = SyntheticScenarioEngine(db_manager=stub_db, data_reader=stub_reader)  # type: ignore[arg-type]

        # Monkeypatch the internal storage with our stub.
        stub_storage = _StubStorage()  # type: ignore[arg-type]
        monkeypatch.setattr(engine, "_storage", stub_storage)

        request = ScenarioRequest(
            name="TEST_SET",
            description="unit-test historical scenarios",
            category="HISTORICAL",
            horizon_days=3,
            num_paths=2,
            markets=["US_EQ"],
            base_date_start=date(2024, 1, 1),
            base_date_end=date(2024, 1, 6),
        )

        # Monkeypatch _load_instruments_for_markets to avoid DB queries.
        monkeypatch.setattr(
            engine,
            "_load_instruments_for_markets",
            lambda markets: ["A", "B"],
        )

        set_ref = engine.generate_scenario_set(request)

        assert set_ref.name == "TEST_SET"
        assert set_ref.category == "HISTORICAL"
        assert set_ref.horizon_days == 3
        assert set_ref.num_paths == 2

        # We expect some paths to have been recorded.
        assert len(stub_storage.created_sets) == 1
        assert stub_storage.created_sets[0].scenario_set_id == "SET1"
        assert stub_storage.saved_rows, "expected scenario path rows to be saved"

        # Basic sanity: horizon_index should include 0..H.
        horizon_indices = {row.horizon_index for _, row in stub_storage.saved_rows}
        assert {0, 1, 2, 3}.issubset(horizon_indices)

        # Instrument ids should match our stub instruments.
        instrument_ids = {row.instrument_id for _, row in stub_storage.saved_rows}
        assert instrument_ids == {"A", "B"}
