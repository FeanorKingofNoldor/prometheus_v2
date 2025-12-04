"""Prometheus v2: Tests for BasicUniverseModel with Assessment scores.

These tests use stubbed DB and data reader implementations to validate
that BasicUniverseModel can optionally incorporate Assessment scores
(from ``instrument_scores``) into the universe ranking while preserving
existing liquidity/STAB behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
import pytest

from prometheus.core.time import TradingCalendar
from prometheus.universe.engine import BasicUniverseModel, UniverseMember
from prometheus.stability.types import SoftTargetClass, SoftTargetState
from prometheus.stability.storage import StabilityStorage


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


@dataclass
class _StubConn:
    parent: "_StubDBManager"

    def cursor(self):  # type: ignore[no-untyped-def]
        return _StubCursor(self.parent)

    def __enter__(self):  # type: ignore[no-untyped-def]
        return self

    def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
        return False


@dataclass
class _StubDBManager:
    """Stub for DatabaseManager used by BasicUniverseModel.

    It returns in-memory instruments and instrument_scores rows.
    """

    instruments: List[Tuple[str, str, str]]  # (instrument_id, issuer_id, market_id)
    assessment_rows: List[Tuple[str, float]]

    def get_runtime_connection(self):  # type: ignore[no-untyped-def]
        return _StubConn(self)


class _StubCursor:
    def __init__(self, parent: _StubDBManager) -> None:  # type: ignore[no-untyped-def]
        self._parent = parent
        self._last_query: str | None = None
        self._last_params: tuple[Any, ...] | None = None

    def execute(self, sql, params):  # type: ignore[no-untyped-def]
        self._last_query = sql
        self._last_params = params

    def fetchall(self):  # type: ignore[no-untyped-def]
        if "FROM instruments" in (self._last_query or ""):
            # Return instrument_id, issuer_id, sector, market_id for all
            # stubbed instruments. The third tuple element in
            # ``self._parent.instruments`` is treated as a synthetic sector
            # label for testing purposes; we use a fixed market_id ("US_EQ")
            # for all rows as the tests do not depend on market splits.
            return [
                (inst, issuer, sector, "US_EQ")
                for inst, issuer, sector in self._parent.instruments
            ]
        if "FROM instrument_scores" in (self._last_query or ""):
            # Return instrument_id, score rows.
            return list(self._parent.assessment_rows)
        return []

    def close(self):  # type: ignore[no-untyped-def]
        return None


@dataclass
class _StubDataReader:
    df: pd.DataFrame

    def read_prices(self, instrument_ids, start_date, end_date):  # type: ignore[no-untyped-def]
        # BasicUniverseModel relies only on close/volume columns; we can
        # return the same window for all instruments.
        return self.df


class _StubStabilityStorage(StabilityStorage):  # type: ignore[misc]
    """Stub StabilityStorage returning a benign SoftTargetState.

    Avoids DB access and returns a fixed state per instrument.
    """

    def __init__(self) -> None:  # type: ignore[no-untyped-def]
        # Do not call parent __init__.
        pass

    def get_latest_state(self, entity_type: str, entity_id: str):  # type: ignore[override, no-untyped-def]
        return SoftTargetState(
            as_of_date=date(2024, 3, 4),
            entity_type=entity_type,
            entity_id=entity_id,
            soft_target_class=SoftTargetClass.STABLE,
            soft_target_score=10.0,
            weak_profile=False,
            instability=10.0,
            high_fragility=5.0,
            complacent_pricing=0.0,
            metadata=None,
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class _StubLambdaProvider:
    """Simple stub for lambda_score_provider used in tests.

    Returns a fixed lambda score regardless of the cluster inputs so
    that we can easily reason about the impact on scores.

    Also exposes ``experiment_id`` and ``score_column`` attributes so we
    can verify that BasicUniverseModel records them in diagnostics.
    """

    def __init__(self, value: float) -> None:  # type: ignore[no-untyped-def]
        self.value = value
        self.experiment_id = "EXP_TEST"
        self.score_column = "lambda_hat"

    def get_cluster_score(  # type: ignore[no-untyped-def]
        self,
        as_of_date,
        market_id,
        sector,
        soft_target_class,
    ) -> float:
        return self.value


@dataclass
class _StubStabRisk:
    risk_score: float
    p_worsen_any: float
    p_to_targetable_or_breaker: float


class _StubStabRiskForecaster:
    """Stub for stability_state_change_forecaster used in tests.

    Returns a fixed risk object regardless of inputs so we can easily
    reason about the multiplicative impact on scores.
    """

    def __init__(self, risk_score: float) -> None:  # type: ignore[no-untyped-def]
        self._risk_score = risk_score

    def forecast(self, entity_id: str, horizon_steps: int) -> _StubStabRisk:  # type: ignore[no-untyped-def]
        return _StubStabRisk(
            risk_score=self._risk_score,
            p_worsen_any=self._risk_score,
            p_to_targetable_or_breaker=self._risk_score,
        )


@dataclass
class _StubRegimeRisk:
    risk_score: float
    p_change_any: float


class _StubRegimeForecaster:
    """Stub for regime_forecaster used in tests.

    Returns a fixed regime risk regardless of region/horizon so that we
    can easily reason about the multiplicative impact on scores.
    """

    def __init__(self, risk_score: float, p_change_any: float) -> None:  # type: ignore[no-untyped-def]
        self._risk_score = risk_score
        self._p_change_any = p_change_any

    def forecast(self, region: str, horizon_steps: int) -> _StubRegimeRisk:  # type: ignore[no-untyped-def]
        return _StubRegimeRisk(risk_score=self._risk_score, p_change_any=self._p_change_any)


class TestBasicUniverseModelWithAssessment:
    def _build_price_df(self, closes: List[float]) -> pd.DataFrame:
        instrument_id = "ANY_INST"
        start = date(2024, 1, 1)
        dates: List[date] = [start + timedelta(days=i) for i in range(len(closes))]

        rows = []
        for d, c in zip(dates, closes):
            rows.append(
                (
                    instrument_id,
                    d,
                    c,
                    c + 1.0,
                    c - 1.0,
                    c,
                    c,
                    1_000_000.0,
                    "USD",
                    {},
                )
            )

        df = pd.DataFrame(
            rows,
            columns=[
                "instrument_id",
                "trade_date",
                "open",
                "high",
                "low",
                "close",
                "adjusted_close",
                "volume",
                "currency",
                "metadata",
            ],
        )
        return df

    def test_assessment_scores_influence_ranking_when_enabled(self) -> None:
        """Assessment scores should change universe ranking when enabled.

        Both instruments have identical price history, liquidity, and
        STAB state; the one with higher Assessment score must receive a
        higher universe ranking score.
        """

        # Two instruments in the same market.
        instruments = [
            ("INST_HIGH", "ISS_A", "US_EQ"),
            ("INST_LOW", "ISS_B", "US_EQ"),
        ]

        # Assessment scores: INST_HIGH > INST_LOW.
        assessment_rows = [
            ("INST_HIGH", 0.8),
            ("INST_LOW", 0.1),
        ]

        db = _StubDBManager(instruments=instruments, assessment_rows=assessment_rows)

        # Price history: gentle uptrend, identical for all instruments.
        closes = [100.0 + 0.5 * i for i in range(63)]
        df = self._build_price_df(closes)
        reader = _StubDataReader(df)

        calendar = TradingCalendar()
        stab_storage = _StubStabilityStorage()  # type: ignore[arg-type]

        model = BasicUniverseModel(
            db_manager=db,  # type: ignore[arg-type]
            calendar=calendar,
            data_reader=reader,  # type: ignore[arg-type]
            profile_service=None,  # type: ignore[arg-type]
            stability_storage=stab_storage,
            market_ids=("US_EQ",),
            min_avg_volume=10_000.0,
            max_soft_target_score=90.0,
            exclude_breakers=True,
            exclude_weak_profile_when_fragile=True,
            window_days=21,
            use_assessment_scores=True,
            assessment_strategy_id="TEST_STRAT",
            assessment_horizon_days=21,
            assessment_score_weight=50.0,
        )

        as_of = date(2024, 3, 4)
        members = model.build_universe(as_of, universe_id="TEST_UNIV")

        # Extract included members and their scores.
        included: Dict[str, UniverseMember] = {
            m.entity_id: m for m in members if m.included
        }
        assert {"INST_HIGH", "INST_LOW"} <= set(included.keys())

        high = included["INST_HIGH"]
        low = included["INST_LOW"]

        # Both should have Assessment scores recorded in reasons.
        assert "assessment_score" in high.reasons
        assert "assessment_score" in low.reasons
        assert high.reasons["assessment_score"] > low.reasons["assessment_score"]

        # And the overall ranking score must reflect the Assessment
        # difference (since all other inputs are identical).
        assert high.score > low.score

    def test_lambda_score_provider_influences_scores(self) -> None:
        """Lambda score provider should add a deterministic bump to scores.

        We construct a tiny universe with a single instrument and attach
        a lambda_score_provider that returns a fixed value. The resulting
        member score must equal the base heuristic score plus the
        weighted lambda score, and diagnostics should record the lambda
        inputs.
        """

        instruments = [
            ("INST_LAMBDA", "ISS_A", "US_EQ"),
        ]

        db = _StubDBManager(instruments=instruments, assessment_rows=[])

        closes = [100.0 + 0.5 * i for i in range(21)]
        df = self._build_price_df(closes)
        reader = _StubDataReader(df)

        calendar = TradingCalendar()
        stab_storage = _StubStabilityStorage()  # type: ignore[arg-type]

        lambda_value = 2.0
        lambda_weight = 5.0

        model = BasicUniverseModel(
            db_manager=db,  # type: ignore[arg-type]
            calendar=calendar,
            data_reader=reader,  # type: ignore[arg-type]
            profile_service=None,  # type: ignore[arg-type]
            stability_storage=stab_storage,
            market_ids=("US_EQ",),
            min_avg_volume=10_000.0,
            max_soft_target_score=90.0,
            exclude_breakers=True,
            exclude_weak_profile_when_fragile=True,
            window_days=21,
            use_assessment_scores=False,
            lambda_score_provider=_StubLambdaProvider(lambda_value),
            lambda_score_weight=lambda_weight,
        )

        as_of = date(2024, 3, 4)
        members = model.build_universe(as_of, universe_id="TEST_UNIV_LAMBDA")

        included = [m for m in members if m.included]
        assert len(included) == 1
        member = included[0]

        reasons = member.reasons
        # Lambda diagnostics must be present.
        assert reasons.get("lambda_score") == lambda_value
        assert reasons.get("lambda_score_weight") == lambda_weight
        # Provider metadata should also be surfaced.
        assert reasons.get("lambda_experiment_id") == "EXP_TEST"
        assert reasons.get("lambda_score_column") == "lambda_hat"

        # Reconstruct the base score from recorded reasons.
        base_score = max(0.0, 100.0 - float(reasons["soft_target_score"])) + min(
            50.0, float(reasons["avg_volume_63d"]) / 1_000_000.0
        )
        expected_score = base_score + lambda_weight * lambda_value
        assert member.score == pytest.approx(expected_score)

    def test_max_universe_size_and_sector_caps_with_tiering(self) -> None:
        """BasicUniverseModel should enforce caps and assign CORE/SATELLITE.

        We construct four otherwise-identical instruments across two
        synthetic sectors and configure caps so that at most one name per
        sector is kept and the global universe size is limited. Included
        names must be split across CORE/SATELLITE tiers, and excluded
        names should carry diagnostic reasons.
        """

        # Four instruments in two synthetic sectors.
        instruments = [
            ("INST_A_TECH", "ISS_A", "TECH"),
            ("INST_B_TECH", "ISS_B", "TECH"),
            ("INST_C_FIN", "ISS_C", "FIN"),
            ("INST_D_FIN", "ISS_D", "FIN"),
        ]

        db = _StubDBManager(instruments=instruments, assessment_rows=[])

        closes = [100.0 + 0.5 * i for i in range(21)]
        df = self._build_price_df(closes)
        reader = _StubDataReader(df)

        calendar = TradingCalendar()
        stab_storage = _StubStabilityStorage()  # type: ignore[arg-type]

        model = BasicUniverseModel(
            db_manager=db,  # type: ignore[arg-type]
            calendar=calendar,
            data_reader=reader,  # type: ignore[arg-type]
            profile_service=None,  # type: ignore[arg-type]
            stability_storage=stab_storage,
            market_ids=("US_EQ",),
            min_avg_volume=10_000.0,
            max_soft_target_score=90.0,
            exclude_breakers=True,
            exclude_weak_profile_when_fragile=True,
            window_days=21,
            use_assessment_scores=False,
            max_universe_size=3,
            sector_max_names=1,
            min_price=1.0,
        )

        as_of = date(2024, 3, 4)
        members = model.build_universe(as_of, universe_id="TEST_UNIV_CAPS")

        included = [m for m in members if m.included]
        # At most one name per sector, and we have two sectors.
        assert len(included) == 2

        sectors = {m.reasons.get("sector") for m in included}
        assert sectors == {"TECH", "FIN"}

        tiers = {m.tier for m in included}
        # With 2 kept names and the 50% split heuristic we expect one CORE
        # and one SATELLITE.
        assert tiers == {"CORE", "SATELLITE"}

        # Some members must have been excluded due to sector cap or size.
        excluded_reasons = [
            m.reasons for m in members if not m.included and m.reasons
        ]
        assert any(r.get("excluded_sector_cap") for r in excluded_reasons)

    def test_stability_risk_modifier_scales_scores_and_records_diagnostics(self) -> None:
        """stability_state_change_forecaster should scale scores multiplicatively.

        We construct a tiny universe with a single instrument and attach a
        stability_state_change_forecaster that returns a fixed risk_score.
        The resulting member score must equal the base heuristic score
        multiplied by ``1 - alpha * risk_score``, and diagnostics should
        record STAB risk fields.
        """

        instruments = [
            ("INST_STAB", "ISS_A", "US_EQ"),
        ]

        db = _StubDBManager(instruments=instruments, assessment_rows=[])

        closes = [100.0 + 0.5 * i for i in range(21)]
        df = self._build_price_df(closes)
        reader = _StubDataReader(df)

        calendar = TradingCalendar()
        stab_storage = _StubStabilityStorage()  # type: ignore[arg-type]

        risk_score = 0.5
        alpha = 0.4

        model = BasicUniverseModel(
            db_manager=db,  # type: ignore[arg-type]
            calendar=calendar,
            data_reader=reader,  # type: ignore[arg-type]
            profile_service=None,  # type: ignore[arg-type]
            stability_storage=stab_storage,
            market_ids=("US_EQ",),
            min_avg_volume=10_000.0,
            max_soft_target_score=90.0,
            exclude_breakers=True,
            exclude_weak_profile_when_fragile=True,
            window_days=21,
            use_assessment_scores=False,
            stability_state_change_forecaster=_StubStabRiskForecaster(risk_score),
            stability_risk_alpha=alpha,
            stability_risk_horizon_steps=1,
        )

        as_of = date(2024, 3, 4)
        members = model.build_universe(as_of, universe_id="TEST_UNIV_STAB")

        included = [m for m in members if m.included]
        assert len(included) == 1
        member = included[0]

        reasons = member.reasons
        # STAB risk diagnostics must be present.
        assert reasons.get("stab_risk_score") == pytest.approx(risk_score)
        assert reasons.get("stab_risk_alpha") == pytest.approx(alpha)
        assert "stab_risk_multiplier" in reasons

        # Reconstruct the base score from recorded reasons (prior to STAB
        # risk modifier). This mirrors the heuristic inside
        # BasicUniverseModel.
        base_score = max(0.0, 100.0 - float(reasons["soft_target_score"])) + min(
            50.0, float(reasons["avg_volume_63d"]) / 1_000_000.0
        )
        expected_multiplier = max(0.0, 1.0 - alpha * risk_score)
        expected_score = base_score * expected_multiplier
        assert member.score == pytest.approx(expected_score)

    def test_regime_risk_modifier_scales_scores_and_records_diagnostics(self) -> None:
        """regime_forecaster should scale scores multiplicatively.

        We construct a tiny universe with a single instrument and attach a
        regime_forecaster that returns a fixed risk_score. The resulting
        member score must equal the base heuristic score multiplied by
        ``1 - alpha * risk_score``, and diagnostics should record regime
        risk fields.
        """

        instruments = [
            ("INST_REGIME", "ISS_A", "US_EQ"),
        ]

        db = _StubDBManager(instruments=instruments, assessment_rows=[])

        closes = [100.0 + 0.5 * i for i in range(21)]
        df = self._build_price_df(closes)
        reader = _StubDataReader(df)

        calendar = TradingCalendar()
        stab_storage = _StubStabilityStorage()  # type: ignore[arg-type]

        risk_score = 0.4
        alpha = 0.3

        model = BasicUniverseModel(
            db_manager=db,  # type: ignore[arg-type]
            calendar=calendar,
            data_reader=reader,  # type: ignore[arg-type]
            profile_service=None,  # type: ignore[arg-type]
            stability_storage=stab_storage,
            market_ids=("US_EQ",),
            min_avg_volume=10_000.0,
            max_soft_target_score=90.0,
            exclude_breakers=True,
            exclude_weak_profile_when_fragile=True,
            window_days=21,
            use_assessment_scores=False,
            regime_forecaster=_StubRegimeForecaster(risk_score=risk_score, p_change_any=risk_score),
            regime_region="US",
            regime_risk_alpha=alpha,
            regime_risk_horizon_steps=1,
        )

        as_of = date(2024, 3, 4)
        members = model.build_universe(as_of, universe_id="TEST_UNIV_REGIME")

        included = [m for m in members if m.included]
        assert len(included) == 1
        member = included[0]

        reasons = member.reasons
        # Regime risk diagnostics must be present.
        assert reasons.get("regime_risk_score") == pytest.approx(risk_score)
        assert reasons.get("regime_risk_alpha") == pytest.approx(alpha)
        assert "regime_risk_multiplier" in reasons
        assert reasons.get("regime_p_change_any") == pytest.approx(risk_score)

        # Reconstruct the base score from recorded reasons (prior to
        # regime risk modifier). This mirrors the heuristic inside
        # BasicUniverseModel.
        base_score = max(0.0, 100.0 - float(reasons["soft_target_score"])) + min(
            50.0, float(reasons["avg_volume_63d"]) / 1_000_000.0
        )
        expected_multiplier = max(0.0, 1.0 - alpha * risk_score)
        expected_score = base_score * expected_multiplier
        assert member.score == pytest.approx(expected_score)
