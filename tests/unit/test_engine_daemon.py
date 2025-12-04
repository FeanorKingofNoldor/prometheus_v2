from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from typing import Any, List

import pytest

from prometheus.orchestration import engine_daemon


class _DummyPhase:
    """Minimal stand-in for RunPhase with a ``value`` attribute."""

    def __init__(self, value: str) -> None:
        self.value = value


def _make_dummy_run(run_id: str, phase_value: str = "DATA_READY") -> Any:
    """Create a lightweight object that looks like an EngineRun for logging.

    The daemon only relies on ``run_id``, ``as_of_date``, ``region``, and a
    ``phase`` with a ``value`` attribute when logging state transitions, so a
    ``SimpleNamespace`` is sufficient here.
    """

    return SimpleNamespace(
        run_id=run_id,
        as_of_date=date(2024, 1, 2),
        region="US",
        phase=_DummyPhase(phase_value),
    )


def test_advance_all_once_no_active_runs(monkeypatch) -> None:
    """When there are no active runs, the daemon should be a no-op."""

    dummy_db = object()

    def fake_get_db_manager() -> Any:
        return dummy_db

    def fake_list_active_runs(db_manager: Any) -> List[Any]:  # noqa: ARG001
        return []

    def fake_advance_run(db_manager: Any, run: Any) -> Any:  # noqa: ARG001
        raise AssertionError("advance_run should not be called when there are no active runs")

    monkeypatch.setattr(engine_daemon, "get_db_manager", fake_get_db_manager)
    monkeypatch.setattr(engine_daemon, "list_active_runs", fake_list_active_runs)
    monkeypatch.setattr(engine_daemon, "advance_run", fake_advance_run)

    # Should not raise and should not call advance_run.
    engine_daemon._advance_all_once()


def test_advance_all_once_advances_each_active_run(monkeypatch) -> None:
    """The daemon should call advance_run once for each active run."""

    dummy_db = object()
    runs = [_make_dummy_run("run-1"), _make_dummy_run("run-2")]
    advanced: list[tuple[Any, Any]] = []

    def fake_get_db_manager() -> Any:
        return dummy_db

    def fake_list_active_runs(db_manager: Any) -> List[Any]:
        assert db_manager is dummy_db
        return list(runs)

    def fake_advance_run(db_manager: Any, run: Any) -> Any:
        advanced.append((db_manager, run))
        # Return a new object to exercise the "after" logging path.
        return _make_dummy_run(f"{run.run_id}-after", phase_value="SIGNALS_DONE")

    monkeypatch.setattr(engine_daemon, "get_db_manager", fake_get_db_manager)
    monkeypatch.setattr(engine_daemon, "list_active_runs", fake_list_active_runs)
    monkeypatch.setattr(engine_daemon, "advance_run", fake_advance_run)

    engine_daemon._advance_all_once()

    assert len(advanced) == len(runs)
    for (db_manager, run), original in zip(advanced, runs, strict=True):
        assert db_manager is dummy_db
        assert run is original
