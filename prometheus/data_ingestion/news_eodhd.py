"""Ingest news and headlines from EODHD into news_articles/news_links.

This module is the text analogue of :mod:`eodhd_prices` and
:mod:`eodhd_fundamentals`. It fetches news articles from the EODHD API,
normalises them, and writes them into the historical DB:

- ``news_articles``: one row per article with headline, body, timestamp,
  and metadata.
- ``news_links``: zero or more rows per article linking it to
  ``issuer_id`` / ``instrument_id``.

The goal is to provide a clean, idempotent ingestion layer that can be
backfilled from ~1997 onwards for the US equity universe, and then kept
up-to-date incrementally.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import requests
from psycopg2.extras import Json

from prometheus.core.database import DatabaseManager, get_db_manager
from prometheus.core.logging import get_logger
from prometheus.data_ingestion.eodhd_client import EodhdClient


logger = get_logger(__name__)


@dataclass(frozen=True)
class EodhdNewsArticle:
    """Normalised representation of a single EODHD news article."""

    external_id: str | None
    timestamp: datetime
    source: str | None
    language: str | None
    headline: str
    body: str | None
    symbols: Tuple[str, ...]
    raw: dict


def _parse_timestamp(value: str) -> datetime:
    """Parse EODHD timestamp strings.

    EODHD returns ISO-8601 style timestamps such as::

        "2024-01-02T13:45:00+00:00"
        "2024-01-02 13:45:00+00:00"
        "2024-01-02"

    We parse them using :func:`datetime.fromisoformat` when possible and
    normalise everything to *naive UTC* datetimes for storage.
    """

    v = value.strip()

    # Normalise trailing ``Z`` (UTC designator) to an explicit offset so
    # that ``fromisoformat`` can handle it.
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"

    # First try full ISO-8601 parsing, including timezone offsets.
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        # Fallbacks for unexpected formats: strip any time / offset and
        # try to interpret the leading portion as a date.
        date_part = v
        for sep in ("T", " "):
            if sep in v:
                date_part = v.split(sep, 1)[0]
                break
        try:
            dt = datetime.strptime(date_part, "%Y-%m-%d")
        except ValueError as exc:
            # Let the caller decide how to handle a truly malformed
            # timestamp; upstream we log and skip the row.
            raise ValueError(f"Unrecognised EODHD timestamp: {value!r}") from exc

    # Convert any timezone-aware datetime to naive UTC.
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)

    return dt


def fetch_news_for_symbol(
    client: EodhdClient,
    symbol: str,
    *,
    start_date: date,
    end_date: date,
) -> List[EodhdNewsArticle]:
    """Fetch news articles for a single EODHD symbol over a date range.

    This uses the EODHD ``/news`` endpoint. The exact response shape is
    vendor-defined, but in practice we expect a list of JSON objects with
    at least:

    - ``date``: timestamp string.
    - ``title`` or ``headline``.
    - ``content`` or ``text`` (optional body/summary).
    - ``source`` / ``language`` (optional metadata).
    - ``symbols`` / ``tickers``: list of associated tickers.
    """

    # We intentionally do not expose this lower-level HTTP call via
    # EodhdClient to avoid coupling this module to that client's public
    # surface. Instead, we re-use its base_url/api_token.
    base_url = client._base_url  # type: ignore[attr-defined]
    api_token = client._api_token  # type: ignore[attr-defined]

    params: Dict[str, str] = {
        "api_token": api_token,
        "fmt": "json",
        "s": symbol,
        "from": start_date.isoformat(),
        "to": end_date.isoformat(),
    }

    url = f"{base_url}/news"
    logger.info("EODHD news: GET %s params=%s", url, params)

    try:
        resp = requests.get(url, params=params, timeout=30)
    except Exception as exc:  # pragma: no cover - network
        logger.error("EODHD news request failed for %s: %s", symbol, exc)
        return []

    if resp.status_code != 200:
        logger.warning(
            "EODHD news request failed for %s: status=%s body=%s",
            symbol,
            resp.status_code,
            resp.text[:300],
        )
        return []

    try:
        payload = resp.json()
    except ValueError as exc:  # pragma: no cover - defensive
        logger.error("Failed to decode EODHD news JSON for %s: %s", symbol, exc)
        return []

    articles: List[EodhdNewsArticle] = []
    for raw in payload or []:
        try:
            ts_raw = raw.get("date") or raw.get("timestamp")
            if not ts_raw:
                continue
            ts = _parse_timestamp(ts_raw)

            headline = raw.get("title") or raw.get("headline") or ""
            if not headline:
                # Skip articles without a meaningful title.
                continue

            body = raw.get("content") or raw.get("text") or None
            source = raw.get("source") or raw.get("provider")
            language = raw.get("language") or raw.get("lang")

            symbols_field = raw.get("symbols") or raw.get("tickers") or []
            if isinstance(symbols_field, str):
                symbols = tuple(s.strip() for s in symbols_field.split(",") if s.strip())
            elif isinstance(symbols_field, (list, tuple)):
                symbols = tuple(str(s).strip() for s in symbols_field if str(s).strip())
            else:
                symbols = (symbol,)

            external_id = (
                str(raw.get("id"))
                if raw.get("id") is not None
                else None
            )

            articles.append(
                EodhdNewsArticle(
                    external_id=external_id,
                    timestamp=ts,
                    source=source,
                    language=language,
                    headline=headline,
                    body=body,
                    symbols=symbols,
                    raw=raw,
                )
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Skipping malformed EODHD news row for %s: %s", symbol, exc)
            continue

    logger.info("Fetched %d EODHD news articles for %s", len(articles), symbol)
    return articles


@dataclass(frozen=True)
class NewsIngestionConfig:
    """Configuration for a bulk news ingestion run."""

    start_date: date
    end_date: date
    market_id: str = "US_EQ"


def _load_instrument_symbol_mapping(
    db: DatabaseManager,
    *,
    market_id: str,
) -> Dict[str, str]:
    """Return mapping instrument_id -> vendor symbol (e.g. ``AAPL.US``).

    We currently derive this from the runtime ``instruments`` table by
    assuming that ``symbol`` already matches the EODHD symbol root and
    appending ``.US`` for US_EQ. This mirrors the price ingestion logic
    and can be generalised later.
    """

    sql = """
        SELECT instrument_id, symbol
        FROM instruments
        WHERE market_id = %s
          AND asset_class = 'EQUITY'
          AND status = 'ACTIVE'
        ORDER BY instrument_id
    """

    mapping: Dict[str, str] = {}

    with db.get_runtime_connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute(sql, (market_id,))
            for instrument_id, symbol in cur.fetchall():
                if not symbol:
                    continue
                if market_id == "US_EQ" and not symbol.endswith(".US"):
                    vendor_symbol = f"{symbol}.US"
                else:
                    vendor_symbol = symbol
                mapping[instrument_id] = vendor_symbol
        finally:
            cur.close()

    logger.info(
        "Loaded %d instruments for market_id=%s for EODHD news ingestion",
        len(mapping),
        market_id,
    )
    return mapping


def _build_symbol_to_instruments(
    instrument_to_symbol: Mapping[str, str],
) -> Dict[str, List[str]]:
    """Invert mapping to vendor_symbol -> [instrument_id, ...]."""

    inv: Dict[str, List[str]] = {}
    for instrument_id, symbol in instrument_to_symbol.items():
        inv.setdefault(symbol, []).append(instrument_id)
    return inv


def _load_issuer_ids_for_instruments(
    db: DatabaseManager,
    instrument_ids: Sequence[str],
) -> Dict[str, str]:
    """Return mapping instrument_id -> issuer_id for a batch of instruments."""

    if not instrument_ids:
        return {}

    sql = """
        SELECT instrument_id, issuer_id
        FROM instruments
        WHERE instrument_id = ANY(%s)
    """

    mapping: Dict[str, str] = {}
    with db.get_runtime_connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute(sql, (list(instrument_ids),))
            for instrument_id, issuer_id in cur.fetchall():
                mapping[instrument_id] = issuer_id
        finally:
            cur.close()

    return mapping


def _upsert_news_articles_and_links(
    db: DatabaseManager,
    *,
    articles: Iterable[EodhdNewsArticle],
    symbol_to_instruments: Mapping[str, List[str]],
    issuer_by_instrument: Mapping[str, str],
) -> Tuple[int, int]:
    """Insert articles into news_articles and links into news_links.

    Idempotent w.r.t. (source, timestamp, headline): if an article with
    the same triple already exists, we reuse its ``article_id`` rather
    than inserting a duplicate row.

    Returns (num_new_articles, num_links).
    """

    sql_select_existing = """
        SELECT article_id
        FROM news_articles
        WHERE timestamp = %s AND source = %s AND headline = %s
        LIMIT 1
    """

    sql_insert_article = """
        INSERT INTO news_articles (
            timestamp,
            source,
            language,
            headline,
            body,
            metadata
        ) VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING article_id
    """

    # We allow multiple links per article; conflict avoidance is via the
    # composite primary key on (article_id, issuer_id, instrument_id).
    sql_link = """
        INSERT INTO news_links (
            article_id,
            issuer_id,
            instrument_id
        ) VALUES (%s, %s, %s)
        ON CONFLICT DO NOTHING
    """

    num_new_articles = 0
    num_links = 0

    with db.get_historical_connection() as conn:
        cur = conn.cursor()
        try:
            for article in articles:
                # Derive a non-null, reasonably short source string. Some
                # EODHD news feeds (e.g. Benzinga) omit explicit provider
                # fields, but our schema requires ``source`` to be NOT NULL.
                raw = article.raw or {}
                db_source = (
                    article.source
                    or raw.get("source")
                    or raw.get("provider")
                    or "eodhd"
                )
                # Truncate to the column limit (128 chars in the migration).
                db_source = str(db_source)[:128]

                meta = {
                    "provider": "eodhd",
                    "external_id": article.external_id,
                    "symbols": list(article.symbols),
                    "raw": raw,
                }

                # Try to find an existing article first.
                cur.execute(
                    sql_select_existing,
                    (article.timestamp, db_source, article.headline),
                )
                row = cur.fetchone()

                if row:
                    article_id = row[0]
                else:
                    cur.execute(
                        sql_insert_article,
                        (
                            article.timestamp,
                            db_source,
                            article.language,
                            article.headline,
                            article.body,
                            Json(meta),
                        ),
                    )
                    article_id = cur.fetchone()[0]
                    num_new_articles += 1

                # Attach links based on the intersection of article symbols
                # and our instrument universe.
                linked_instruments: List[str] = []
                for sym in article.symbols:
                    for inst_id in symbol_to_instruments.get(sym, []):
                        linked_instruments.append(inst_id)

                for inst_id in linked_instruments:
                    issuer_id = issuer_by_instrument.get(inst_id)
                    if not issuer_id:
                        continue
                    cur.execute(
                        sql_link,
                        (article_id, issuer_id, inst_id),
                    )
                    num_links += 1

            conn.commit()
        finally:
            cur.close()

    return num_new_articles, num_links


def ingest_eodhd_news_for_market(
    config: NewsIngestionConfig,
    *,
    db_manager: DatabaseManager | None = None,
    client: EodhdClient | None = None,
) -> Tuple[int, int]:
    """Ingest EODHD news for all ACTIVE equity instruments in a market.

    Returns (num_articles, num_links).
    """

    db = db_manager or get_db_manager()
    client = client or EodhdClient()

    instrument_to_symbol = _load_instrument_symbol_mapping(db, market_id=config.market_id)
    if not instrument_to_symbol:
        logger.warning("No instruments found for market_id=%s; nothing to do", config.market_id)
        return 0, 0

    symbol_to_instruments = _build_symbol_to_instruments(instrument_to_symbol)
    issuer_by_instrument = _load_issuer_ids_for_instruments(db, list(instrument_to_symbol.keys()))

    total_articles = 0
    total_links = 0

    # Fetch news per vendor symbol to avoid redundant HTTP calls when
    # multiple instruments share the same vendor symbol.
    for vendor_symbol, inst_ids in symbol_to_instruments.items():
        try:
            articles = fetch_news_for_symbol(
                client=client,
                symbol=vendor_symbol,
                start_date=config.start_date,
                end_date=config.end_date,
            )
            if not articles:
                continue

            num_articles, num_links = _upsert_news_articles_and_links(
                db,
                articles=articles,
                symbol_to_instruments={vendor_symbol: inst_ids},
                issuer_by_instrument=issuer_by_instrument,
            )
            total_articles += num_articles
            total_links += num_links
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Failed to ingest EODHD news for symbol %s: %s", vendor_symbol, exc)

    logger.info(
        "EODHD news ingestion complete: %d news_articles rows, %d news_links rows",
        total_articles,
        total_links,
    )
    return total_articles, total_links


__all__ = [
    "EodhdNewsArticle",
    "NewsIngestionConfig",
    "fetch_news_for_symbol",
    "ingest_eodhd_news_for_market",
]
