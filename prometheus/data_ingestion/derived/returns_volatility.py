"""Derived daily returns and volatility from ``prices_daily``.

This module computes:

- 1/5/21-day simple returns into ``returns_daily``.
- 21/63-day realised volatility (of log returns) into ``volatility_daily``.

The calculations are performed per instrument. For idempotence we
delete any existing rows for the target instrument and (optional) date
range before inserting new ones.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np

from prometheus.core.database import DatabaseManager, get_db_manager
from prometheus.core.logging import get_logger
from prometheus.data.reader import DataReader
from prometheus.data.types import ReturnsRecord, VolatilityRecord
from prometheus.data.writer import DataWriter


logger = get_logger(__name__)


@dataclass
class DerivedStatsResult:
    """Summary of derived data written for a single instrument."""

    instrument_id: str
    returns_rows: int
    volatility_rows: int


def _get_price_date_range(
    db_manager: DatabaseManager,
    instrument_id: str,
) -> Optional[Tuple[date, date]]:
    """Return (min_date, max_date) for prices of an instrument, or None."""

    sql = """
        SELECT MIN(trade_date), MAX(trade_date)
        FROM prices_daily
        WHERE instrument_id = %s
    """
    with db_manager.get_historical_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (instrument_id,))
            row = cursor.fetchone()
        finally:
            cursor.close()

    if not row or row[0] is None or row[1] is None:
        return None

    return row[0], row[1]


def _delete_existing_derived(
    db_manager: DatabaseManager,
    instrument_id: str,
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> None:
    """Delete existing returns/vol rows for an instrument/date range."""

    with db_manager.get_historical_connection() as conn:
        cursor = conn.cursor()
        try:
            if start_date is None and end_date is None:
                cursor.execute(
                    "DELETE FROM returns_daily WHERE instrument_id = %s",
                    (instrument_id,),
                )
                cursor.execute(
                    "DELETE FROM volatility_daily WHERE instrument_id = %s",
                    (instrument_id,),
                )
            else:
                if start_date is None:
                    start_date = date.min
                if end_date is None:
                    end_date = date.max
                cursor.execute(
                    """
                    DELETE FROM returns_daily
                    WHERE instrument_id = %s
                      AND trade_date BETWEEN %s AND %s
                    """,
                    (instrument_id, start_date, end_date),
                )
                cursor.execute(
                    """
                    DELETE FROM volatility_daily
                    WHERE instrument_id = %s
                      AND trade_date BETWEEN %s AND %s
                    """,
                    (instrument_id, start_date, end_date),
                )
            conn.commit()
        finally:
            cursor.close()


def compute_returns_and_volatility_for_instrument(
    instrument_id: str,
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db_manager: Optional[DatabaseManager] = None,
) -> DerivedStatsResult:
    """Compute returns and volatility for a single instrument.

    If ``start_date`` / ``end_date`` are omitted, the full price history
    available in ``prices_daily`` is used. Existing rows in
    ``returns_daily`` and ``volatility_daily`` for the relevant
    instrument/date range are deleted before inserting new values.
    """

    db_manager = db_manager or get_db_manager()
    price_range = _get_price_date_range(db_manager, instrument_id)
    if price_range is None:
        logger.info(
            "No prices found for instrument %s; skipping derived computations",
            instrument_id,
        )
        return DerivedStatsResult(instrument_id=instrument_id, returns_rows=0, volatility_rows=0)

    min_date, max_date = price_range

    # Default to full price range when explicit bounds are not provided.
    start_date = start_date or min_date
    end_date = end_date or max_date

    if start_date < min_date:
        start_date = min_date
    if end_date > max_date:
        end_date = max_date

    if start_date > end_date:
        return DerivedStatsResult(instrument_id=instrument_id, returns_rows=0, volatility_rows=0)

    logger.info(
        "Computing derived returns/vol for %s in [%s, %s] (price range [%s, %s])",
        instrument_id,
        start_date,
        end_date,
        min_date,
        max_date,
    )

    reader = DataReader(db_manager=db_manager)
    writer = DataWriter(db_manager=db_manager)

    # Read full available history to support lookback windows.
    df = reader.read_prices([instrument_id], min_date, max_date)
    if df.empty:
        return DerivedStatsResult(instrument_id=instrument_id, returns_rows=0, volatility_rows=0)

    df_sorted = df.sort_values(["trade_date"]).reset_index(drop=True)
    prices = df_sorted["adjusted_close"].astype(float).to_numpy()
    dates = df_sorted["trade_date"].to_numpy()

    n = prices.shape[0]
    if n < 64:
        logger.warning(
            "Not enough history (%d rows) to compute 63-day volatility for %s",
            n,
            instrument_id,
        )

    # Simple daily returns based on adjusted close.
    simple_rets = np.empty_like(prices, dtype=float)
    simple_rets[0] = np.nan
    simple_rets[1:] = prices[1:] / prices[:-1] - 1.0

    def _k_day_return(k: int) -> np.ndarray:
        out = np.full_like(prices, np.nan, dtype=float)
        if n > k:
            out[k:] = prices[k:] / prices[:-k] - 1.0
        return out

    ret_1d = simple_rets
    ret_5d = _k_day_return(5)
    ret_21d = _k_day_return(21)

    # Log returns for volatility calculations (daily, not annualised).
    log_rets = np.zeros_like(prices, dtype=float)
    log_rets[1:] = np.log(prices[1:] / prices[:-1])

    vol_21d = np.full_like(prices, np.nan, dtype=float)
    vol_63d = np.full_like(prices, np.nan, dtype=float)

    for i in range(n):
        if i >= 20:  # 21 observations
            window = log_rets[i - 20 : i + 1]
            if window.size > 1:
                vol_21d[i] = float(np.std(window[1:], ddof=1))
        if i >= 62:  # 63 observations
            window = log_rets[i - 62 : i + 1]
            if window.size > 1:
                vol_63d[i] = float(np.std(window[1:], ddof=1))

    # Delete any existing derived rows for the target range.
    _delete_existing_derived(db_manager, instrument_id, start_date=start_date, end_date=end_date)

    returns_records: List[ReturnsRecord] = []
    volatility_records: List[VolatilityRecord] = []

    for dt, r1, r5, r21, v21, v63 in zip(dates, ret_1d, ret_5d, ret_21d, vol_21d, vol_63d):
        if dt < start_date or dt > end_date:
            continue

        # Only write rows once we have the necessary lookback history.
        if not (np.isfinite(r1) and np.isfinite(r5) and np.isfinite(r21)):
            continue

        returns_records.append(
            ReturnsRecord(
                instrument_id=instrument_id,
                trade_date=dt,
                ret_1d=float(r1),
                ret_5d=float(r5),
                ret_21d=float(r21),
                metadata=None,
            )
        )

        if np.isfinite(v21) and np.isfinite(v63):
            volatility_records.append(
                VolatilityRecord(
                    instrument_id=instrument_id,
                    trade_date=dt,
                    vol_21d=float(v21),
                    vol_63d=float(v63),
                    metadata=None,
                )
            )

    if returns_records:
        writer.write_returns(returns_records)
    if volatility_records:
        writer.write_volatility(volatility_records)

    logger.info(
        "Derived returns/vol for %s: %d returns rows, %d volatility rows",
        instrument_id,
        len(returns_records),
        len(volatility_records),
    )

    return DerivedStatsResult(
        instrument_id=instrument_id,
        returns_rows=len(returns_records),
        volatility_rows=len(volatility_records),
    )


def compute_returns_and_volatility_for_instruments(
    instrument_ids: Sequence[str],
    *,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db_manager: Optional[DatabaseManager] = None,
) -> List[DerivedStatsResult]:
    """Batch variant of :func:`compute_returns_and_volatility_for_instrument`."""

    db_manager = db_manager or get_db_manager()
    results: List[DerivedStatsResult] = []

    for instrument_id in instrument_ids:
        try:
            result = compute_returns_and_volatility_for_instrument(
                instrument_id,
                start_date=start_date,
                end_date=end_date,
                db_manager=db_manager,
            )
            results.append(result)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception(
                "Failed to compute returns/vol for %s: %s",
                instrument_id,
                exc,
            )

    return results


__all__ = [
    "DerivedStatsResult",
    "compute_returns_and_volatility_for_instrument",
    "compute_returns_and_volatility_for_instruments",
]
