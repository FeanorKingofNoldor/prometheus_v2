from __future__ import annotations

from datetime import date
from typing import Any, List

import pytest

from prometheus.backtest.campaign import SleeveRunSummary
from prometheus.backtest.config import SleeveConfig
from prometheus.pipeline import tasks


class _DummyDbManager:
    """Lightweight stand-in for DatabaseManager used in wiring tests.

    The concrete type and behaviour of DatabaseManager are irrelevant for
    these tests; we only need an identity object that is passed through to
    helpers.
    """

    pass


def _make_sleeve_configs(strategy_id: str, market_id: str) -> List[SleeveConfig]:
    return [
        SleeveConfig(
            sleeve_id="SLEEVE_1",
            strategy_id=strategy_id,
            market_id=market_id,
            universe_id="U1",
            portfolio_id="P1",
            assessment_strategy_id="ASTRAT",
        ),
        SleeveConfig(
            sleeve_id="SLEEVE_2",
            strategy_id=strategy_id,
            market_id=market_id,
            universe_id="U2",
            portfolio_id="P2",
            assessment_strategy_id="ASTRAT",
        ),
    ]


def test_run_backtest_campaign_and_meta_for_strategy_wires_components(monkeypatch) -> None:
    """The helper should wire campaign + meta and propagate configuration.

    This is a pure wiring test: we monkeypatch the heavy campaign/meta
    helpers to record calls and return lightweight summaries/ids so that no
    real database or engines are required.
    """

    db_manager = _DummyDbManager()
    strategy_id_param = "US_CORE_LONG_EQ"
    market_id_param = "US_EQ"
    start = date(2024, 1, 2)
    end = date(2024, 3, 29)

    recorded: dict[str, Any] = {}

    def fake_build_core_long_sleeves(*, strategy_id: str, market_id: str) -> List[SleeveConfig]:
        assert strategy_id == strategy_id_param
        assert market_id == market_id_param
        return _make_sleeve_configs(strategy_id, market_id)

    def fake_run_backtest_campaign(
        *,
        db_manager: Any,
        calendar: Any,
        market_id: str,
        start_date: date,
        end_date: date,
        sleeve_configs: List[SleeveConfig],
        initial_cash: float,
        apply_risk: bool,
        **kwargs: Any,
    ) -> List[SleeveRunSummary]:
        recorded["campaign_args"] = {
            "db_manager": db_manager,
            "calendar_type": type(calendar),
            "market_id": market_id,
            "start_date": start_date,
            "end_date": end_date,
            "sleeve_configs": sleeve_configs,
            "initial_cash": initial_cash,
            "apply_risk": apply_risk,
        }
        return [
            SleeveRunSummary(
                run_id="run-1",
                sleeve_id=sleeve_configs[0].sleeve_id,
                strategy_id=sleeve_configs[0].strategy_id,
                start_date=start_date,
                end_date=end_date,
                metrics={"cumulative_return": 0.1},
            )
        ]

    def fake_run_meta_for_strategy(
        *,
        db_manager: Any,
        strategy_id: str,
        as_of_date: date,
        top_k: int,
    ) -> str:
        recorded["meta_args"] = {
            "db_manager": db_manager,
            "strategy_id": strategy_id,
            "as_of_date": as_of_date,
            "top_k": top_k,
        }
        return "decision-123"

    monkeypatch.setattr(tasks, "build_core_long_sleeves", fake_build_core_long_sleeves)
    monkeypatch.setattr(tasks, "run_backtest_campaign", fake_run_backtest_campaign)
    monkeypatch.setattr(tasks, "run_meta_for_strategy", fake_run_meta_for_strategy)

    summaries, decision_id = tasks.run_backtest_campaign_and_meta_for_strategy(
        db_manager=db_manager,
        strategy_id=strategy_id_param,
        market_id=market_id_param,
        start_date=start,
        end_date=end,
        top_k=2,
        initial_cash=123_456.0,
        apply_risk=False,
        assessment_backend="context",
        assessment_use_joint_context=True,
        assessment_context_model_id="ctx-model",
        assessment_model_id="assessment-model",
    )

    # The helper should return the campaign summaries and meta decision id.
    assert decision_id == "decision-123"
    assert len(summaries) == 1

    # run_backtest_campaign should see the same db_manager and date range
    # and receive sleeves with the assessment configuration applied.
    campaign_args = recorded["campaign_args"]
    assert campaign_args["db_manager"] is db_manager
    assert campaign_args["market_id"] == market_id_param
    assert campaign_args["start_date"] == start
    assert campaign_args["end_date"] == end
    assert campaign_args["initial_cash"] == 123_456.0
    assert campaign_args["apply_risk"] is False

    sleeve_configs = campaign_args["sleeve_configs"]
    assert {cfg.sleeve_id for cfg in sleeve_configs} == {"SLEEVE_1", "SLEEVE_2"}
    for cfg in sleeve_configs:
        assert cfg.assessment_backend == "context"
        assert cfg.assessment_use_joint_context is True
        assert cfg.assessment_context_model_id == "ctx-model"
        assert cfg.assessment_model_id == "assessment-model"

    # run_meta_for_strategy should be invoked with the same db_manager,
    # strategy_id, end_date, and top_k.
    meta_args = recorded["meta_args"]
    assert meta_args["db_manager"] is db_manager
    assert meta_args["strategy_id"] == strategy_id_param
    assert meta_args["as_of_date"] == end
    assert meta_args["top_k"] == 2


def test_run_backtest_campaign_and_meta_for_strategy_no_sleeves(monkeypatch) -> None:
    """If no sleeve configs are available, the helper should be a no-op."""

    db_manager = _DummyDbManager()
    strategy_id_param = "US_CORE_LONG_EQ"
    market_id_param = "US_EQ"
    start = date(2024, 1, 2)
    end = date(2024, 3, 29)

    def fake_build_core_long_sleeves(*, strategy_id: str, market_id: str) -> List[SleeveConfig]:  # noqa: ARG001
        assert strategy_id == strategy_id_param
        assert market_id == market_id_param
        return []

    def fake_run_backtest_campaign(*args: Any, **kwargs: Any) -> List[SleeveRunSummary]:  # noqa: ARG001
        raise AssertionError("run_backtest_campaign should not be called when there are no sleeves")

    def fake_run_meta_for_strategy(*args: Any, **kwargs: Any) -> str:  # noqa: ARG001
        raise AssertionError("run_meta_for_strategy should not be called when there are no sleeves")

    monkeypatch.setattr(tasks, "build_core_long_sleeves", fake_build_core_long_sleeves)
    monkeypatch.setattr(tasks, "run_backtest_campaign", fake_run_backtest_campaign)
    monkeypatch.setattr(tasks, "run_meta_for_strategy", fake_run_meta_for_strategy)

    summaries, decision_id = tasks.run_backtest_campaign_and_meta_for_strategy(
        db_manager=db_manager,
        strategy_id=strategy_id_param,
        market_id=market_id_param,
        start_date=start,
        end_date=end,
        top_k=2,
        initial_cash=1_000_000.0,
    )

    assert summaries == []
    assert decision_id is None


def test_run_backtest_campaign_and_meta_for_strategy_invalid_date_range() -> None:
    """The helper should raise on an invalid date range."""

    db_manager = _DummyDbManager()

    start = date(2024, 3, 29)
    end = date(2024, 1, 2)

    with pytest.raises(ValueError):
        tasks.run_backtest_campaign_and_meta_for_strategy(
            db_manager=db_manager,
            strategy_id="US_CORE_LONG_EQ",
            market_id="US_EQ",
            start_date=start,
            end_date=end,
        )
