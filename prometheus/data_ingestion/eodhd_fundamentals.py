"""Ingest EODHD fundamentals into financial_statements and fundamental_ratios.

This module uses the EODHD `/fundamentals/{symbol}` endpoint for
S&P 500 equities and writes:

- Normalised financial statements into ``financial_statements``.
- Basic ratios into ``fundamental_ratios``.

At this stage we focus on correctness and idempotence rather than
exhaustive ratio coverage.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, Iterable, List, Tuple

from psycopg2.extras import Json

from prometheus.core.database import DatabaseManager, get_db_manager
from prometheus.core.logging import get_logger
from prometheus.data_ingestion.eodhd_client import EodhdClient


logger = get_logger(__name__)


@dataclass(frozen=True)
class StatementSnapshot:
    """Canonical representation of a single financial statement."""

    issuer_id: str
    statement_type: str  # "IS", "BS", "CF"
    frequency: str  # "ANNUAL" or "QUARTERLY"
    fiscal_year: int
    fiscal_period: str
    period_end: date
    report_date: date
    currency: str | None
    values: dict


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _quarter_from_month(month: int) -> int:
    return (month - 1) // 3 + 1


def fetch_fundamentals_for_symbol(
    symbol: str,
    issuer_id: str,
    *,
    client: EodhdClient,
) -> Tuple[List[StatementSnapshot], Dict[str, dict]]:
    """Fetch fundamentals for a symbol and return statement snapshots.

    Also returns a mapping ``ratios_by_period`` keyed by
    ``(frequency, period_end.isoformat())`` with ratio-related fields
    extracted from EODHD's ``Highlights`` / ``Valuation`` sections.
    """

    import requests

    url = f"{client._base_url}/fundamentals/{symbol}"  # type: ignore[attr-defined]
    params = {"api_token": client._api_token, "fmt": "json"}  # type: ignore[attr-defined]

    logger.info("Fetching fundamentals for %s", symbol)

    resp = requests.get(url, params=params, timeout=30)
    if resp.status_code != 200:
        logger.warning(
            "Fundamentals request failed for %s: status=%s body=%s",
            symbol,
            resp.status_code,
            resp.text[:300],
        )
        return [], {}

    data = resp.json()
    fin = data.get("Financials") or {}

    general = data.get("General") or {}
    currency = general.get("CurrencyCode") or general.get("CurrencySymbol")

    statements: List[StatementSnapshot] = []

    # Helper to traverse one statement family (e.g. Balance_Sheet yearly)
    def _extract(
        stype_key: str,
        logical_type: str,
        freq_key: str,
        freq_label: str,
    ) -> None:
        section = fin.get(stype_key) or {}
        per_freq = section.get(freq_key)
        if not isinstance(per_freq, dict):
            return
        for key, rec in per_freq.items():
            try:
                pend = _parse_date(rec.get("date") or key)
                if pend is None:
                    continue
                # Only keep data from 1997 onwards to match price horizon.
                if pend < date(1997, 1, 1):
                    continue
                filing_date = _parse_date(rec.get("filing_date")) or pend
                year = pend.year
                if freq_label == "ANNUAL":
                    fiscal_period = f"{year}A"
                else:
                    q = _quarter_from_month(pend.month)
                    fiscal_period = f"{year}Q{q}"
                snap = StatementSnapshot(
                    issuer_id=issuer_id,
                    statement_type=logical_type,
                    frequency=freq_label,
                    fiscal_year=year,
                    fiscal_period=fiscal_period,
                    period_end=pend,
                    report_date=filing_date,
                    currency=rec.get("currency_symbol") or currency,
                    values=rec,
                )
                statements.append(snap)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    "Skipping malformed %s/%s record for %s key=%s: %s",
                    stype_key,
                    freq_key,
                    symbol,
                    key,
                    exc,
                )

    _extract("Income_Statement", "IS", "yearly", "ANNUAL")
    _extract("Income_Statement", "IS", "quarterly", "QUARTERLY")
    _extract("Balance_Sheet", "BS", "yearly", "ANNUAL")
    _extract("Balance_Sheet", "BS", "quarterly", "QUARTERLY")
    _extract("Cash_Flow", "CF", "yearly", "ANNUAL")
    _extract("Cash_Flow", "CF", "quarterly", "QUARTERLY")

    # Ratios: EODHD exposes some headline metrics in "Highlights" and
    # "Valuation". We attach them keyed by (frequency, period_end).
    ratios_by_period: Dict[str, dict] = {}
    # For now we treat all ratios as ANNUAL at the latest available
    # date; a more precise mapping can be added later.
    highlights = data.get("Highlights") or {}
    valuation = data.get("Valuation") or {}
    if statements:
        latest = max(statements, key=lambda s: s.period_end)
        key = f"{latest.frequency}:{latest.period_end.isoformat()}"
        metrics: dict = {}
        for field in [
            "MarketCapitalization",
            "BookValue",
            "DividendShare",
            "DividendYield",
            "EarningsShare",
            "PERatio",
            "PEGRatio",
        ]:
            if field in highlights and highlights[field] is not None:
                metrics[field] = highlights[field]
        for field in [
            "TrailingPE",
            "ForwardPE",
            "PriceSalesTTM",
            "PriceBookMRQ",
            "EnterpriseValue",
            "EnterpriseValueRevenue",
            "EnterpriseValueEbitda",
        ]:
            if field in valuation and valuation[field] is not None:
                metrics[field] = valuation[field]
        ratios_by_period[key] = metrics

    return statements, ratios_by_period


def write_financial_statements(
    statements: Iterable[StatementSnapshot],
    db_manager: DatabaseManager | None = None,
) -> int:
    """Upsert a collection of statements into ``financial_statements``.

    Returns the number of rows written.
    """

    db = db_manager or get_db_manager()
    sql = """
        INSERT INTO financial_statements (
            issuer_id,
            fiscal_period,
            fiscal_year,
            statement_type,
            report_date,
            period_start,
            period_end,
            currency,
            values,
            metadata
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (issuer_id, statement_type, period_end)
        DO UPDATE SET
            fiscal_period = EXCLUDED.fiscal_period,
            fiscal_year = EXCLUDED.fiscal_year,
            report_date = EXCLUDED.report_date,
            currency = EXCLUDED.currency,
            values = EXCLUDED.values,
            metadata = EXCLUDED.metadata
    """

    count = 0
    with db.get_historical_connection() as conn:
        cur = conn.cursor()
        try:
            for s in statements:
                meta = {"frequency": s.frequency, "source": "eodhd"}
                cur.execute(
                    sql,
                    (
                        s.issuer_id,
                        s.fiscal_period,
                        s.fiscal_year,
                        s.statement_type,
                        s.report_date,
                        None,
                        s.period_end,
                        s.currency,
                        Json(s.values),
                        Json(meta),
                    ),
                )
                count += 1
            conn.commit()
        finally:
            cur.close()

    logger.info("Inserted/updated %d financial_statements rows", count)
    return count


def write_fundamental_ratios(
    issuer_id: str,
    ratios_by_period: Dict[str, dict],
    db_manager: DatabaseManager | None = None,
) -> int:
    """Write basic ratios into ``fundamental_ratios``.

    The ``ratios_by_period`` mapping is keyed by
    ``f"{frequency}:{period_end}"``.
    """

    db = db_manager or get_db_manager()
    sql = """
        INSERT INTO fundamental_ratios (
            issuer_id,
            period_start,
            period_end,
            frequency,
            roe,
            roic,
            gross_margin,
            op_margin,
            net_margin,
            leverage,
            interest_coverage,
            revenue_growth,
            eps_growth,
            metrics,
            metadata
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (issuer_id, period_start, period_end, frequency)
        DO UPDATE SET
            roe = EXCLUDED.roe,
            roic = EXCLUDED.roic,
            gross_margin = EXCLUDED.gross_margin,
            op_margin = EXCLUDED.op_margin,
            net_margin = EXCLUDED.net_margin,
            leverage = EXCLUDED.leverage,
            interest_coverage = EXCLUDED.interest_coverage,
            revenue_growth = EXCLUDED.revenue_growth,
            eps_growth = EXCLUDED.eps_growth,
            metrics = EXCLUDED.metrics,
            metadata = EXCLUDED.metadata
    """

    count = 0
    with db.get_historical_connection() as conn:
        cur = conn.cursor()
        try:
            for key, metrics in ratios_by_period.items():
                freq, pend_str = key.split(":", 1)
                pend = date.fromisoformat(pend_str)
                # For now we approximate period_start using calendar day
                # offsets rather than month arithmetic so we never create
                # invalid dates (e.g. 31st of February).
                if freq == "ANNUAL":
                    pstart = pend - timedelta(days=365)
                else:
                    # Approximate quarter length as 90 days.
                    pstart = pend - timedelta(days=90)

                row = {
                    "roe": metrics.get("ROE"),
                    "roic": metrics.get("ROIC"),
                    "gross_margin": metrics.get("GrossMargin"),
                    "op_margin": metrics.get("OperatingMargin"),
                    "net_margin": metrics.get("NetMargin"),
                    "leverage": metrics.get("Leverage"),
                    "interest_coverage": metrics.get("InterestCoverage"),
                    "revenue_growth": metrics.get("RevenueGrowth"),
                    "eps_growth": metrics.get("EPSGrowth"),
                }

                cur.execute(
                    sql,
                    (
                        issuer_id,
                        pstart,
                        pend,
                        freq,
                        row["roe"],
                        row["roic"],
                        row["gross_margin"],
                        row["op_margin"],
                        row["net_margin"],
                        row["leverage"],
                        row["interest_coverage"],
                        row["revenue_growth"],
                        row["eps_growth"],
                        Json(metrics),
                        Json({"source": "eodhd"}),
                    ),
                )
                count += 1
            conn.commit()
        finally:
            cur.close()

    logger.info("Inserted/updated %d fundamental_ratios rows for %s", count, issuer_id)
    return count


def ingest_fundamentals_for_issuers(
    issuer_ids: Iterable[str],
    *,
    db_manager: DatabaseManager | None = None,
    client: EodhdClient | None = None,
) -> Tuple[int, int]:
    """Fetch and write fundamentals for a collection of issuers.

    Returns ``(statements_written, ratios_written)``.
    """

    db = db_manager or get_db_manager()
    client = client or EodhdClient()

    total_statements = 0
    total_ratios = 0

    for issuer_id in issuer_ids:
        symbol = f"{issuer_id}.US"
        try:
            statements, ratios = fetch_fundamentals_for_symbol(symbol, issuer_id, client=client)
            if not statements:
                continue
            total_statements += write_financial_statements(statements, db)
            if ratios:
                total_ratios += write_fundamental_ratios(issuer_id, ratios, db)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Failed to ingest fundamentals for %s (%s): %s", issuer_id, symbol, exc)

    logger.info(
        "Fundamentals ingestion complete: %d financial_statements rows, %d fundamental_ratios rows",
        total_statements,
        total_ratios,
    )
    return total_statements, total_ratios


__all__ = [
    "StatementSnapshot",
    "fetch_fundamentals_for_symbol",
    "write_financial_statements",
    "write_fundamental_ratios",
    "ingest_fundamentals_for_issuers",
]
