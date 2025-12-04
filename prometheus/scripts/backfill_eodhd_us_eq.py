"""Prometheus v2 – Backfill EODHD prices for US_EQ instruments.

This script discovers equity instruments in the runtime DB for the
`US_EQ` market and ingests end-of-day prices for each of them from
EODHD into the historical `prices_daily` table.

It is intended as a simple backfill driver so you can start with a small
subset of instruments (via `--limit`) and gradually increase coverage.

Examples
--------

    # Ingest up to 5 US_EQ instruments over a short window
    python -m prometheus.scripts.backfill_eodhd_us_eq \
        --from 2024-01-01 --to 2024-01-31 --limit 5

    # Ingest the next 5 instruments (using offset)
    python -m prometheus.scripts.backfill_eodhd_us_eq \
        --from 2024-01-01 --to 2024-01-31 --limit 5 --offset 5
"""

from __future__ import annotations

import argparse
from datetime import date
from typing import Dict, List, Optional, Tuple

from prometheus.core.database import get_db_manager, DatabaseManager
from prometheus.core.logging import get_logger
from prometheus.data.writer import DataWriter
from prometheus.data_ingestion.eodhd_client import EodhdClient
from prometheus.data_ingestion.eodhd_prices import (
    EodhdIngestionResult,
    ingest_eodhd_prices_for_instruments,
)


logger = get_logger(__name__)


def _parse_date(value: str) -> date:
    try:
        year, month, day = map(int, value.split("-"))
        return date(year, month, day)
    except Exception as exc:  # pragma: no cover - CLI validation
        raise argparse.ArgumentTypeError(f"Invalid date {value!r}, expected YYYY-MM-DD") from exc


def _load_us_eq_instruments(
    db_manager: DatabaseManager,
    *,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
) -> List[Tuple[str, str, str]]:
    """Return list of (instrument_id, symbol, currency) for US_EQ equities.

    Instruments are filtered by `market_id = 'US_EQ'`, `asset_class =
    'EQUITY'`, and `status = 'ACTIVE'`.
    """

    base_sql = """
        SELECT instrument_id, symbol, currency
        FROM instruments
        WHERE market_id = 'US_EQ'
          AND asset_class = 'EQUITY'
          AND status = 'ACTIVE'
        ORDER BY instrument_id
    """

    params: Tuple[object, ...] = ()
    if limit is not None:
        base_sql += " LIMIT %s"
        params += (limit,)
        if offset is not None:
            base_sql += " OFFSET %s"
            params += (offset,)

    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(base_sql, params or None)
            rows = cursor.fetchall()
        finally:
            cursor.close()

    return [(instrument_id, symbol, currency) for instrument_id, symbol, currency in rows]


def main(argv: Optional[list[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Backfill EODHD prices for US_EQ equities")

    parser.add_argument(
        "--from",
        dest="from_date",
        type=_parse_date,
        required=True,
        help="Start date (inclusive, YYYY-MM-DD)",
    )
    parser.add_argument(
        "--to",
        dest="to_date",
        type=_parse_date,
        required=True,
        help="End date (inclusive, YYYY-MM-DD)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of instruments to process (for incremental backfills)",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=None,
        help="Offset into the instrument list (used with --limit)",
    )
    parser.add_argument(
        "--suffix",
        type=str,
        default=".US",
        help="Suffix appended to instrument symbols when building EODHD symbols (default: .US)",
    )
    parser.add_argument(
        "--currency",
        type=str,
        default="USD",
        help="Default currency code for prices (used when instrument currency is NULL)",
    )

    args = parser.parse_args(argv)

    db_manager = get_db_manager()
    instruments = _load_us_eq_instruments(
        db_manager,
        limit=args.limit,
        offset=args.offset,
    )

    if not instruments:
        logger.info("No US_EQ instruments found matching the criteria")
        return

    logger.info("Loaded %d US_EQ instruments for backfill", len(instruments))

    mapping: Dict[str, str] = {}
    currency_by_instrument: Dict[str, str] = {}

    for instrument_id, symbol, currency in instruments:
        if not symbol:
            logger.warning("Instrument %s has empty symbol; skipping", instrument_id)
            continue
        eodhd_symbol = f"{symbol}{args.suffix}"
        mapping[instrument_id] = eodhd_symbol
        currency_by_instrument[instrument_id] = currency or args.currency

    if not mapping:
        logger.info("No instruments with valid symbols to ingest")
        return

    writer = DataWriter(db_manager=db_manager)
    client = EodhdClient()

    results: List[EodhdIngestionResult] = ingest_eodhd_prices_for_instruments(
        mapping=mapping,
        start_date=args.from_date,
        end_date=args.to_date,
        default_currency=args.currency,
        currency_by_instrument=currency_by_instrument,
        client=client,
        writer=writer,
    )

    total_bars = sum(r.bars_written for r in results)
    logger.info(
        "Backfill complete: %d instruments, %d bars written", len(results), total_bars
    )


if __name__ == "__main__":  # pragma: no cover - manual CLI entry
    main()
