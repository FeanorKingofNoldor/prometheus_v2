"""Prometheus v2: Tests for BasicPriceStabilityModel.

These tests exercise the basic price-based StabilityModel implementation
using in-memory price data and a simple TradingCalendar.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List

import numpy as np
import pandas as pd

from prometheus.core.time import TradingCalendar
from prometheus.profiles.types import ProfileSnapshot
from prometheus.stability.model_basic import BasicPriceStabilityModel
from prometheus.stability.types import SoftTargetClass


@dataclass
class _StubDataReader:
    """Stub for DataReader.read_prices using an in-memory DataFrame."""

    df: pd.DataFrame

    def read_prices(self, instrument_ids, start_date, end_date):  # type: ignore[no-untyped-def]
        return self.df


@dataclass
class _StubProfileService:
    """Stub for a profile service returning a fixed snapshot."""

    snapshot: ProfileSnapshot

    def get_snapshot(self, issuer_id: str, as_of_date: date) -> ProfileSnapshot:  # type: ignore[no-untyped-def]
        return self.snapshot


class TestBasicPriceStabilityModel:
    """Tests for BasicPriceStabilityModel behaviour."""

    def _build_price_df(self, closes: List[float]) -> pd.DataFrame:
        instrument_id = "TEST_STAB_INSTRUMENT"
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

    def test_stable_uptrend_yields_low_score(self) -> None:
        # Monotonic gentle uptrend with small changes.
        closes = [100.0 + i * 0.2 for i in range(63)]
        df = self._build_price_df(closes)
        reader = _StubDataReader(df)
        calendar = TradingCalendar()

        model = BasicPriceStabilityModel(data_reader=reader, calendar=calendar, window_days=63)
        as_of = date(2024, 3, 4)

        vector, state = model.score(as_of, "INSTRUMENT", "TEST_STAB_INSTRUMENT")

        assert state.soft_target_class in (SoftTargetClass.STABLE, SoftTargetClass.WATCH)
        assert state.soft_target_score < 45.0
        assert vector.overall_score == state.soft_target_score

    def test_high_vol_drawdown_yields_high_score(self) -> None:
        # Start high, then volatile and large drawdown.
        closes = [100.0]
        for i in range(1, 40):
            closes.append(closes[-1] * (1.0 + (0.05 if i % 2 == 0 else -0.06)))
        # Extend to full window by flat prices at the lower level.
        closes.extend([closes[-1]] * (63 - len(closes)))

        df = self._build_price_df(closes)
        reader = _StubDataReader(df)
        calendar = TradingCalendar()

        model = BasicPriceStabilityModel(data_reader=reader, calendar=calendar, window_days=63)
        as_of = date(2024, 3, 4)

        vector, state = model.score(as_of, "INSTRUMENT", "TEST_STAB_INSTRUMENT")

        assert state.soft_target_class in (SoftTargetClass.TARGETABLE, SoftTargetClass.BREAKER)
        assert state.soft_target_score > 60.0
        assert vector.overall_score == state.soft_target_score

    def test_more_drawdown_produces_higher_dd_score(self) -> None:
        # Two series differing only in the depth of the drawdown.
        closes_shallow = [100.0] * 20 + [90.0] * 43  # ~10% dd
        closes_deep = [100.0] * 20 + [70.0] * 43     # ~30% dd

        df_shallow = self._build_price_df(closes_shallow)
        df_deep = self._build_price_df(closes_deep)
        calendar = TradingCalendar()

        model_shallow = BasicPriceStabilityModel(data_reader=_StubDataReader(df_shallow), calendar=calendar, window_days=63)
        model_deep = BasicPriceStabilityModel(data_reader=_StubDataReader(df_deep), calendar=calendar, window_days=63)

        as_of = date(2024, 3, 4)

        vec_shallow, state_shallow = model_shallow.score(as_of, "INSTRUMENT", "TEST_STAB_INSTRUMENT")
        vec_deep, state_deep = model_deep.score(as_of, "INSTRUMENT", "TEST_STAB_INSTRUMENT")

        dd_shallow = vec_shallow.components["dd_score"]
        dd_deep = vec_deep.components["dd_score"]

        assert dd_deep > dd_shallow
        assert state_deep.soft_target_score >= state_shallow.soft_target_score

    def test_weak_profile_flag_reflects_vol_and_dd_risk_flags(self) -> None:
        """Vol/DD profile risk flags should flip ``weak_profile`` when elevated.

        Uses a stub profile service and instrument→issuer mapping so that
        the model can query profile information without touching a real
        database. This test covers the default weighting of vol_flag and
        dd_flag when leverage_flag is absent.
        """

        closes = [100.0 + i * 0.2 for i in range(63)]
        df = self._build_price_df(closes)
        reader = _StubDataReader(df)
        calendar = TradingCalendar()

        instrument_id = "TEST_STAB_INSTRUMENT"
        issuer_id = "ISS_TEST"
        as_of = date(2024, 3, 4)

        def instrument_to_issuer(eid: str) -> str | None:
            return issuer_id if eid == instrument_id else None

        # Low-risk profile → weak_profile should be False.
        low_snapshot = ProfileSnapshot(
            issuer_id=issuer_id,
            as_of_date=as_of,
            structured={},
            embedding=None,
            risk_flags={"vol_flag": 0.1, "dd_flag": 0.1},
        )
        low_service = _StubProfileService(snapshot=low_snapshot)

        model_low = BasicPriceStabilityModel(
            data_reader=reader,
            calendar=calendar,
            window_days=63,
            profile_service=low_service,
            instrument_to_issuer=instrument_to_issuer,
            weak_profile_threshold=0.7,
        )

        _, state_low = model_low.score(as_of, "INSTRUMENT", instrument_id)
        assert state_low.weak_profile is False

        # High-risk profile → weak_profile should be True.
        high_snapshot = ProfileSnapshot(
            issuer_id=issuer_id,
            as_of_date=as_of,
            structured={},
            embedding=None,
            risk_flags={"vol_flag": 1.0, "dd_flag": 1.0},
        )
        high_service = _StubProfileService(snapshot=high_snapshot)

        model_high = BasicPriceStabilityModel(
            data_reader=reader,
            calendar=calendar,
            window_days=63,
            profile_service=high_service,
            instrument_to_issuer=instrument_to_issuer,
            weak_profile_threshold=0.7,
        )

        _, state_high = model_high.score(as_of, "INSTRUMENT", instrument_id)
        assert state_high.weak_profile is True

    def test_leverage_flag_contributes_to_weak_profile(self) -> None:
        """Leverage-based profile risk should affect ``weak_profile``.

        With the same vol/dd flags but different leverage_flag values,
        the high-leverage snapshot should cross the weak_profile
        threshold while the low-leverage snapshot stays below it.
        """

        closes = [100.0 + i * 0.2 for i in range(63)]
        df = self._build_price_df(closes)
        reader = _StubDataReader(df)
        calendar = TradingCalendar()

        instrument_id = "TEST_STAB_INSTRUMENT"
        issuer_id = "ISS_TEST_LEV"
        as_of = date(2024, 3, 4)

        def instrument_to_issuer(eid: str) -> str | None:
            return issuer_id if eid == instrument_id else None

        # Same vol/dd but different leverage.
        low_lev_snapshot = ProfileSnapshot(
            issuer_id=issuer_id,
            as_of_date=as_of,
            structured={},
            embedding=None,
            risk_flags={"vol_flag": 0.3, "dd_flag": 0.3, "leverage_flag": 0.2},
        )
        high_lev_snapshot = ProfileSnapshot(
            issuer_id=issuer_id,
            as_of_date=as_of,
            structured={},
            embedding=None,
            risk_flags={"vol_flag": 0.3, "dd_flag": 0.3, "leverage_flag": 1.0},
        )

        threshold = 0.6
        # Put more weight on leverage so that changing leverage_flag
        # meaningfully moves the combined score around the threshold.
        weight_vol = 0.2
        weight_dd = 0.2
        weight_lev = 0.6

        low_service = _StubProfileService(snapshot=low_lev_snapshot)
        model_low = BasicPriceStabilityModel(
            data_reader=reader,
            calendar=calendar,
            window_days=63,
            profile_service=low_service,
            instrument_to_issuer=instrument_to_issuer,
            weak_profile_threshold=threshold,
            weak_profile_weight_vol=weight_vol,
            weak_profile_weight_dd=weight_dd,
            weak_profile_weight_lev=weight_lev,
        )

        high_service = _StubProfileService(snapshot=high_lev_snapshot)
        model_high = BasicPriceStabilityModel(
            data_reader=reader,
            calendar=calendar,
            window_days=63,
            profile_service=high_service,
            instrument_to_issuer=instrument_to_issuer,
            weak_profile_threshold=threshold,
            weak_profile_weight_vol=weight_vol,
            weak_profile_weight_dd=weight_dd,
            weak_profile_weight_lev=weight_lev,
        )

        _, state_low = model_low.score(as_of, "INSTRUMENT", instrument_id)
        _, state_high = model_high.score(as_of, "INSTRUMENT", instrument_id)

        assert state_low.weak_profile is False
        assert state_high.weak_profile is True
