"""Prometheus v2 – Daily data ingestion orchestrator.

This module orchestrates the complete daily data ingestion workflow:
1. Fetch EOD prices for all active instruments in a market
2. Compute returns and volatility
3. Mark ingestion as complete
4. Trigger engine run to DATA_READY state

Designed to be called by the market-aware daemon's ingest_prices job.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import List, Set

from prometheus.core.database import DatabaseManager
from prometheus.core.ids import generate_uuid
from prometheus.core.logging import get_logger
from prometheus.data.writer import DataWriter
from prometheus.data_ingestion.eodhd_client import EodhdClient
from prometheus.data_ingestion.eodhd_prices import ingest_eodhd_prices_for_instruments

logger = get_logger(__name__)


class IngestionStatus(str, Enum):
    """Status of a data ingestion run."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


@dataclass
class IngestionResult:
    """Result of a daily ingestion run."""
    market_id: str
    as_of_date: date
    status: IngestionStatus
    instruments_received: int
    instruments_expected: int
    error_message: str | None = None


# ============================================================================
# Database Functions
# ============================================================================


def create_ingestion_status(
    db_manager: DatabaseManager,
    market_id: str,
    as_of_date: date,
    instruments_expected: int,
) -> str:
    """Create a new ingestion status record."""
    status_id = generate_uuid()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    sql = """
        INSERT INTO data_ingestion_status (
            status_id, market_id, as_of_date, status,
            instruments_expected, instruments_received,
            started_at, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (market_id, as_of_date) 
        DO UPDATE SET
            status = EXCLUDED.status,
            instruments_expected = EXCLUDED.instruments_expected,
            started_at = EXCLUDED.started_at,
            updated_at = EXCLUDED.updated_at
        RETURNING status_id
    """

    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                sql,
                (
                    status_id,
                    market_id,
                    as_of_date,
                    IngestionStatus.IN_PROGRESS.value,
                    instruments_expected,
                    0,
                    now,
                    now,
                    now,
                ),
            )
            result = cursor.fetchone()
            conn.commit()
            return result[0] if result else status_id
        finally:
            cursor.close()


