"""Prometheus v2: Tests for AssessmentEngine orchestration and storage.

These tests verify that AssessmentEngine delegates to an AssessmentModel
and storage implementation correctly, and that InstrumentScoreStorage
emits the expected SQL calls against a stubbed DatabaseManager.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, Mapping

import pandas as pd

from prometheus.assessment import AssessmentEngine, AssessmentModel, InstrumentScore
from prometheus.assessment.storage import InstrumentScoreStorage


# ---------------------------------------------------------------------------
# AssessmentEngine orchestration tests
# ---------------------------------------------------------------------------


@dataclass
class _StubAssessmentModel(AssessmentModel):  # type: ignore[misc]
    """Stub AssessmentModel returning fixed scores for instruments."""

    score_value: float = 0.5

    def score_instruments(  # type: ignore[override]
        self,
        strategy_id: str,
        market_id: str,
        instrument_ids,
        as_of_date: date,
        horizon_days: int,
    ) -> Dict[str, InstrumentScore]:
        scores: Dict[str, InstrumentScore] = {}
        for inst in instrument_ids:
            scores[inst] = InstrumentScore(
                instrument_id=inst,
                as_of_date=as_of_date,
                horizon_days=horizon_days,
                expected_return=self.score_value,
                score=self.score_value,
                confidence=0.8,
                signal_label="BUY",
                alpha_components={"momentum": self.score_value},
                metadata=None,
            )
        return scores


@dataclass
class _StubScoreStorage:
    """In-memory stub for InstrumentScoreStorage-like behaviour."""

    saved: list[tuple[str, str, str, Mapping[str, InstrumentScore]]]

    def __init__(self) -> None:  # type: ignore[no-untyped-def]
        self.saved = []

    def save_scores(  # type: ignore[no-untyped-def]
        self,
        strategy_id: str,
        market_id: str,
        model_id: str,
        scores: Mapping[str, InstrumentScore],
    ) -> None:
        self.saved.append((strategy_id, market_id, model_id, dict(scores)))


class TestAssessmentEngine:
    def test_score_universe_delegates_to_model_and_storage(self) -> None:
        model = _StubAssessmentModel(score_value=0.7)
        storage = _StubScoreStorage()
        engine = AssessmentEngine(model=model, storage=storage, model_id="test-model")

        instruments = ["AAA", "BBB"]
        as_of = date(2024, 3, 4)

        scores = engine.score_universe(
            strategy_id="STRAT1",
            market_id="US_EQ",
            instrument_ids=instruments,
            as_of_date=as_of,
            horizon_days=21,
        )

        assert set(scores.keys()) == set(instruments)
        # Storage should have been called exactly once with the same scores.
        assert len(storage.saved) == 1
        strat_id, market_id, model_id, saved_scores = storage.saved[0]
        assert strat_id == "STRAT1"
        assert market_id == "US_EQ"
        assert model_id == "test-model"
        assert set(saved_scores.keys()) == set(instruments)


# ---------------------------------------------------------------------------
# InstrumentScoreStorage tests with stubbed DB manager
# ---------------------------------------------------------------------------


@dataclass
class _StubConn:
    parent: "_StubDBManager"

    def cursor(self):  # type: ignore[no-untyped-def]
        return _StubCursor(self.parent)

    def commit(self) -> None:  # type: ignore[no-untyped-def]
        # No-op for tests.
        return None

    def __enter__(self):  # type: ignore[no-untyped-def]
        return self

    def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
        return False


@dataclass
class _StubDBManager:
    """Very small stub for DatabaseManager runtime connection.

    It records SQL calls and parameters issued via InstrumentScoreStorage.
    """

    calls: list[tuple[str, tuple]]

    def __init__(self) -> None:  # type: ignore[no-untyped-def]
        self.calls = []

    def get_runtime_connection(self):  # type: ignore[no-untyped-def]
        return _StubConn(self)


class _StubCursor:
    def __init__(self, parent: _StubDBManager) -> None:  # type: ignore[no-untyped-def]
        self._parent = parent

    def execute(self, sql, params):  # type: ignore[no-untyped-def]
        # Record the SQL and params for inspection.
        self._parent.calls.append((sql, params))

    def close(self):  # type: ignore[no-untyped-def]
        return None


class TestInstrumentScoreStorage:
    def test_save_scores_emits_insert_statements(self) -> None:
        db = _StubDBManager()
        storage = InstrumentScoreStorage(db_manager=db)  # type: ignore[arg-type]

        as_of = date(2024, 3, 4)
        scores = {
            "AAA": InstrumentScore(
                instrument_id="AAA",
                as_of_date=as_of,
                horizon_days=21,
                expected_return=0.01,
                score=0.5,
                confidence=0.8,
                signal_label="BUY",
                alpha_components={"momentum": 0.5},
                metadata=None,
            ),
            "BBB": InstrumentScore(
                instrument_id="BBB",
                as_of_date=as_of,
                horizon_days=21,
                expected_return=-0.02,
                score=-0.3,
                confidence=0.7,
                signal_label="SELL",
                alpha_components={"momentum": -0.3},
                metadata=None,
            ),
        }

        storage.save_scores(
            strategy_id="STRAT1",
            market_id="US_EQ",
            model_id="model-1",
            scores=scores,
        )

        # We expect one INSERT per instrument.
        assert len(db.calls) == 2
        seen_instruments: set[str] = set()
        for sql, params in db.calls:
            # Basic shape checks: first param is score_id; next three are
            # strategy_id, market_id, instrument_id.
            assert "INSERT INTO instrument_scores" in sql
            assert params[1] == "STRAT1"
            assert params[2] == "US_EQ"
            inst_id = params[3]
            seen_instruments.add(inst_id)
            assert inst_id in scores
        assert seen_instruments == {"AAA", "BBB"}
