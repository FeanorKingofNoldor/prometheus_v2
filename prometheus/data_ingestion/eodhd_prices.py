"""Prometheus v2 – EODHD price ingestion helpers.

This module contains small helper functions that:

- Fetch end‑of‑day OHLCV data from EODHD via :class:`EodhdClient`.
- Convert the result into :class:`prometheus.data.types.PriceBar` records.
- Persist them into ``prices_daily`` using :class:`prometheus.data.writer.DataWriter`.

The goal is to keep ingestion logic thin and composable so that higher‑
level orchestration (cron jobs, DAGs, or the engine pipeline) can call
these helpers without knowing about HTTP or provider‑specific
conventions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable, Mapping

from prometheus.core.logging import get_logger
from prometheus.data.types import PriceBar
from prometheus.data.writer import DataWriter

from prometheus.data_ingestion.eodhd_client import EodhdBar, EodhdClient


logger = get_logger(__name__)


@dataclass
class EodhdIngestionResult:
    """Summary of an ingestion run for a single instrument."""

    instrument_id: str
    eodhd_symbol: str
    bars_written: int


def _bars_to_price_bars(
    instrument_id: str,
    currency: str,
    eodhd_bars: Iterable[EodhdBar],
) -> list[PriceBar]:
    """Convert EODHD bars into :class:`PriceBar` objects."""

    price_bars: list[PriceBar] = []
    for bar in eodhd_bars:
        price_bars.append(
            PriceBar(
                instrument_id=instrument_id,
                trade_date=bar.trade_date,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                adjusted_close=bar.adjusted_close,
                volume=bar.volume,
                currency=currency,
                metadata={"source": "eodhd"},
            )
        )
    return price_bars


def ingest_eodhd_prices_for_instrument(
    instrument_id: str,
    eodhd_symbol: str,
    start_date: date,
    end_date: date,
    *,
    currency: str = "USD",
    client: EodhdClient,
    writer: DataWriter,
) -> EodhdIngestionResult:
    """Fetch and persist prices for a single instrument.

    This function is deliberately dependency‑injected: callers must
    provide an :class:`EodhdClient` and :class:`DataWriter`. This keeps
    unit tests free from network and database access while allowing
    higher‑level scripts to use shared client/DB instances.
    """

    logger.info(
        "ingest_eodhd_prices_for_instrument: instrument_id=%s symbol=%s %s→%s",
        instrument_id,
        eodhd_symbol,
        start_date,
        end_date,
    )

    bars = client.get_eod_prices(eodhd_symbol, start_date, end_date)
    price_bars = _bars_to_price_bars(instrument_id, currency, bars)

    if price_bars:
        writer.write_prices(price_bars)

    logger.info(
        "ingest_eodhd_prices_for_instrument: wrote %d bars for %s (%s)",
        len(price_bars),
        instrument_id,
        eodhd_symbol,
    )

    return EodhdIngestionResult(
        instrument_id=instrument_id,
        eodhd_symbol=eodhd_symbol,
        bars_written=len(price_bars),
    )


def ingest_eodhd_prices_for_instruments(
    mapping: Mapping[str, str],
    start_date: date,
    end_date: date,
    *,
    default_currency: str = "USD",
    currency_by_instrument: Mapping[str, str] | None = None,
    client: EodhdClient,
    writer: DataWriter,
) -> list[EodhdIngestionResult]:
    """Ingest prices for multiple instruments using a shared client/writer.

    Parameters
    ----------
    mapping:
        Mapping from ``instrument_id`` → ``eodhd_symbol`` (e.g. ``"AAPL" →
        "AAPL.US"``). How this mapping is derived (from ``instruments``
        metadata, config files, etc.) is left to higher‑level orchestration.
    start_date, end_date:
        Inclusive date range for which to request prices.
    default_currency:
        Currency to use when ``currency_by_instrument`` does not specify
        one for a given instrument.
    currency_by_instrument:
        Optional mapping from ``instrument_id`` → currency code.
    client, writer:
        Shared :class:`EodhdClient` and :class:`DataWriter` instances.
    """

    results: list[EodhdIngestionResult] = []

    for instrument_id, eodhd_symbol in mapping.items():
        currency = (
            currency_by_instrument.get(instrument_id, default_currency)
            if currency_by_instrument is not None
            else default_currency
        )
        try:
            result = ingest_eodhd_prices_for_instrument(
                instrument_id=instrument_id,
                eodhd_symbol=eodhd_symbol,
                start_date=start_date,
                end_date=end_date,
                currency=currency,
                client=client,
                writer=writer,
            )
            results.append(result)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception(
                "Failed to ingest EODHD prices for %s (%s): %s",
                instrument_id,
                eodhd_symbol,
                exc,
            )

    return results


__all__ = [
    "EodhdIngestionResult",
    "ingest_eodhd_prices_for_instrument",
    "ingest_eodhd_prices_for_instruments",
]
