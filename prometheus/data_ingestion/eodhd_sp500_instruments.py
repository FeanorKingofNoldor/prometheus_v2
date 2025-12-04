"""EODHD S&P 500 instrument and issuer ingestion.

This module downloads the S&P 500 index fundamentals from EODHD and
converts the `Components` and `HistoricalTickerComponents` sections into
Prometheus `issuers` and `instruments` rows for the US_EQ market.

Design goals:

- **Real data only**: we rely on EODHD's official S&P 500 constituents
  (current + historical) instead of hard-coded lists.
- **Idempotent**: running the ingestion multiple times should be safe;
  existing rows are upserted where appropriate.
- **Separation of concerns**: this module only handles runtime schema
  (`markets`, `issuers`, `instruments`). Price history is handled by the
  existing EODHD price ingestion.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, Iterable, List, Tuple

from psycopg2.extras import Json

from prometheus.core.database import DatabaseManager, get_db_manager
from prometheus.core.logging import get_logger
from prometheus.data_ingestion.eodhd_client import EodhdClient


logger = get_logger(__name__)


@dataclass(frozen=True)
class Sp500Constituent:
    """Single S&P 500 constituent (merged current + historical info).

    Attributes
    ----------
    code:
        Ticker code as used by EODHD fundamentals (e.g. "AAPL"). The
        corresponding EODHD EOD symbol is typically ``"{code}.US"``.
    name:
        Company name.
    exchange:
        Exchange code from EODHD (e.g. "US").
    sector, industry:
        GICS-style sector/industry (if available).
    start_date, end_date:
        Dates when the ticker entered and left the index. ``end_date``
        is ``None`` for currently active members.
    is_active_now:
        1 if the ticker is currently in the index, 0 otherwise.
    is_delisted:
        1 if the ticker is delisted in EODHD's universe.
    """

    code: str
    name: str
    exchange: str
    sector: str | None
    industry: str | None
    start_date: date | None
    end_date: date | None
    is_active_now: int
    is_delisted: int


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def fetch_sp500_constituents(client: EodhdClient) -> List[Sp500Constituent]:
    """Fetch S&P 500 constituents (current + historical) from EODHD.

    This calls ``/fundamentals/GSPC.INDX`` and combines data from
    ``Components`` (current membership with sector/industry) and
    ``HistoricalTickerComponents`` (membership episodes).
    """

    logger.info("Fetching S&P 500 constituents from EODHD fundamentals API")

    # We use the low-level HTTP session of EodhdClient because the
    # existing client currently only wraps the /eod endpoint. This keeps
    # the price client stable while extending functionality here.
    url = f"{client._base_url}/fundamentals/GSPC.INDX"  # type: ignore[attr-defined]
    params = {"api_token": client._api_token, "fmt": "json"}  # type: ignore[attr-defined]

    import requests  # imported locally to avoid hard dependency in client module

    try:
        resp = requests.get(url, params=params, timeout=30)
    except Exception as exc:  # pragma: no cover - network errors
        logger.error("Failed to fetch GSPC.INDX fundamentals from EODHD: %s", exc)
        raise

    if resp.status_code != 200:
        body_preview = resp.text[:500]
        logger.error(
            "EODHD fundamentals request failed: status=%s body=%s",
            resp.status_code,
            body_preview,
        )
        raise RuntimeError(
            f"EODHD fundamentals /fundamentals/GSPC.INDX failed with status {resp.status_code}"
        )

    payload = resp.json()

    components_raw: Dict[str, dict] = payload.get("Components", {}) or {}
    hist_raw: Dict[str, dict] = payload.get("HistoricalTickerComponents", {}) or {}

    # Map current components by code so we can enrich historical entries
    # with sector/industry when available.
    current_by_code: Dict[str, dict] = {}
    for idx, comp in components_raw.items():
        try:
            code = str(comp["Code"]).strip()
        except KeyError:
            logger.warning("Skipping malformed Components[%s]: missing Code", idx)
            continue
        current_by_code[code] = comp

    constituents: List[Sp500Constituent] = []
    for idx, hist in hist_raw.items():
        try:
            code = str(hist["Code"]).strip()
            name = str(hist.get("Name") or "").strip() or code
            start = _parse_date(hist.get("StartDate"))
            end = _parse_date(hist.get("EndDate"))
            is_active = int(hist.get("IsActiveNow", 0) or 0)
            is_delisted = int(hist.get("IsDelisted", 0) or 0)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Skipping malformed HistoricalTickerComponents[%s]: %s", idx, exc)
            continue

        comp_meta = current_by_code.get(code, {})
        exchange = str(comp_meta.get("Exchange", "US"))
        sector = comp_meta.get("Sector")
        industry = comp_meta.get("Industry")

        constituents.append(
            Sp500Constituent(
                code=code,
                name=name,
                exchange=exchange,
                sector=sector,
                industry=industry,
                start_date=start,
                end_date=end,
                is_active_now=is_active,
                is_delisted=is_delisted,
            )
        )

    logger.info("Fetched %d historical S&P 500 constituents", len(constituents))
    return constituents


# ---------------------------------------------------------------------------
# Persistence into markets / issuers / instruments
# ---------------------------------------------------------------------------


def _ensure_us_eq_market(db: DatabaseManager) -> None:
    """Ensure the US_EQ market row exists in ``markets``.

    If the row already exists, this is a no-op.
    """

    sql = """
        INSERT INTO markets (market_id, name, region, timezone)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (market_id) DO NOTHING
    """
    with db.get_runtime_connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute(sql, ("US_EQ", "US Equity", "US", "America/New_York"))
            conn.commit()
        finally:
            cur.close()


def upsert_sp500_instruments(
    constituents: Iterable[Sp500Constituent],
    *,
    db_manager: DatabaseManager | None = None,
) -> Tuple[int, int]:
    """Create or update issuers and instruments for S&P 500 constituents.

    Returns a tuple ``(issuers_written, instruments_written)``.
    """

    db = db_manager or get_db_manager()
    _ensure_us_eq_market(db)

    issuer_sql = """
        INSERT INTO issuers (
            issuer_id,
            issuer_type,
            name,
            country,
            sector,
            industry,
            metadata
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (issuer_id) DO UPDATE SET
            name = EXCLUDED.name,
            country = EXCLUDED.country,
            sector = EXCLUDED.sector,
            industry = EXCLUDED.industry,
            metadata = EXCLUDED.metadata
    """

    instrument_sql = """
        INSERT INTO instruments (
            instrument_id,
            issuer_id,
            market_id,
            asset_class,
            symbol,
            exchange,
            currency,
            status,
            metadata
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (instrument_id) DO UPDATE SET
            issuer_id = EXCLUDED.issuer_id,
            market_id = EXCLUDED.market_id,
            asset_class = EXCLUDED.asset_class,
            symbol = EXCLUDED.symbol,
            exchange = EXCLUDED.exchange,
            currency = EXCLUDED.currency,
            status = EXCLUDED.status,
            metadata = EXCLUDED.metadata
    """

    issuers_written = 0
    instruments_written = 0

    with db.get_runtime_connection() as conn:
        cur = conn.cursor()
        try:
            for c in constituents:
                # We scope issuers by ticker code for now. If multiple
                # share classes or listings appear, they can either share
                # an issuer_id explicitly later or use separate issuers.
                issuer_id = c.code

                issuer_metadata = {
                    "source": "eodhd",
                    "sp500": True,
                    "is_active_now": c.is_active_now,
                    "is_delisted": c.is_delisted,
                    "start_date": c.start_date.isoformat() if c.start_date else None,
                    "end_date": c.end_date.isoformat() if c.end_date else None,
                }

                cur.execute(
                    issuer_sql,
                    (
                        issuer_id,
                        "COMPANY",
                        c.name,
                        "US",
                        c.sector,
                        c.industry,
                        Json(issuer_metadata),
                    ),
                )
                issuers_written += 1

                instrument_id = f"{c.code}.US"
                instrument_metadata = {
                    "source": "eodhd",
                    "index": "SP500",
                }

                cur.execute(
                    instrument_sql,
                    (
                        instrument_id,
                        issuer_id,
                        "US_EQ",
                        "EQUITY",
                        c.code,
                        c.exchange,
                        "USD",
                        "ACTIVE",
                        Json(instrument_metadata),
                    ),
                )
                instruments_written += 1

            conn.commit()
        finally:
            cur.close()

    logger.info(
        "Upserted %d issuers and %d instruments for S&P 500 constituents",
        issuers_written,
        instruments_written,
    )
    return issuers_written, instruments_written


__all__ = [
    "Sp500Constituent",
    "fetch_sp500_constituents",
    "upsert_sp500_instruments",
]
