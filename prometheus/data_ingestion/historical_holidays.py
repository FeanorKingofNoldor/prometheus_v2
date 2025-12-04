"""Prometheus v2 – Historical market holiday loader.

This module provides accurate historical holiday calendars for backtesting
using pandas_market_calendars, which has comprehensive historical data back
to ~1990 for major exchanges.

For live/future data, we continue to use EODHD. This module fills the gap
for historical backtesting.
"""

from __future__ import annotations

from datetime import date
from typing import List, Tuple

try:
    import pandas_market_calendars as mcal
    HAS_PANDAS_MARKET_CALENDARS = True
except ImportError:
    HAS_PANDAS_MARKET_CALENDARS = False

from prometheus.core.database import DatabaseManager
from prometheus.core.logging import get_logger

logger = get_logger(__name__)


# Mapping from our market_id to pandas_market_calendars exchange name
MARKET_TO_CALENDAR = {
    "US_EQ": "NYSE",  # NYSE calendar covers US equities (NYSE + NASDAQ holidays align)
    "EU_EQ": "LSE",   # London Stock Exchange
    "ASIA_EQ": "JPX", # Japan Exchange (Tokyo)
}


def fetch_historical_holidays_pandas(
    market_id: str,
    start_year: int,
    end_year: int,
) -> List[Tuple[date, str]]:
    """Fetch historical holidays using pandas_market_calendars.
    
    Args:
        market_id: Our internal market ID (e.g., "US_EQ")
        start_year: Start year (inclusive)
        end_year: End year (inclusive)
    
    Returns:
        List of (date, name) tuples
        
    Raises:
        ImportError: If pandas_market_calendars not installed
        ValueError: If market_id not supported
    """
    if not HAS_PANDAS_MARKET_CALENDARS:
        raise ImportError(
            "pandas_market_calendars is required for historical holidays. "
            "Install with: pip install pandas_market_calendars"
        )
    
    calendar_name = MARKET_TO_CALENDAR.get(market_id)
    if not calendar_name:
        raise ValueError(f"Unsupported market_id for historical holidays: {market_id}")
    
    logger.info(
        "Fetching historical holidays for %s using %s calendar (%d-%d)",
        market_id,
        calendar_name,
        start_year,
        end_year,
    )
    
    # Get calendar
    cal = mcal.get_calendar(calendar_name)
    
    # Get holidays
    # pandas_market_calendars returns a pandas DatetimeIndex
    start_date_str = f"{start_year}-01-01"
    end_date_str = f"{end_year}-12-31"
    
    # Get schedule first to determine valid range
    try:
        schedule = cal.schedule(start_date=start_date_str, end_date=end_date_str)
        # holidays() returns USFederalHolidayCalendar or similar
        holidays_calendar = cal.holidays()
        all_holidays = holidays_calendar.holidays
        
        # Filter to our date range
        start_pd = f"{start_year}-01-01"
        end_pd = f"{end_year}-12-31"
        
        # Convert to list of dates
        # pandas_market_calendars returns numpy.datetime64, convert to Python date
        import pandas as pd
        holidays_in_range = []
        for h in all_holidays:
            # Convert numpy.datetime64 to pandas Timestamp, then to Python date
            if isinstance(h, pd.Timestamp):
                dt = h
            else:
                dt = pd.Timestamp(h)
            
            # Check if in range
            if start_year <= dt.year <= end_year:
                holidays_in_range.append(
                    (dt.date(), dt.strftime("%B %d"))  # e.g., "January 01"
                )
        
        logger.info(
            "Fetched %d historical holidays for %s (%d-%d)",
            len(holidays_in_range),
            market_id,
            start_year,
            end_year,
        )
        
        return holidays_in_range
        
    except Exception as exc:
        logger.exception(
            "Failed to fetch holidays from pandas_market_calendars for %s: %s",
            market_id,
            exc,
        )
        raise


def backfill_historical_holidays(
    db_manager: DatabaseManager,
    market_id: str,
    start_year: int = 1990,
    end_year: int = 2025,
) -> int:
    """Backfill historical holidays into market_holidays table.
    
    This should be run once to populate historical data for backtesting.
    For live/future data, use the EODHD backfill script instead.
    
    Args:
        db_manager: Database manager
        market_id: Market ID to backfill
        start_year: Start year (default 1990)
        end_year: End year (default 2025)
    
    Returns:
        Number of holidays inserted/updated
    """
    logger.info(
        "Backfilling historical holidays for %s (%d-%d)",
        market_id,
        start_year,
        end_year,
    )
    
    # Fetch holidays
    holidays = fetch_historical_holidays_pandas(market_id, start_year, end_year)
    
    if not holidays:
        logger.warning("No holidays fetched for %s", market_id)
        return 0
    
    # Upsert into database
    sql = """
        INSERT INTO market_holidays (market_id, holiday_date, holiday_name, source, created_at)
        VALUES (%s, %s, %s, %s, NOW())
        ON CONFLICT (market_id, holiday_date) DO UPDATE SET
            holiday_name = EXCLUDED.holiday_name,
            source = EXCLUDED.source
    """
    
    count = 0
    with db_manager.get_historical_connection() as conn:
        cur = conn.cursor()
        try:
            for holiday_date, holiday_name in holidays:
                cur.execute(sql, (market_id, holiday_date, holiday_name, "pandas_market_calendars"))
                count += 1
            conn.commit()
        finally:
            cur.close()
    
    logger.info(
        "Backfilled %d historical holidays for %s",
        count,
        market_id,
    )
    
    return count


# Fallback: Hardcoded historical US holidays if pandas_market_calendars unavailable
# These are the major US market holidays that occur annually
US_MARKET_HOLIDAYS_RULES = [
    # Fixed dates
    ("01-01", "New Year's Day"),
    ("07-04", "Independence Day"),
    ("12-25", "Christmas Day"),
    # Third Monday rules (approximate - real calendar handles observed dates)
    ("01-15", "Martin Luther King Jr. Day"),  # ~3rd Monday of January
    ("02-15", "Presidents' Day"),              # ~3rd Monday of February
    ("05-25", "Memorial Day"),                 # ~Last Monday of May
    ("09-01", "Labor Day"),                    # ~1st Monday of September
    ("11-22", "Thanksgiving"),                 # ~4th Thursday of November
]


def get_fallback_us_holidays(start_year: int, end_year: int) -> List[Tuple[date, str]]:
    """Generate approximate US market holidays when pandas_market_calendars unavailable.
    
    WARNING: This is a rough approximation. Real holidays have complex rules
    (e.g., observed dates when holidays fall on weekends). Use
    pandas_market_calendars for accurate historical data.
    """
    logger.warning(
        "Using fallback holiday generation (inaccurate). "
        "Install pandas_market_calendars for accurate historical holidays."
    )
    
    holidays = []
    for year in range(start_year, end_year + 1):
        for month_day, name in US_MARKET_HOLIDAYS_RULES:
            month, day = map(int, month_day.split("-"))
            try:
                d = date(year, month, day)
                # Skip weekends (real holidays are observed on nearby weekdays)
                if d.weekday() < 5:  # Monday-Friday
                    holidays.append((d, name))
            except ValueError:
                # Invalid date (e.g., Feb 31)
                continue
    
    return holidays


__all__ = [
    "fetch_historical_holidays_pandas",
    "backfill_historical_holidays",
    "get_fallback_us_holidays",
    "HAS_PANDAS_MARKET_CALENDARS",
]
