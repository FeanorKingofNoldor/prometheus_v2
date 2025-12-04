"""Tests for BasicLongOnlyPortfolioModel.

These tests validate weight construction, caps, and simple risk metrics
using stubbed universe members.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List

from prometheus.portfolio import BasicLongOnlyPortfolioModel, PortfolioConfig
from prometheus.universe.engine import UniverseMember, UniverseStorage


@dataclass
class _StubUniverseStorage(UniverseStorage):  # type: ignore[misc]
    def __init__(self, members: List[UniverseMember]) -> None:  # type: ignore[no-untyped-def]
        # Do not call parent __init__.
        self._members = members

    def get_universe(  # type: ignore[override]
        self,
        as_of_date,
        universe_id,
        entity_type="INSTRUMENT",
        included_only=True,
    ):
        return list(self._members)


class TestBasicLongOnlyPortfolioModel:
    def _make_config(self) -> PortfolioConfig:
        return PortfolioConfig(
            portfolio_id="US_CORE_LONG_EQ",
            strategies=["US_CORE_LONG_EQ"],
            markets=["US_EQ"],
            base_currency="USD",
            risk_model_id="basic-longonly-v1",
            optimizer_type="SIMPLE_LONG_ONLY",
            risk_aversion_lambda=0.0,
            leverage_limit=1.0,
            gross_exposure_limit=1.0,
            per_instrument_max_weight=1.0,
            sector_limits={},
            country_limits={},
            factor_limits={},
            fragility_exposure_limit=0.8,
            turnover_limit=0.5,
            cost_model_id="none",
        )

    def test_weights_normalized_from_scores(self) -> None:
        as_of = date(2024, 1, 5)
        members = [
            UniverseMember(as_of, "U", "INSTRUMENT", "A", True, 1.0, {"sector": "TECH"}),
            UniverseMember(as_of, "U", "INSTRUMENT", "B", True, 3.0, {"sector": "TECH"}),
        ]
        storage = _StubUniverseStorage(members=members)  # type: ignore[arg-type]
        model = BasicLongOnlyPortfolioModel(
            universe_storage=storage,
            config=self._make_config(),
            universe_id="U",
        )

        target = model.build_target_portfolio("US_CORE_LONG_EQ", as_of)

        w_a = target.weights["A"]
        w_b = target.weights["B"]
        # With a generous per-name cap, weights should still be
        # approximately proportional to scores 1:3.
        ratio = w_a / w_b
        assert abs(ratio - (1.0 / 3.0)) < 1e-2
        assert abs(sum(target.weights.values()) - 1.0) < 1e-6

    def test_per_instrument_max_weight_cap(self) -> None:
        as_of = date(2024, 1, 5)
        members = [
            UniverseMember(as_of, "U", "INSTRUMENT", "A", True, 10.0, {"sector": "TECH"}),
            UniverseMember(as_of, "U", "INSTRUMENT", "B", True, 1.0, {"sector": "TECH"}),
        ]
        storage = _StubUniverseStorage(members=members)  # type: ignore[arg-type]
        # Set a low max weight so the higher-score name is capped.
        config = self._make_config().model_copy(update={"per_instrument_max_weight": 0.6})
        model = BasicLongOnlyPortfolioModel(
            universe_storage=storage,
            config=config,
            universe_id="U",
        )

        target = model.build_target_portfolio("US_CORE_LONG_EQ", as_of)

        assert max(target.weights.values()) <= 0.6 + 1e-6
        assert target.constraints_status["per_instrument_max_weight_binding"] is True
        assert abs(sum(target.weights.values()) - 1.0) < 1e-6

    def test_fragility_exposure_metrics(self) -> None:
        as_of = date(2024, 1, 5)
        members = [
            UniverseMember(
                as_of,
                "U",
                "INSTRUMENT",
                "A",
                True,
                1.0,
                {"sector": "TECH", "soft_target_class": "STABLE", "weak_profile": False},
            ),
            UniverseMember(
                as_of,
                "U",
                "INSTRUMENT",
                "B",
                True,
                1.0,
                {"sector": "FIN", "soft_target_class": "FRAGILE", "weak_profile": True},
            ),
        ]
        storage = _StubUniverseStorage(members=members)  # type: ignore[arg-type]
        config = self._make_config().model_copy(update={"fragility_exposure_limit": 0.4})
        model = BasicLongOnlyPortfolioModel(
            universe_storage=storage,
            config=config,
            universe_id="U",
        )

        target = model.build_target_portfolio("US_CORE_LONG_EQ", as_of)

        frag_exposure = target.risk_metrics["fragility_exposure"]
        assert 0.0 < frag_exposure < 1.0
        assert target.constraints_status["fragility_exposure_within_limit"] is (frag_exposure <= 0.4)