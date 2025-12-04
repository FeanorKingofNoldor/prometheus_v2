from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict

import numpy as np

from prometheus.regime.engine import RegimeModel
from prometheus.regime.state_change import (
    RegimeChangeRisk,
    RegimeStateChangeForecaster,
)
from prometheus.regime.storage import RegimeStorage
from prometheus.regime.types import RegimeLabel, RegimeState


@dataclass
class _StubStorage(RegimeStorage):  # type: ignore[misc]
    """In-memory stub for RegimeStorage used by the forecaster tests.

    Only the methods required by RegimeStateChangeForecaster are
    implemented; all DB interactions are avoided.
    """

    def __init__(self) -> None:  # type: ignore[no-untyped-def]
        # We don't call RegimeStorage.__init__, so ignore type checker
        # complaints about the missing DatabaseManager.
        self.saved: list[RegimeState] = []
        self.transition_matrix: Dict[str, Dict[str, float]] = {}

    def save_regime(self, state: RegimeState) -> None:  # type: ignore[override]
        self.saved.append(state)

    def get_latest_regime(self, region: str) -> RegimeState | None:  # type: ignore[override]
        for state in reversed(self.saved):
            if state.region == region:
                return state
        return None

    def get_transition_matrix(self, region: str) -> Dict[str, Dict[str, float]]:  # type: ignore[override]
        return self.transition_matrix


class TestRegimeStateChangeForecaster:
    def test_forecast_returns_none_when_no_state(self) -> None:
        storage = _StubStorage()
        forecaster = RegimeStateChangeForecaster(storage=storage)

        risk = forecaster.forecast(region="US", horizon_steps=1)
        assert risk is None

    def test_forecast_uses_transition_matrix_and_current_state(self) -> None:
        # Prepare a simple history: latest regime for US is NEUTRAL.
        state = RegimeState(
            as_of_date=date(2024, 1, 5),
            region="US",
            regime_label=RegimeLabel.NEUTRAL,
            confidence=0.8,
            regime_embedding=None,
            metadata=None,
        )

        storage = _StubStorage()
        storage.saved = [state]

        # Transition matrix: from NEUTRAL, 80% chance to stay NEUTRAL,
        # 20% chance to move to CRISIS. Other rows are left empty and
        # should default to identity.
        storage.transition_matrix = {
            "NEUTRAL": {"NEUTRAL": 0.8, "CRISIS": 0.2}
        }

        forecaster = RegimeStateChangeForecaster(storage=storage)

        risk = forecaster.forecast(region="US", horizon_steps=1)
        assert isinstance(risk, RegimeChangeRisk)
        assert risk.current_regime == RegimeLabel.NEUTRAL
        assert risk.as_of_date == state.as_of_date
        assert risk.horizon_steps == 1

        # With the specified transition matrix, the probability of staying
        # NEUTRAL is 0.8 and of moving to CRISIS is 0.2.
        assert np.isclose(risk.distribution[RegimeLabel.NEUTRAL], 0.8)
        assert np.isclose(risk.distribution[RegimeLabel.CRISIS], 0.2)

        # p_change_any should be 1 - P(stay).
        assert np.isclose(risk.p_change_any, 0.2)

        # All stressed probability mass is in CRISIS for this toy setup.
        assert np.isclose(risk.p_to_crisis_or_risk_off, 0.2)
        assert np.isclose(risk.risk_score, 0.2)

    def test_build_transition_matrix_handles_missing_rows(self) -> None:
        # If the transition matrix is empty, the forecaster should fall
        # back to an identity matrix (no change) and therefore report
        # zero change probability.
        state = RegimeState(
            as_of_date=date(2024, 1, 5),
            region="US",
            regime_label=RegimeLabel.CARRY,
            confidence=0.9,
            regime_embedding=None,
            metadata=None,
        )

        storage = _StubStorage()
        storage.saved = [state]
        storage.transition_matrix = {}

        forecaster = RegimeStateChangeForecaster(storage=storage)
        risk = forecaster.forecast(region="US", horizon_steps=1)
        assert isinstance(risk, RegimeChangeRisk)

        # With identity transitions, probability of change is zero.
        assert np.isclose(risk.p_change_any, 0.0)
        assert np.isclose(risk.p_to_crisis_or_risk_off, 0.0)
        assert np.isclose(risk.risk_score, 0.0)