def update_ingestion_status(
    db_manager: DatabaseManager,
    status_id: str,
    status: IngestionStatus,
    instruments_received: int,
    error_message: str | None = None,
    error_details: dict | None = None,
) -> None:
    """Update an ingestion status record."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    if status == IngestionStatus.COMPLETE:
        sql = """
            UPDATE data_ingestion_status
            SET status = %s,
                instruments_received = %s,
                completed_at = %s,
                last_price_timestamp = %s,
                updated_at = %s
            WHERE status_id = %s
        """
        params = (status.value, instruments_received, now, now, now, status_id)
    else:
        sql = """
            UPDATE data_ingestion_status
            SET status = %s,
                instruments_received = %s,
                error_message = %s,
                error_details = %s,
                updated_at = %s
            WHERE status_id = %s
        """
        params = (
            status.value,
            instruments_received,
            error_message,
            json.dumps(error_details) if error_details else None,
            now,
            status_id,
        )

    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(sql, params)
            conn.commit()
        finally:
            cursor.close()


def get_ingestion_status(
    db_manager: DatabaseManager,
    market_id: str,
    as_of_date: date,
) -> IngestionStatus | None:
    """Get the current ingestion status for a market/date."""
    sql = """
        SELECT status
        FROM data_ingestion_status
        WHERE market_id = %s AND as_of_date = %s
    """

    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (market_id, as_of_date))
            row = cursor.fetchone()
        finally:
            cursor.close()

    if not row:
        return None

    return IngestionStatus(row[0])


# ============================================================================
# Instrument Management
# ============================================================================


def get_active_instruments_for_market(
    db_manager: DatabaseManager,
    market_id: str,
) -> List[tuple[str, str, str]]:
    """Get all active instruments for a market.
    
    Returns:
        List of (instrument_id, symbol, currency) tuples
    """
    sql = """
        SELECT instrument_id, metadata->>'eodhd_symbol', currency
        FROM instruments
        WHERE market_id = %s
          AND status = 'ACTIVE'
          AND metadata->>'eodhd_symbol' IS NOT NULL
        ORDER BY instrument_id
    """

    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (market_id,))
            rows = cursor.fetchall()
        finally:
            cursor.close()

    return [(row[0], row[1], row[2] or "USD") for row in rows]


# ============================================================================
# Returns & Volatility Computation
# ============================================================================


def compute_returns_and_volatility(
    db_manager: DatabaseManager,
    instrument_ids: List[str],
    as_of_date: date,
    lookback_days: int = 252,
) -> tuple[int, int]:
    """Compute returns and volatility for instruments on a given date.
    
    Returns:
        (returns_computed, volatility_computed) counts
    """
    # Get the trading day before as_of_date for return calculation
    sql_prev_day = """
        SELECT MAX(trade_date)
        FROM prices_daily
        WHERE instrument_id = %s
          AND trade_date < %s
    """

    # Insert returns
    sql_insert_returns = """
        INSERT INTO returns_daily (
            instrument_id, trade_date, return_1d, created_at
        )
        SELECT 
            curr.instrument_id,
            curr.trade_date,
            (curr.adjusted_close / prev.adjusted_close) - 1.0 as return_1d,
            NOW()
        FROM prices_daily curr
        JOIN prices_daily prev ON prev.instrument_id = curr.instrument_id
            AND prev.trade_date = (
                SELECT MAX(trade_date)
                FROM prices_daily
                WHERE instrument_id = curr.instrument_id
                  AND trade_date < curr.trade_date
            )
        WHERE curr.instrument_id = ANY(%s)
          AND curr.trade_date = %s
          AND prev.adjusted_close > 0
        ON CONFLICT (instrument_id, trade_date) DO UPDATE
        SET return_1d = EXCLUDED.return_1d,
            created_at = EXCLUDED.created_at
    """

    # Compute rolling volatility (21-day)
    sql_insert_volatility = """
        INSERT INTO volatility_daily (
            instrument_id, trade_date, volatility_21d, created_at
        )
        SELECT 
            instrument_id,
            trade_date,
            STDDEV(return_1d) OVER (
                PARTITION BY instrument_id
                ORDER BY trade_date
                ROWS BETWEEN 20 PRECEDING AND CURRENT ROW
            ) * SQRT(252) as volatility_21d,
            NOW()
        FROM returns_daily
        WHERE instrument_id = ANY(%s)
          AND trade_date <= %s
          AND trade_date > %s
        ON CONFLICT (instrument_id, trade_date) DO UPDATE
        SET volatility_21d = EXCLUDED.volatility_21d,
            created_at = EXCLUDED.created_at
    """

    returns_computed = 0
    volatility_computed = 0

    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            # Compute returns
            cursor.execute(sql_insert_returns, (instrument_ids, as_of_date))
            returns_computed = cursor.rowcount or 0

            # Compute volatility
            lookback_start = as_of_date - timedelta(days=lookback_days)
            cursor.execute(sql_insert_volatility, (instrument_ids, as_of_date, lookback_start))
            volatility_computed = cursor.rowcount or 0

            conn.commit()
        finally:
            cursor.close()

    logger.info(
        "compute_returns_and_volatility: as_of_date=%s computed %d returns, %d volatility",
        as_of_date,
        returns_computed,
        volatility_computed,
    )

    return returns_computed, volatility_computed


# ============================================================================
# Main Orchestration
# ============================================================================


def run_daily_ingestion(
    db_manager: DatabaseManager,
    market_id: str,
    as_of_date: date,
    *,
    eodhd_client: EodhdClient | None = None,
) -> IngestionResult:
    """Run complete daily ingestion for a market.
    
    Args:
        db_manager: Database manager
        market_id: Market identifier (e.g., "US_EQ")
        as_of_date: Date to ingest data for
        eodhd_client: Optional EODHD client (created if not provided)
    
    Returns:
        IngestionResult with status and counts
    """
    logger.info(
        "run_daily_ingestion: starting market_id=%s as_of_date=%s",
        market_id,
        as_of_date,
    )

    # Get active instruments
    instruments = get_active_instruments_for_market(db_manager, market_id)
    if not instruments:
        logger.warning("run_daily_ingestion: no active instruments for market_id=%s", market_id)
        return IngestionResult(
            market_id=market_id,
            as_of_date=as_of_date,
            status=IngestionStatus.COMPLETE,
            instruments_received=0,
            instruments_expected=0,
        )

    # Create ingestion status record
    status_id = create_ingestion_status(db_manager, market_id, as_of_date, len(instruments))

    try:
        # Build instrument mapping
        instrument_mapping = {inst_id: symbol for inst_id, symbol, _ in instruments}
        currency_mapping = {inst_id: currency for inst_id, _, currency in instruments}

        # Create clients
        if eodhd_client is None:
            eodhd_client = EodhdClient()
        writer = DataWriter(db_manager=db_manager)

        # Fetch prices
        logger.info(
            "run_daily_ingestion: fetching prices for %d instruments",
            len(instruments),
        )
        price_results = ingest_eodhd_prices_for_instruments(
            mapping=instrument_mapping,
            start_date=as_of_date,
            end_date=as_of_date,
            default_currency="USD",
            currency_by_instrument=currency_mapping,
            client=eodhd_client,
            writer=writer,
        )

        instruments_received = sum(1 for r in price_results if r.bars_written > 0)
        instrument_ids = list(instrument_mapping.keys())

        logger.info(
            "run_daily_ingestion: fetched prices for %d/%d instruments",
            instruments_received,
            len(instruments),
        )

        # Compute returns and volatility
        logger.info("run_daily_ingestion: computing returns and volatility")
        returns_count, vol_count = compute_returns_and_volatility(
            db_manager,
            instrument_ids,
            as_of_date,
        )

        # Mark as complete
        update_ingestion_status(
            db_manager,
            status_id,
            IngestionStatus.COMPLETE,
            instruments_received,
        )

        logger.info(
            "run_daily_ingestion: COMPLETE market_id=%s as_of_date=%s "
            "instruments=%d/%d returns=%d volatility=%d",
            market_id,
            as_of_date,
            instruments_received,
            len(instruments),
            returns_count,
            vol_count,
        )

        return IngestionResult(
            market_id=market_id,
            as_of_date=as_of_date,
            status=IngestionStatus.COMPLETE,
            instruments_received=instruments_received,
            instruments_expected=len(instruments),
        )

    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {exc}"
        logger.exception(
            "run_daily_ingestion: FAILED market_id=%s as_of_date=%s: %s",
            market_id,
            as_of_date,
            error_msg,
        )

        update_ingestion_status(
            db_manager,
            status_id,
            IngestionStatus.FAILED,
            0,
            error_message=error_msg,
        )

        return IngestionResult(
            market_id=market_id,
            as_of_date=as_of_date,
            status=IngestionStatus.FAILED,
            instruments_received=0,
            instruments_expected=len(instruments),
            error_message=error_msg,
        )


def is_data_ready_for_market(
    db_manager: DatabaseManager,
    market_id: str,
    as_of_date: date,
    *,
    min_coverage: float = 0.95,
) -> bool:
    """Check if data ingestion is complete and ready for processing.
    
    Args:
        db_manager: Database manager
        market_id: Market identifier
        as_of_date: Date to check
        min_coverage: Minimum fraction of instruments that must have data (0.0-1.0)
    
    Returns:
        True if data is ready (ingestion complete with sufficient coverage)
    """
    status = get_ingestion_status(db_manager, market_id, as_of_date)
    
    if status != IngestionStatus.COMPLETE:
        return False

    # Check coverage
    sql = """
        SELECT instruments_received, instruments_expected
        FROM data_ingestion_status
        WHERE market_id = %s AND as_of_date = %s
    """

    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (market_id, as_of_date))
            row = cursor.fetchone()
        finally:
            cursor.close()

    if not row:
        return False

    received, expected = row
    if expected == 0:
        return True

    coverage = received / expected
    return coverage >= min_coverage


__all__ = [
    "IngestionStatus",
    "IngestionResult",
    "run_daily_ingestion",
    "is_data_ready_for_market",
    "get_ingestion_status",
    "compute_returns_and_volatility",
]
