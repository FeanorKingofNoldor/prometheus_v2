"""Unit tests for returns/volatility derivation from prices_daily.

These tests work purely in memory using small artificial price series
and do not hit a real database; we exercise the internal math helpers by
calling ``compute_returns_and_volatility_for_instrument`` against a
stubbed database manager.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import List
from unittest.mock import MagicMock

import numpy as np
import pandas as pd

from prometheus.data.types import ReturnsRecord, VolatilityRecord
from prometheus.data_ingestion.derived.returns_volatility import (
    DerivedStatsResult,
    compute_returns_and_volatility_for_instrument,
)


class _StubConn:
    def __init__(self) -> None:
        self.cursor_obj = MagicMock()

    def cursor(self):  # type: ignore[no-untyped-def]
        return self.cursor_obj

    def __enter__(self):  # type: ignore[no-untyped-def]
        return self

    def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
        return False

    def commit(self) -> None:  # pragma: no cover - stub
        return None


class _StubDbManager:
    """Very small stub for DatabaseManager used in these tests.

    We intercept ``get_historical_connection`` and route SQL calls to an
    in-memory DataFrame that represents ``prices_daily``.
    """

    def __init__(self, df_prices: pd.DataFrame) -> None:
        self._df_prices = df_prices
        self._conn = _StubConn()

        # Configure cursor behaviour
        cursor = self._conn.cursor_obj

        def _execute(sql, params=None):  # type: ignore[no-untyped-def]
            sql_str = " ".join(sql.split()).lower()
            if "min(trade_date)" in sql_str:
                inst_id = params[0]
                sub = self._df_prices[self._df_prices["instrument_id"] == inst_id]
                if sub.empty:
                    cursor.fetchone.return_value = (None, None)
                else:
                    cursor.fetchone.return_value = (
                        sub["trade_date"].min(),
                        sub["trade_date"].max(),
                    )
            elif sql_str.startswith("delete from returns_daily") or sql_str.startswith(
                "delete from volatility_daily",
            ):
                # No-op for unit tests; writer will not actually hit DB.
                pass
            else:
                raise AssertionError(f"Unexpected SQL in stub: {sql}")

        cursor.execute.side_effect = _execute

    def get_historical_connection(self):  # type: ignore[no-untyped-def]
        return self._conn


def test_compute_returns_and_volatility_math_only(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Validate basic shape of returns and volatility calculations.

    We construct a synthetic price series with deterministic growth so
    that returns are strictly positive and volatility is finite.
    """

    instrument_id = "TEST_INST"
    # Use a contiguous range of valid calendar dates spanning > 63 days
    dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(0, 90)]
    prices = np.linspace(100.0, 130.0, num=len(dates))

    df_prices = pd.DataFrame(
        {
            "instrument_id": [instrument_id] * len(dates),
            "trade_date": dates,
            "open": prices,
            "high": prices + 1.0,
            "low": prices - 1.0,
            "close": prices,
            "adjusted_close": prices,
            "volume": np.full_like(prices, 1_000_000.0),
            "currency": ["USD"] * len(dates),
            "metadata": [{}] * len(dates),
        },
    )

    # Stub DataReader.read_prices to return our DataFrame regardless of dates.
    from prometheus import data as _data_pkg  # type: ignore[import-not-found]

    from prometheus.data import reader as data_reader_mod

    def _stub_read_prices(self, instrument_ids, start_date, end_date):  # type: ignore[no-untyped-def]
        return df_prices.copy()

    monkeypatch.setattr(data_reader_mod.DataReader, "read_prices", _stub_read_prices)

    db_manager = _StubDbManager(df_prices)

    # Also stub DataWriter so we can capture what would be written.
    from prometheus.data import writer as data_writer_mod

    written_returns: List[ReturnsRecord] = []
    written_vols: List[VolatilityRecord] = []

    def _stub_write_returns(self, records):  # type: ignore[no-untyped-def]
        written_returns.extend(records)

    def _stub_write_volatility(self, records):  # type: ignore[no-untyped-def]
        written_vols.extend(records)

    monkeypatch.setattr(data_writer_mod.DataWriter, "write_returns", _stub_write_returns)
    monkeypatch.setattr(data_writer_mod.DataWriter, "write_volatility", _stub_write_volatility)

    result: DerivedStatsResult = compute_returns_and_volatility_for_instrument(
        instrument_id,
        db_manager=db_manager,  # type: ignore[arg-type]
    )

    # We expect some rows written, but fewer than the total number of
    # price observations because we require lookback windows.
    assert result.returns_rows > 0
    assert result.returns_rows < len(dates)
    assert result.volatility_rows > 0
    assert result.volatility_rows <= result.returns_rows

    # Sanity checks on the derived values
    assert written_returns
    assert all(r.instrument_id == instrument_id for r in written_returns)
    assert all(np.isfinite(r.ret_1d) for r in written_returns)

    assert written_vols
    assert all(v.instrument_id == instrument_id for v in written_vols)
    assert all(v.vol_21d >= 0.0 for v in written_vols)
    assert all(v.vol_63d >= 0.0 for v in written_vols)
