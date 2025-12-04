"""
Prometheus v2: Market calendar loader using EODHD

This module fetches exchange holiday calendars from EODHD and caches them
into the historical database (market_holidays table). It also exposes a
small reader API to retrieve holidays by market_id for use by
TradingCalendar.

Key responsibilities:
- Fetch exchange details (including holidays) from EODHD
- Map exchange codes to logical market_ids (e.g., US_EQ -> US)
- Upsert holidays into historical_db.market_holidays
- Provide read helpers to list holidays for a market and year range

External dependencies:
- requests (via EodhdClient): HTTP calls to EODHD

Database tables accessed:
- historical_db.market_holidays: Write/Read

Thread safety: Thread-safe (stateless operations per call)

Author: Prometheus Team
Created: 2025-12-01
Last Modified: 2025-12-01
Status: Development
Version: v0.1.0
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from prometheus.core.database import DatabaseManager
from prometheus.core.logging import get_logger
from prometheus.data_ingestion.eodhd_client import EodhdClient

logger = get_logger(__name__)


# ============================================================================
# Mapping from logical market_id to EODHD exchange code
# ============================================================================

_MARKET_TO_EXCHANGE: dict[str, str] = {
    "US_EQ": "US",  # NYSE/NASDAQ grouped via US
}


@dataclass(frozen=True)
class Holiday:
    """Simple holiday record."""

    market_id: str
    holiday_date: date
    holiday_name: str


def fetch_exchange_holidays(client: EodhdClient, exchange_code: str) -> List[Tuple[date, str]]:
    """Return list of (date, name) holidays from EODHD exchange-details.

    Args:
        client: EodhdClient instance
        exchange_code: EODHD exchange code (e.g. "US", "LSE")

    Returns:
        List of tuples (holiday_date, holiday_name)

    Raises:
        EodhdClientError: If API request fails
        KeyError: If expected fields missing in payload
    """
    details = client.get_exchange_details(exchange_code)
    holidays = []

    # EODHD uses "ExchangeHolidays" as an object with numbered keys
    exchange_holidays = details.get("ExchangeHolidays", {})
    for key, item in exchange_holidays.items():
        try:
            d = date.fromisoformat(item["Date"])  # YYYY-MM-DD
            name = str(item.get("Holiday") or "Holiday")
        except Exception as exc:  # pragma: no cover - defensive parsing
            logger.warning("Skipping malformed holiday entry: %s (err=%s)", item, exc)
            continue
        holidays.append((d, name))

    logger.info("Parsed %d holidays for exchange %s", len(holidays), exchange_code)
    return holidays


def upsert_market_holidays(
    db_manager: DatabaseManager,
    market_id: str,
    holidays: Iterable[tuple[date, str]],
    *,
    source: str = "eodhd",
) -> int:
    """Upsert holidays into market_holidays table.

    Returns the number of rows inserted/updated.
    """
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
            for d, name in holidays:
                cur.execute(sql, (market_id, d, name, source))
                count += 1
            conn.commit()
        finally:
            cur.close()
    return count


def load_and_cache_market_holidays(
    db_manager: DatabaseManager,
    market_id: str,
    *,
    client: EodhdClient | None = None,
) -> int:
    """Fetch holidays for market_id from EODHD and cache to DB.

    Returns number of rows written.
    """
    exchange = _MARKET_TO_EXCHANGE.get(market_id)
    if not exchange:
        raise ValueError(f"Unsupported market_id: {market_id}")

    client = client or EodhdClient()
    hols = fetch_exchange_holidays(client, exchange)
    written = upsert_market_holidays(db_manager, market_id, hols)
    logger.info("Cached %d holidays for market %s from exchange %s", written, market_id, exchange)
    return written


def list_market_holidays(
    db_manager: DatabaseManager, market_id: str, start_year: int, end_year: int
) -> list[Holiday]:
    """List holidays for market between Jan 1 start_year and Dec 31 end_year."""
    sql = """
        SELECT market_id, holiday_date, holiday_name
        FROM market_holidays
        WHERE market_id = %s
          AND holiday_date BETWEEN %s AND %s
        ORDER BY holiday_date ASC
    """
    start = date(start_year, 1, 1)
    end = date(end_year, 12, 31)

    with db_manager.get_historical_connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute(sql, (market_id, start, end))
            rows = cur.fetchall()
        finally:
            cur.close()

    return [Holiday(market_id=r[0], holiday_date=r[1], holiday_name=r[2]) for r in rows]
