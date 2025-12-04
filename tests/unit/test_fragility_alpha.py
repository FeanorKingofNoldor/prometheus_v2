"""Unit tests for Fragility Alpha storage and basic model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List

import numpy as np
import pytest

from prometheus.fragility import (
    BasicFragilityAlphaModel,
    FragilityAlphaEngine,
    FragilityClass,
    FragilityMeasure,
    FragilityStorage,
    PositionTemplate,
)
from prometheus.stability.types import SoftTargetClass, SoftTargetState


@dataclass
class _StubDBManager:  # type: ignore[misc]
    """Very small stub for DatabaseManager used in unit tests.

    We only provide the context manager interface required by
    FragilityStorage._get_runtime_connection; in these tests we avoid
    touching the real database.
    """

    def get_runtime_connection(self):  # type: ignore[no-untyped-def]
        raise RuntimeError("_StubDBManager should not be used for DB access in unit tests")


@dataclass
class _StubStabilityStorage:  # type: ignore[misc]
    """Stub StabilityStorage returning a fixed SoftTargetState."""

    state: SoftTargetState | None

    def get_latest_state(self, entity_type: str, entity_id: str):  # type: ignore[no-untyped-def]
        return self.state


class TestBasicFragilityAlphaModel:
    def test_score_entity_with_high_soft_target_score(self) -> None:
        as_of = date(2024, 1, 5)
        soft_state = SoftTargetState(
            as_of_date=as_of,
            entity_type="INSTRUMENT",
            entity_id="INST_X",
            soft_target_class=SoftTargetClass.TARGETABLE,
            soft_target_score=80.0,
            weak_profile=True,
            instability=70.0,
            high_fragility=60.0,
            complacent_pricing=50.0,
            metadata=None,
        )

        model = BasicFragilityAlphaModel(
            db_manager=_StubDBManager(),  # type: ignore[arg-type]
            stability_storage=_StubStabilityStorage(state=soft_state),  # type: ignore[arg-type]
            scenario_set_id=None,
            w_soft_target=1.0,
            w_scenario=0.0,
        )

        measure = model.score_entity(as_of, "INSTRUMENT", "INST_X")

        assert 0.0 < measure.fragility_score <= 1.0
        assert measure.class_label in {
            FragilityClass.WATCHLIST,
            FragilityClass.SHORT_CANDIDATE,
            FragilityClass.CRISIS,
        }

        templates = model.suggest_positions(measure, as_of)
        if measure.class_label in {FragilityClass.SHORT_CANDIDATE, FragilityClass.CRISIS}:
            assert templates
            t = templates[0]
            assert t.direction == "SHORT"
            assert t.instrument_id == "INST_X"
        else:
            assert templates == []


class TestFragilityStorageRoundTrip:
    def test_round_trip_measure(self, monkeypatch) -> None:
        # Use an in-memory list to capture executed inserts instead of
        # hitting a real database.
        executed: List[tuple] = []
        last_inserted: Dict[str, object] = {}

        @dataclass
        class _Conn:
            def cursor(self):  # type: ignore[no-untyped-def]
                class _Cursor:
                    def execute(self, sql, params=None):  # type: ignore[no-untyped-def]
                        # Capture INSERT params separately so that
                        # SELECT executions do not overwrite the last
                        # inserted row we want to round-trip.
                        if sql.strip().upper().startswith("INSERT INTO fragility_measures".upper()):
                            (
                                fragility_id,
                                entity_type,
                                entity_id,
                                as_of_date,
                                score,
                                scenario_losses,
                                metadata,
                            ) = params
                            # Unwrap psycopg2 Json objects into plain
                            # Python structures for the round-trip.
                            if hasattr(scenario_losses, "adapted"):
                                scenario_losses = scenario_losses.adapted
                            if hasattr(metadata, "adapted"):
                                metadata = metadata.adapted
                            last_inserted.clear()
                            last_inserted.update(
                                {
                                    "entity_type": entity_type,
                                    "entity_id": entity_id,
                                    "as_of_date": as_of_date,
                                    "score": score,
                                    "scenario_losses": scenario_losses,
                                    "metadata": metadata,
                                }
                            )
                        executed.append(params)

                    def fetchone(self):  # type: ignore[no-untyped-def]
                        # Return the last inserted row as if it were
                        # fetched back from the DB. We ignore
                        # fragility_id and created_at.
                        return (
                            last_inserted["entity_type"],
                            last_inserted["entity_id"],
                            last_inserted["as_of_date"],
                            last_inserted["score"],
                            last_inserted["scenario_losses"],
                            last_inserted["metadata"],
                        )

                    def close(self):  # type: ignore[no-untyped-def]
                        pass

                return _Cursor()

            def commit(self):  # type: ignore[no-untyped-def]
                # No-op for stub connection.
                pass

        @dataclass
        class _StubManager:  # type: ignore[misc]
            def get_runtime_connection(self):  # type: ignore[no-untyped-def]
                class _Ctx:
                    def __enter__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                        return _Conn()

                    def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
                        return False

                return _Ctx()

        storage = FragilityStorage(db_manager=_StubManager())  # type: ignore[arg-type]

        measure = FragilityMeasure(
            entity_type="INSTRUMENT",
            entity_id="INST_Y",
            as_of_date=date(2024, 1, 6),
            fragility_score=0.6,
            class_label=FragilityClass.SHORT_CANDIDATE,
            scenario_losses={"SET": 0.4},
            components={"soft_target_score": 80.0},
            metadata={"class_label": FragilityClass.SHORT_CANDIDATE.value, "components": {"soft_target_score": 80.0}},
        )

        storage.save_measure(measure)
        loaded = storage.get_latest_measure("INSTRUMENT", "INST_Y")

        assert loaded is not None
        assert loaded.entity_id == measure.entity_id
        assert abs(loaded.fragility_score - measure.fragility_score) < 1e-6
        assert loaded.class_label == FragilityClass.SHORT_CANDIDATE
