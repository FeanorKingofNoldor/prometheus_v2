"""Sector factor backfill from returns_daily.

This module computes simple **sector factors** and per-instrument
exposures using existing `returns_daily` data and the `issuers` sector
classification.

For a given equity market and date range it populates:

- `factors_daily` with one factor per sector, e.g. `SECTOR_TECH`.
- `instrument_factors_daily` with exposure 1.0 for instruments in that
  sector on each date where they have returns.

The factor value on each date is the equal-weighted average of `ret_1d`
across all instruments in the sector that have non-null returns.

The goal is to provide a basic but real multi-factor structure on top of
which the Portfolio & Risk Engine can compute factor-based volatility.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Tuple

from psycopg2.extras import Json

from prometheus.core.database import DatabaseManager, get_db_manager
from prometheus.core.logging import get_logger


logger = get_logger(__name__)


@dataclass(frozen=True)
class SectorFactorBackfillConfig:
    """Configuration for sector factor backfill.

    Attributes:
        market_id: Logical market identifier (e.g. "US_EQ").
        factor_prefix: Prefix used when constructing factor_ids
            (e.g. "SECTOR" → "SECTOR_TECH").
        start_date: Inclusive start date for the backfill.
        end_date: Inclusive end date for the backfill.
    """

    market_id: str
    factor_prefix: str
    start_date: date
    end_date: date


def _load_instrument_sectors(db_manager: DatabaseManager, market_id: str) -> Dict[str, str]:
    """Return mapping instrument_id -> sector for a given market.

    Sector is derived from the `issuers` table when available and
    defaults to "UNKNOWN" when missing. We include all instruments in the
    market regardless of status so that historical instruments are
    covered as long as they remain present in `instruments`.
    """

    sql = """
        SELECT i.instrument_id,
               COALESCE(u.sector, 'UNKNOWN') AS sector
        FROM instruments AS i
        LEFT JOIN issuers AS u ON u.issuer_id = i.issuer_id
        WHERE i.market_id = %s
          AND i.asset_class = 'EQUITY'
    """

    mapping: Dict[str, str] = {}
    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (market_id,))
            for instrument_id, sector in cursor.fetchall():
                if not instrument_id:
                    continue
                mapping[str(instrument_id)] = str(sector or "UNKNOWN")
        finally:
            cursor.close()

    logger.info(
        "Sector factor backfill: loaded %d instruments with sector classification for market_id=%s",
        len(mapping),
        market_id,
    )
    return mapping


def _load_returns(
    db_manager: DatabaseManager,
    *,
    start_date: date,
    end_date: date,
) -> List[Tuple[date, str, float]]:
    """Return (trade_date, instrument_id, ret_1d) rows from returns_daily.

    We intentionally do **not** filter by market here; `returns_daily`
    currently contains only the US_EQ equity universe. If/when multiple
    markets are present, this helper can be extended to join against a
    historical instruments table or a mapping keyed by market_id.
    """

    sql = """
        SELECT r.trade_date, r.instrument_id, r.ret_1d
        FROM returns_daily AS r
        WHERE r.trade_date BETWEEN %s AND %s
        ORDER BY r.trade_date, r.instrument_id
    """

    with db_manager.get_historical_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (start_date, end_date))
            rows = cursor.fetchall()
        finally:
            cursor.close()

    return [
        (trade_date, str(instrument_id), float(ret_1d))
        for trade_date, instrument_id, ret_1d in rows
    ]


def _normalise_sector_name(sector: str) -> str:
    """Normalise a sector label into a compact identifier.

    The output is uppercased, non-alphanumeric characters are replaced by
    underscores, and consecutive underscores are collapsed. The result is
    truncated to 32 characters to keep `factor_id` within the 64-char
    limit alongside the prefix.
    """

    if not sector:
        return "UNKNOWN"
    s = sector.upper()
    cleaned_chars: List[str] = []
    prev_us = False
    for ch in s:
        if ch.isalnum():
            cleaned_chars.append(ch)
            prev_us = False
        else:
            if not prev_us:
                cleaned_chars.append("_")
                prev_us = True
    cleaned = "".join(cleaned_chars).strip("_")
    if not cleaned:
        cleaned = "UNKNOWN"
    return cleaned[:32]


def backfill_sector_factors(
    *,
    config: SectorFactorBackfillConfig,
    db_manager: DatabaseManager | None = None,
) -> Tuple[int, int]:
    """Backfill sector factors and exposures over a date range.

    Returns a tuple ``(num_factor_rows, num_exposure_rows)`` giving the
    number of rows attempted to be written into `factors_daily` and
    `instrument_factors_daily` respectively. Inserts are idempotent via
    `ON CONFLICT DO NOTHING`.
    """

    db = db_manager or get_db_manager()

    instrument_to_sector = _load_instrument_sectors(db, config.market_id)
    if not instrument_to_sector:
        logger.warning(
            "backfill_sector_factors: no instruments found for market_id=%s; nothing to do",
            config.market_id,
        )
        return 0, 0

    rows = _load_returns(
        db,
        start_date=config.start_date,
        end_date=config.end_date,
    )
    if not rows:
        logger.warning(
            "backfill_sector_factors: no returns_daily rows in %s→%s",
            config.start_date,
            config.end_date,
        )
        return 0, 0

    # Group returns by (trade_date, sector).
    by_date_sector: Dict[date, Dict[str, List[Tuple[str, float]]]] = {}
    for trade_date, instrument_id, ret_1d in rows:
        if ret_1d is None:  # defensive; schema is non-null
            continue
        sector = instrument_to_sector.get(instrument_id)
        if sector is None:
            continue
        by_date_sector.setdefault(trade_date, {}).setdefault(sector, []).append(
            (instrument_id, ret_1d)
        )

    if not by_date_sector:
        logger.warning("backfill_sector_factors: no sector-mapped returns; nothing to do")
        return 0, 0

    sql_factor = """
        INSERT INTO factors_daily (factor_id, trade_date, value, metadata)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (factor_id, trade_date) DO NOTHING
    """

    sql_exposure = """
        INSERT INTO instrument_factors_daily (instrument_id, trade_date, factor_id, exposure)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (instrument_id, trade_date, factor_id) DO NOTHING
    """

    factor_rows = 0
    exposure_rows = 0

    with db.get_historical_connection() as conn:
        cursor = conn.cursor()
        try:
            for trade_date, sectors in by_date_sector.items():
                if not sectors:
                    continue
                for sector, inst_rets in sectors.items():
                    if not inst_rets:
                        continue
                    values = [r for _inst, r in inst_rets]
                    mean_ret = sum(values) / float(len(values))

                    sector_norm = _normalise_sector_name(sector)
                    factor_id = f"{config.factor_prefix}_{sector_norm}"[:64]
                    metadata = {
                        "source": "derived_sector_mean",
                        "market_id": config.market_id,
                        "sector": sector,
                    }

                    cursor.execute(
                        sql_factor,
                        (factor_id, trade_date, mean_ret, Json(metadata)),
                    )
                    factor_rows += 1

                    for instrument_id, _ret in inst_rets:
                        cursor.execute(
                            sql_exposure,
                            (instrument_id, trade_date, factor_id, 1.0),
                        )
                        exposure_rows += 1

            conn.commit()
        finally:
            cursor.close()

    logger.info(
        "backfill_sector_factors: wrote %d factor rows and %d exposure rows for market_id=%s",
        factor_rows,
        exposure_rows,
        config.market_id,
    )
    return factor_rows, exposure_rows
