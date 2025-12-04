"""Unit tests for the Risk Management Service core modules."""

from __future__ import annotations

from prometheus.risk import (
    StrategyRiskConfig,
    RiskActionType,
    apply_risk_constraints,
    get_strategy_risk_config,
)
from prometheus.risk.constraints import apply_per_name_limit
from prometheus.risk.engine import apply_risk_to_decision


class TestRiskConstraints:
    def test_apply_per_name_limit_within_cap_is_ok(self) -> None:
        cfg = StrategyRiskConfig(strategy_id="TEST", max_abs_weight_per_name=0.05)
        w, reason = apply_per_name_limit(0.04, cfg)
        assert w == 0.04
        assert reason is None

    def test_apply_per_name_limit_caps_excess_weight(self) -> None:
        cfg = StrategyRiskConfig(strategy_id="TEST", max_abs_weight_per_name=0.05)
        w, reason = apply_per_name_limit(0.10, cfg)
        assert abs(w - 0.05) < 1e-9
        assert reason == "CAPPED_PER_NAME"


class TestRiskEngine:
    def test_apply_risk_to_decision_sets_annotations(self) -> None:
        cfg = StrategyRiskConfig(strategy_id="TEST", max_abs_weight_per_name=0.05)
        decision = {"instrument_id": "ABC.US", "target_weight": 0.10}

        updated, result = apply_risk_to_decision(decision, cfg)

        assert updated["target_weight"] == result.adjusted_weight
        assert "risk_action_type" in updated
        assert "risk_reasoning_summary" in updated
        assert result.action_type in {RiskActionType.CAPPED, RiskActionType.OK}


class TestRiskApi:
    def test_apply_risk_constraints_pure_in_memory(self) -> None:
        decisions = [
            {"instrument_id": "AAA.US", "target_weight": 0.10},
            {"instrument_id": "BBB.US", "target_weight": 0.01},
        ]

        out = apply_risk_constraints(decisions, strategy_id="US_EQ_CORE_LONG_EQ", db_manager=None)

        assert len(out) == 2
        for d in out:
            assert "risk_action_type" in d
            assert "risk_reasoning_summary" in d
            assert abs(d["target_weight"]) <= get_strategy_risk_config(
                "US_EQ_CORE_LONG_EQ"
            ).max_abs_weight_per_name + 1e-9
