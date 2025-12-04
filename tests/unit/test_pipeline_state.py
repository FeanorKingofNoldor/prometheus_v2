"""Prometheus v2: Tests for pipeline engine run state machine."""

from __future__ import annotations

from datetime import date

import pytest

from prometheus.core.config import get_config
from prometheus.core.database import DatabaseManager
from prometheus.pipeline.state import (
    RunPhase,
    EngineRunStateError,
    get_or_create_run,
    update_phase,
)


@pytest.mark.integration
class TestEngineRunState:
    def _db(self) -> DatabaseManager:
        config = get_config()
        return DatabaseManager(config)

    def test_create_and_transition_through_phases(self) -> None:
        db = self._db()
        as_of = date(2024, 3, 4)
        region = "US"

        run = get_or_create_run(db, as_of, region)
        assert run.phase == RunPhase.WAITING_FOR_DATA

        run = update_phase(db, run.run_id, RunPhase.DATA_READY)
        assert run.phase == RunPhase.DATA_READY

        run = update_phase(db, run.run_id, RunPhase.SIGNALS_DONE)
        assert run.phase == RunPhase.SIGNALS_DONE

        run = update_phase(db, run.run_id, RunPhase.UNIVERSES_DONE)
        assert run.phase == RunPhase.UNIVERSES_DONE

        run = update_phase(db, run.run_id, RunPhase.BOOKS_DONE)
        assert run.phase == RunPhase.BOOKS_DONE

        run = update_phase(db, run.run_id, RunPhase.COMPLETED)
        assert run.phase == RunPhase.COMPLETED

        with pytest.raises(EngineRunStateError):
            update_phase(db, run.run_id, RunPhase.DATA_READY)

    def test_invalid_backwards_transition_raises(self) -> None:
        db = self._db()
        as_of = date(2024, 3, 5)
        region = "US"

        run = get_or_create_run(db, as_of, region)
        run = update_phase(db, run.run_id, RunPhase.DATA_READY)

        with pytest.raises(EngineRunStateError):
            update_phase(db, run.run_id, RunPhase.WAITING_FOR_DATA)

        run = update_phase(db, run.run_id, RunPhase.FAILED)
        assert run.phase == RunPhase.FAILED

        with pytest.raises(EngineRunStateError):
            update_phase(db, run.run_id, RunPhase.DATA_READY)
