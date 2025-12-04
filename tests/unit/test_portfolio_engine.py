"""Tests for PortfolioEngine orchestration.

These tests verify that PortfolioEngine calls the underlying model and
storage as expected without embedding optimisation logic itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List

from prometheus.portfolio import PortfolioEngine, PortfolioModel, PortfolioStorage
from prometheus.portfolio.types import TargetPortfolio, RiskReport
from prometheus.universe.engine import UniverseMember


@dataclass
class _StubStorage(PortfolioStorage):  # type: ignore[misc]
    def __init__(self) -> None:  # type: ignore[no-untyped-def]
        # Do not call parent __init__.
        self.saved_args: list[tuple] = []
        self.saved_targets: list[TargetPortfolio] = []
        self.saved_risk_reports: list[RiskReport] = []

    def save_book_targets(  # type: ignore[override]
        self,
        portfolio_id,
        region,
        as_of_date,
        members,
        weights,
        metadata_extra=None,
    ) -> None:
        self.saved_args.append((portfolio_id, region, as_of_date, members, weights, metadata_extra))

    def save_target_portfolio(self, strategy_id: str, target: TargetPortfolio) -> None:  # type: ignore[override]
        self.saved_targets.append(target)

    def save_portfolio_risk_report(self, model_id: str, report: RiskReport) -> None:  # type: ignore[override]
        self.saved_risk_reports.append(report)


@dataclass
class _StubModel(PortfolioModel):  # type: ignore[misc]
    portfolio_id: str
    as_of: date
    target: TargetPortfolio
    members: List[UniverseMember]

    def __post_init__(self) -> None:
        # Expose members for PortfolioEngine persistence.
        self._last_members = self.members

    def build_target_portfolio(self, portfolio_id: str, as_of_date: date) -> TargetPortfolio:  # type: ignore[override]
        assert portfolio_id == self.portfolio_id
        assert as_of_date == self.as_of
        return self.target

    def build_risk_report(  # type: ignore[override]
        self,
        portfolio_id: str,
        as_of_date: date,
        target: TargetPortfolio | None = None,
    ) -> RiskReport | None:
        return None


class TestPortfolioEngine:
    def test_optimize_and_save_persists_targets(self) -> None:
        as_of = date(2024, 1, 5)
        portfolio_id = "US_CORE_LONG_EQ"

        member = UniverseMember(
            as_of_date=as_of,
            universe_id="CORE_EQ_US",
            entity_type="INSTRUMENT",
            entity_id="INST_A",
            included=True,
            score=1.0,
            reasons={"sector": "TECH"},
        )
        target = TargetPortfolio(
            portfolio_id=portfolio_id,
            as_of_date=as_of,
            weights={"INST_A": 1.0},
            expected_return=0.1,
            expected_volatility=0.0,
            risk_metrics={"gross_exposure": 1.0},
            factor_exposures={"TECH": 1.0},
            constraints_status={},
            metadata={"risk_model_id": "basic-longonly-v1"},
        )

        model = _StubModel(portfolio_id=portfolio_id, as_of=as_of, target=target, members=[member])
        storage = _StubStorage()  # type: ignore[arg-type]
        engine = PortfolioEngine(model=model, storage=storage, region="US")

        result = engine.optimize_and_save(portfolio_id, as_of)

        assert result == target
        assert len(storage.saved_args) == 1
        saved_portfolio_id, region, saved_as_of, members, weights, metadata = storage.saved_args[0]
        assert saved_portfolio_id == portfolio_id
        assert region == "US"
        assert saved_as_of == as_of
        assert members == [member]
        assert weights == {"INST_A": 1.0}