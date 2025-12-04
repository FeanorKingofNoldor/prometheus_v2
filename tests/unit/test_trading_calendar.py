"""
Prometheus v2: Tests for Trading Calendar

Test suite for ``prometheus.core.time``. Covers:
- Weekend handling
- Simple US_EQ holiday handling
- Previous/next trading day logic
- Trading days between two dates
"""

from __future__ import annotations

from datetime import date

from prometheus.core.time import (
    US_EQ,
    TradingCalendar,
    TradingCalendarConfig,
    get_next_trading_day,
    get_prev_trading_day,
    is_trading_day,
    trading_days_between,
)


class TestTradingCalendar:
    """Tests for the TradingCalendar implementation."""

    def test_weekends_are_not_trading_days(self) -> None:
        """Saturdays and Sundays should never be trading days."""

        # Use hardcoded holidays for unit tests (avoid DB dependency)
        calendar = TradingCalendar(TradingCalendarConfig(use_db_holidays=False))
        saturday = date(2024, 1, 6)
        sunday = date(2024, 1, 7)

        assert not calendar.is_trading_day(saturday)
        assert not calendar.is_trading_day(sunday)

    def test_weekdays_are_trading_days_except_holidays(self) -> None:
        """Normal weekdays should be trading days, except configured holidays."""

        # Use hardcoded holidays for unit tests (avoid DB dependency)
        calendar = TradingCalendar(TradingCalendarConfig(use_db_holidays=False))
        normal_weekday = date(2024, 1, 3)  # Wednesday
        holiday = date(2024, 1, 1)  # New Year's Day (configured holiday)

        assert calendar.is_trading_day(normal_weekday)
        assert not calendar.is_trading_day(holiday)

    def test_prev_trading_day_skips_weekend(self) -> None:
        """Previous trading day from Monday should be the prior Friday."""

        calendar = TradingCalendar(TradingCalendarConfig(use_db_holidays=False))
        monday = date(2024, 1, 8)

        prev_day = calendar.get_prev_trading_day(monday)
        assert prev_day == date(2024, 1, 5)  # Friday

    def test_next_trading_day_skips_weekend(self) -> None:
        """Next trading day from Friday should be the following Monday."""

        calendar = TradingCalendar(TradingCalendarConfig(use_db_holidays=False))
        friday = date(2024, 1, 5)

        next_day = calendar.get_next_trading_day(friday)
        assert next_day == date(2024, 1, 8)  # Monday

    def test_prev_and_next_trading_day_across_holiday(self) -> None:
        """Holiday should be skipped when computing prev/next trading day."""

        calendar = TradingCalendar(TradingCalendarConfig(use_db_holidays=False))
        holiday = date(2024, 1, 1)  # Tuesday (treated as holiday)

        prev_day = calendar.get_prev_trading_day(holiday)
        next_day = calendar.get_next_trading_day(holiday)

        assert prev_day == date(2023, 12, 29)  # Last trading day of 2023 (Friday)
        assert next_day == date(2024, 1, 2)    # First trading day after holiday

    def test_trading_days_between_inclusive(self) -> None:
        """trading_days_between should include both start and end when trading days."""

        calendar = TradingCalendar(TradingCalendarConfig(use_db_holidays=False))
        start = date(2024, 1, 3)  # Wednesday
        end = date(2024, 1, 9)    # Tuesday

        days = calendar.trading_days_between(start, end)

        # Should exclude weekend (6th, 7th)
        expected = [
            date(2024, 1, 3),
            date(2024, 1, 4),
            date(2024, 1, 5),
            date(2024, 1, 8),
            date(2024, 1, 9),
        ]
        assert days == expected

    def test_module_level_helpers_delegate_to_calendar(self) -> None:
        """Module-level convenience functions should behave like the instance methods."""

        non_trading = date(2024, 1, 6)  # Saturday
        assert not is_trading_day(US_EQ, non_trading)

        friday = date(2024, 1, 5)
        monday = date(2024, 1, 8)

        assert get_next_trading_day(US_EQ, friday) == monday
        assert get_prev_trading_day(US_EQ, monday) == friday

        days = trading_days_between(US_EQ, friday, monday)
        assert days == [friday, monday]
