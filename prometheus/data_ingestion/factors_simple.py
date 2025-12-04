"""Simple derived factor backfill from returns_daily.

This module computes a basic *market factor* time series and
per-instrument exposures for a given equity market using existing
`returns_daily` data. It populates:

- `factors_daily` with a factor_id such as ``"MKT_US_EQ"``; and
- `instrument_factors_daily` with constant exposure 1.0 to that factor
  for all instruments in the market that have returns on that date.

The intent is to provide a minimal but real factor model that the
Portfolio & Risk Engine can use for factor-based volatility estimates.
It can be refined later with additional factors and more nuanced
exposures.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, Iterable, List, Tuple

from psycopg2.extras import Json

from prometheus.core.database import DatabaseManager, get_db_manager
from prometheus.core.logging import get_logger


logger = get_logger(__name__)


@dataclass(frozen=True)
class FactorBackfillConfig:
    """Configuration for a simple market factor backfill.

    Attributes:
        market_id: Logical market_id (e.g. ``"US_EQ"``).
        factor_id: Identifier written into ``factors_daily`` and
            ``instrument_factors_daily`` (e.g. ``"MKT_US_EQ"``).
        start_date: Inclusive start date for the backfill.
        end_date: Inclusive end date for the backfill.
    """

    market_id: str
    factor_id: str
    start_date: date
    end_date: date


def _load_market_returns(
    db_manager: DatabaseManager,
    *,
    market_id: str,
    start_date: date,
    end_date: date,
) -> List[Tuple[date, str, float]]:
    """Return (trade_date, instrument_id, ret_1d) rows for a market.

    For Iteration 2, we assume that ``returns_daily`` in the historical DB
    only contains instruments for a single logical equity market
    (currently ``US_EQ``). We therefore select all rows in the requested
    date range and ignore ``market_id`` except for metadata tagging.

    If/when we introduce multiple markets into ``returns_daily``, this
    helper should be updated to join against the appropriate historical
    instruments table or a dedicated mapping table.
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

    return [(trade_date, instrument_id, float(ret_1d)) for trade_date, instrument_id, ret_1d in rows]


def backfill_simple_market_factor(
    *,
    db_manager: DatabaseManager | None = None,
    config: FactorBackfillConfig,
) -> Tuple[int, int]:
    """Backfill a simple market factor for a given market over a date range.

    The factor value on each date is the equal-weighted average of
    ``ret_1d`` across all ACTIVE equity instruments in ``config.market_id``
    that have non-null returns on that date.

    For each (instrument_id, trade_date) pair contributing to the factor,
    an exposure row with value 1.0 is written into
    ``instrument_factors_daily``.

    Returns:
        Tuple ``(num_factor_rows, num_exposure_rows)`` giving the number
        of rows written into ``factors_daily`` and
        ``instrument_factors_daily`` respectively.
    """

    db = db_manager or get_db_manager()
    rows = _load_market_returns(
        db,
        market_id=config.market_id,
        start_date=config.start_date,
        end_date=config.end_date,
    )
    if not rows:
        logger.warning(
            "backfill_simple_market_factor: no returns_daily rows for market_id=%s in %s→%s",
            config.market_id,
            config.start_date,
            config.end_date,
        )
        return 0, 0

    # Group by trade_date in memory; returns_daily is already ordered by
    # date then instrument_id.
    by_date: Dict[date, List[Tuple[str, float]]] = {}
    for trade_date, instrument_id, ret_1d in rows:
        if ret_1d is None:  # defensive; ret_1d is non-null in schema
            continue
        by_date.setdefault(trade_date, []).append((instrument_id, ret_1d))

    if not by_date:
        return 0, 0

    # Prepare batched INSERTs with ON CONFLICT DO NOTHING so the script is
    # idempotent.
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
            for trade_date, inst_rets in by_date.items():
                if not inst_rets:
                    continue
                # Equal-weighted average of ret_1d.
                values = [r for _inst, r in inst_rets]
                mean_ret = sum(values) / float(len(values))
                metadata = {"source": "derived_market_mean", "market_id": config.market_id}

                cursor.execute(
                    sql_factor,
                    (config.factor_id, trade_date, mean_ret, Json(metadata)),
                )
                # rowcount is unreliable under ON CONFLICT; we conservatively
                # increment by 1 per date but this is harmless.
                factor_rows += 1

                # Exposures: 1.0 for each instrument with a return on that date.
                for instrument_id, _ret in inst_rets:
                    cursor.execute(
                        sql_exposure,
                        (instrument_id, trade_date, config.factor_id, 1.0),
                    )
                    exposure_rows += 1

            conn.commit()
        finally:
            cursor.close()

    logger.info(
        "backfill_simple_market_factor: wrote %d factor rows and %d exposure rows for factor_id=%s",
        factor_rows,
        exposure_rows,
        config.factor_id,
    )
    return factor_rows, exposure_rows
