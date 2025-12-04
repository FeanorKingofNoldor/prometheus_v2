"""Prometheus v2: Tests for TimeMachine.

Covers:
- Trading day iteration using TradingCalendar.
- Advancing to next trading day.
- Time-gated data access for prices_daily.
- Strict vs non-strict handling of requested future dates.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from prometheus.core.time import TradingCalendar
from prometheus.execution.time_machine import TimeMachine


class _StubDataReader:
    """Stub DataReader returning a predefined DataFrame.

    This avoids hitting a real database in unit tests while exercising
    the TimeMachine's filtering logic.
    """

    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df

    def read_prices(self, instrument_ids, start_date, end_date):  # type: ignore[no-untyped-def]
        # Ignore filters; TimeMachine is responsible for enforcing the
        # date constraints in these tests.
        return self._df


class TestTimeMachineDates:
    """Tests focused on date iteration and advancement."""

    def test_iter_trading_days_matches_calendar(self) -> None:
        """iter_trading_days should match TradingCalendar.trading_days_between."""

        calendar = TradingCalendar()
        start = date(2024, 1, 3)
        end = date(2024, 1, 9)

        tm = TimeMachine(start_date=start, end_date=end, calendar=calendar, data_reader=None)

        expected = calendar.trading_days_between(start, end)
        actual = list(tm.iter_trading_days())

        assert actual == expected

    def test_advance_to_next_trading_day_skips_weekend(self) -> None:
        """advance_to_next_trading_day should move from Friday to Monday."""

        calendar = TradingCalendar()
        start = date(2024, 1, 5)  # Friday
        end = date(2024, 1, 10)

        tm = TimeMachine(start_date=start, end_date=end, calendar=calendar, data_reader=None)

        assert tm.current_date == start

        next_day = tm.advance_to_next_trading_day()
        assert next_day == date(2024, 1, 8)  # Monday
        assert tm.current_date == date(2024, 1, 8)

        # Advancing past end of window should eventually return None
        tm.set_date(end)
        assert tm.advance_to_next_trading_day() is None


class TestTimeMachineDataAccess:
    """Tests focused on time-gated data access via get_data."""

    def _build_stub_df(self) -> pd.DataFrame:
        instrument_id = "TEST_INST_TM"
        rows = [
            (instrument_id, date(2024, 1, 10), 100.0),
            (instrument_id, date(2024, 1, 16), 101.0),
            (instrument_id, date(2024, 1, 20), 102.0),
        ]
        df = pd.DataFrame(rows, columns=["instrument_id", "trade_date", "close"])
        return df

    def test_non_strict_filters_out_future_rows(self) -> None:
        """When strict_mode=False, future rows should be filtered out."""

        df = self._build_stub_df()
        reader = _StubDataReader(df)

        tm = TimeMachine(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            calendar=TradingCalendar(),
            data_reader=reader,
            strict_mode=False,
        )
        tm.set_date(date(2024, 1, 15))

        result = tm.get_data(
            "prices_daily",
            {
                "instrument_ids": ["TEST_INST_TM"],
                "start_date": date(2024, 1, 1),
                "end_date": date(2024, 1, 31),
            },
        )

        # Only rows with trade_date <= current_date should be present.
        assert not result.empty
        assert result["trade_date"].max() <= date(2024, 1, 15)

    def test_strict_mode_raises_on_future_end_date(self) -> None:
        """When strict_mode=True, requesting future dates should raise."""

        df = self._build_stub_df()
        reader = _StubDataReader(df)

        tm = TimeMachine(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            calendar=TradingCalendar(),
            data_reader=reader,
            strict_mode=True,
        )
        tm.set_date(date(2024, 1, 15))

        with pytest.raises(ValueError):
            tm.get_data(
                "prices_daily",
                {
                    "instrument_ids": ["TEST_INST_TM"],
                    "start_date": date(2024, 1, 1),
                    "end_date": date(2024, 1, 31),
                },
            )

    def test_unsupported_table_raises(self) -> None:
        """Requesting an unsupported table should fail fast."""

        df = self._build_stub_df()
        reader = _StubDataReader(df)

        tm = TimeMachine(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            calendar=TradingCalendar(),
            data_reader=reader,
        )

        with pytest.raises(ValueError):
            tm.get_data("returns_daily", {"instrument_ids": ["TEST_INST_TM"]})
