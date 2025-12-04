"""Prometheus v2: Tests for ProfileFeatureBuilder.

These tests use a stubbed DB interface and DataReader to validate
structured field and risk flag construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from prometheus.core.time import TradingCalendar
from prometheus.profiles.features import ProfileFeatureBuilder


@dataclass
class _StubDBManager:
    """Very small stub for DatabaseManager runtime connection.

    It responds to issuer and instrument lookups using in-memory maps.
    """

    issuers: Dict[str, tuple]
    instruments: Dict[str, List[str]]

    class _Conn:
        def __init__(self, parent: "_StubDBManager") -> None:
            self._parent = parent

        def cursor(self):  # type: ignore[no-untyped-def]
            return _StubCursor(self._parent)

        def __enter__(self):  # type: ignore[no-untyped-def]
            return self

        def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
            return False

    def get_runtime_connection(self):  # type: ignore[no-untyped-def]
        return self._Conn(self)


class _StubCursor:
    def __init__(self, parent: _StubDBManager) -> None:
        self._parent = parent
        self._last_query: str | None = None
        self._last_params: tuple[Any, ...] | None = None

    def execute(self, sql, params):  # type: ignore[no-untyped-def]
        self._last_query = sql
        self._last_params = params

    def fetchone(self):  # type: ignore[no-untyped-def]
        if "FROM issuers" in (self._last_query or ""):
            issuer_id = self._last_params[0]
            return self._parent.issuers.get(issuer_id)
        if "FROM instruments" in (self._last_query or ""):
            issuer_id = self._last_params[0]
            ids = self._parent.instruments.get(issuer_id) or []
            return (ids[0],) if ids else None
        return None

    def close(self):  # type: ignore[no-untyped-def]
        return None


@dataclass
class _StubDataReader:
    df: pd.DataFrame

    def read_prices(self, instrument_ids, start_date, end_date):  # type: ignore[no-untyped-def]
        return self.df


class TestProfileFeatureBuilder:
    def _build_price_df(self, closes: List[float]) -> pd.DataFrame:
        instrument_id = "TEST_PROF_INST"
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

    def test_build_structured_includes_issuer_metadata_and_numeric_features(self) -> None:
        issuer_id = "ISS_TEST"
        issuers = {
            issuer_id: ("COMPANY", "Test Corp", "US", "TECH", "SOFTWARE", {"rating": "A"}),
        }
        instruments = {issuer_id: ["TEST_PROF_INST"]}

        db = _StubDBManager(issuers=issuers, instruments=instruments)
        closes = [100.0 + i for i in range(63)]
        df = self._build_price_df(closes)
        reader = _StubDataReader(df)
        calendar = TradingCalendar()

        builder = ProfileFeatureBuilder(db_manager=db, data_reader=reader, calendar=calendar, window_days=63)
        as_of = date(2024, 3, 4)

        structured = builder.build_structured(issuer_id, as_of)

        assert structured["issuer_id"] == issuer_id
        assert structured["name"] == "Test Corp"
        assert structured["issuer_type"] == "COMPANY"
        assert structured["sector"] == "TECH"
        assert "numeric_features" in structured
        numeric = structured["numeric_features"]
        assert numeric["instrument_id"] == "TEST_PROF_INST"
        assert "price_vol_63d" in numeric
        assert "price_dd_63d" in numeric
        assert "price_trend_63d" in numeric

    def test_build_risk_flags_reflects_vol_and_drawdown(self) -> None:
        issuer_id = "ISS_TEST"
        issuers = {issuer_id: ("COMPANY", "Test Corp", "US", "TECH", "SOFTWARE", {})}
        instruments = {issuer_id: ["TEST_PROF_INST"]}
        db = _StubDBManager(issuers=issuers, instruments=instruments)
        calendar = TradingCalendar()

        closes_low = [100.0 + i * 0.1 for i in range(63)]
        closes_high = []
        price = 100.0
        for i in range(63):
            price *= 1.05 if i % 2 == 0 else 0.95
            closes_high.append(price)

        df_low = self._build_price_df(closes_low)
        df_high = self._build_price_df(closes_high)

        builder_low = ProfileFeatureBuilder(db_manager=db, data_reader=_StubDataReader(df_low), calendar=calendar, window_days=63)
        builder_high = ProfileFeatureBuilder(db_manager=db, data_reader=_StubDataReader(df_high), calendar=calendar, window_days=63)

        as_of = date(2024, 3, 4)
        structured_low = builder_low.build_structured(issuer_id, as_of)
        structured_high = builder_high.build_structured(issuer_id, as_of)

        flags_low = builder_low.build_risk_flags(structured_low)
        flags_high = builder_high.build_risk_flags(structured_high)

        assert flags_high["vol_flag"] >= flags_low["vol_flag"]
        assert flags_high["dd_flag"] >= flags_low["dd_flag"]
