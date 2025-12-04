"""
Prometheus v2: Trading Calendar Utilities

This module implements a simple trading calendar abstraction used by
engines and backtesting infrastructure. For Iteration 2 it supports a
single market ("US_EQ") with weekend and a small fixed holiday set.

Key responsibilities:
- Determine whether a given date is a trading day
- Compute previous/next trading days
- Enumerate trading days between two dates

External dependencies:
- datetime: Standard library date arithmetic only

Database tables accessed:
- None (pure calendar logic)

Thread safety: Thread-safe (stateless, no shared mutable state)

Author: Prometheus Team
Created: 2025-11-24
Last Modified: 2025-11-24
Status: Development
Version: v0.2.0
"""

# ============================================================================
# Imports
# ============================================================================

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta

from prometheus.core.logging import get_logger

# ============================================================================
# Module Setup
# ============================================================================

logger = get_logger(__name__)

# Trading calendar identifiers
US_EQ: str = "US_EQ"

# Minimal holiday set for US equities (NYSE/NASDAQ) to support tests.
# In later iterations this should be expanded or sourced from an
# authoritative calendar library.
US_EQ_HOLIDAYS: set[date] = {
    date(2024, 1, 1),   # New Year's Day
    date(2024, 12, 25), # Christmas Day
}

# Mapping from market code to holiday set for simple lookup
MARKET_HOLIDAYS: Mapping[str, set[date]] = {
    US_EQ: US_EQ_HOLIDAYS,
}


@dataclass(frozen=True)
class TradingCalendarConfig:
    """Configuration for a trading calendar.

    Attributes:
        market: Market identifier (e.g. "US_EQ").
        use_db_holidays: If True, load holidays from market_holidays table.
            If False or DB unavailable, use hardcoded fallback.
    """

    market: str = US_EQ
    use_db_holidays: bool = True


class TradingCalendar:
    """Trading calendar for a specific market.

    This calendar implements trading-day logic:

    - Trading days are Monday–Friday (no weekend trading).
    - Market-specific holidays are excluded.

    Holidays are loaded from the historical DB (market_holidays table)
    if available and configured. Falls back to a minimal hardcoded set
    if DB is unavailable or use_db_holidays=False.
    """

    def __init__(
        self,
        config: TradingCalendarConfig | None = None,
        db_manager: object | None = None,
    ) -> None:
        """Initialise the trading calendar.

        Args:
            config: Optional :class:`TradingCalendarConfig`. If omitted,
                a default configuration for ``US_EQ`` is used.
            db_manager: Optional DatabaseManager for loading holidays from DB.
                If None and config.use_db_holidays is True, will attempt to
                import and use get_db_manager().
        """
        self._config = config or TradingCalendarConfig()
        self._market = self._config.market

        # Attempt to load holidays from DB if requested
        if self._config.use_db_holidays:
            self._holidays = self._load_holidays_from_db(db_manager)
        else:
            self._holidays = MARKET_HOLIDAYS.get(self._market, set())

        logger.info(
            "TradingCalendar initialized: market=%s, holidays=%d, use_db=%s",
            self._market,
            len(self._holidays),
            self._config.use_db_holidays,
        )

    # ======================================================================
    # Internal: Holiday Loading
    # ======================================================================

    def _load_holidays_from_db(self, db_manager: object | None) -> set[date]:
        """Load holidays from market_holidays table.

        Returns a set of holiday dates. Falls back to hardcoded holidays if
        DB unavailable or query fails.
        """
        try:
            # Lazy import to avoid circular dependency at module load time
            from prometheus.core.database import get_db_manager
            from prometheus.data_ingestion.market_calendar import list_market_holidays

            db = db_manager or get_db_manager()
            # Load holidays for a broad year range (2000-2030)
            holidays_list = list_market_holidays(db, self._market, 2000, 2030)
            loaded = {h.holiday_date for h in holidays_list}
            if loaded:
                logger.info(
                    "Loaded %d holidays from DB for market %s", len(loaded), self._market
                )
                return loaded
            # No holidays in DB, fallback
            logger.warning(
                "No holidays found in DB for market %s, using hardcoded fallback",
                self._market,
            )
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning(
                "Failed to load holidays from DB for market %s: %s. Using fallback.",
                self._market,
                exc,
            )

        # Fallback to hardcoded holidays
        return MARKET_HOLIDAYS.get(self._market, set())

    # ======================================================================
    # Core API
    # ======================================================================

    def is_trading_day(self, as_of_date: date) -> bool:
        """Return True if ``as_of_date`` is a trading day for this market.

        Args:
            as_of_date: Date to check.

        Returns:
            True if the date is a weekday and not a configured holiday.
        """

        # Weekends are never trading days
        if as_of_date.weekday() >= 5:  # 5 = Saturday, 6 = Sunday
            return False

        # Market-specific holidays
        if as_of_date in self._holidays:
            return False

        return True

    def get_prev_trading_day(self, as_of_date: date, n: int = 1) -> date:
        """Return the previous trading day ``n`` steps back.

        Args:
            as_of_date: Anchor date.
            n: Number of trading days to step back (default 1).

        Returns:
            The previous trading day ``n`` days before ``as_of_date``.
        """

        if n < 1:
            raise ValueError("n must be >= 1")

        current = as_of_date
        steps = 0
        while steps < n:
            current = current - timedelta(days=1)
            if self.is_trading_day(current):
                steps += 1
        return current

    def get_next_trading_day(self, as_of_date: date, n: int = 1) -> date:
        """Return the next trading day ``n`` steps forward.

        Args:
            as_of_date: Anchor date.
            n: Number of trading days to step forward (default 1).

        Returns:
            The next trading day ``n`` days after ``as_of_date``.
        """

        if n < 1:
            raise ValueError("n must be >= 1")

        current = as_of_date
        steps = 0
        while steps < n:
            current = current + timedelta(days=1)
            if self.is_trading_day(current):
                steps += 1
        return current

    def trading_days_between(self, start_date: date, end_date: date) -> list[date]:
        """Return all trading days in the inclusive range [start_date, end_date].

        Args:
            start_date: Start of the range (inclusive).
            end_date: End of the range (inclusive).

        Returns:
            A list of trading-day dates in ascending order. Returns an
            empty list if ``start_date`` > ``end_date``.
        """

        if start_date > end_date:
            return []

        days: list[date] = []
        current = start_date
        while current <= end_date:
            if self.is_trading_day(current):
                days.append(current)
            current = current + timedelta(days=1)
        return days


# ============================================================================
# Module-level convenience functions (spec-style API)
# ============================================================================


def is_trading_day(market: str, as_of_date: date) -> bool:
    """Convenience wrapper for :meth:`TradingCalendar.is_trading_day`.

    Args:
        market: Market identifier (e.g. "US_EQ").
        as_of_date: Date to check.
    """

    calendar = TradingCalendar(TradingCalendarConfig(market=market))
    return calendar.is_trading_day(as_of_date)


def get_prev_trading_day(market: str, as_of_date: date, n: int = 1) -> date:
    """Convenience wrapper for previous trading day lookup."""

    calendar = TradingCalendar(TradingCalendarConfig(market=market))
    return calendar.get_prev_trading_day(as_of_date, n=n)


def get_next_trading_day(market: str, as_of_date: date, n: int = 1) -> date:
    """Convenience wrapper for next trading day lookup."""

    calendar = TradingCalendar(TradingCalendarConfig(market=market))
    return calendar.get_next_trading_day(as_of_date, n=n)


def trading_days_between(market: str, start_date: date, end_date: date) -> list[date]:
    """Convenience wrapper for trading days enumeration."""

    calendar = TradingCalendar(TradingCalendarConfig(market=market))
    return calendar.trading_days_between(start_date, end_date)


# NOTE(prometheus, 2025-12-01): Holidays are now loaded from market_holidays
# table via EODHD API. The hardcoded US_EQ_HOLIDAYS above serves only as a
# fallback for testing/dev environments where the DB may not be populated.
