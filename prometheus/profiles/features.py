"""Prometheus v2 – Profile feature builder.

This module builds structured profile fields and simple risk flags for
issuers using currently available data:

- Issuer metadata from `issuers`.
- A representative instrument and its recent price history from
  `prices_daily`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import numpy as np

from prometheus.core.database import DatabaseManager
from prometheus.core.logging import get_logger
from prometheus.core.time import TradingCalendar
from prometheus.data.reader import DataReader
from prometheus.encoders.news_features import load_issuer_news_features

logger = get_logger(__name__)


@dataclass
class ProfileFeatureBuilder:
    """Build structured fields and risk flags for issuer profiles."""

    db_manager: DatabaseManager
    data_reader: DataReader
    calendar: TradingCalendar
    window_days: int = 63

    # Minimum required days for price features. Default allows ~87% tolerance.
    min_required_days: int = 55

    # Optional integration with issuer×day news features. When the
    # DatabaseManager exposes a historical connection and issuer×day
    # NEWS embeddings have been backfilled, structured profiles can
    # include a small `news_features` section built from
    # `issuer_news_daily` / `text_embeddings`.
    include_news_features: bool = True
    news_model_id: str = "text-fin-general-v1"

    # Reference scales for risk flags (rough initial calibration).
    vol_ref: float = 0.02   # 2% daily volatility
    dd_ref: float = 0.30    # 30% drawdown
    lev_ref: float = 3.0    # leverage ratio reference (Liab/Equity)

    def _load_issuer_row(self, issuer_id: str) -> tuple | None:
        sql = """
            SELECT issuer_type, name, country, sector, industry, metadata
            FROM issuers
            WHERE issuer_id = %s
        """
        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (issuer_id,))
                row = cursor.fetchone()
            finally:
                cursor.close()
        return row

    def _load_representative_instrument(self, issuer_id: str) -> str | None:
        sql = """
            SELECT instrument_id
            FROM instruments
            WHERE issuer_id = %s
            ORDER BY instrument_id ASC
            LIMIT 1
        """
        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (issuer_id,))
                row = cursor.fetchone()
            finally:
                cursor.close()
        if row is None:
            return None
        (instrument_id,) = row
        return instrument_id

    # ------------------------------------------------------------------
    # Price-based numeric features
    # ------------------------------------------------------------------

    def _compute_price_features(self, instrument_id: str, as_of_date: date) -> dict[str, float]:
        if self.window_days <= 0:
            raise ValueError("window_days must be positive")

        search_start = as_of_date - timedelta(days=self.window_days * 3)
        trading_days = self.calendar.trading_days_between(search_start, as_of_date)
        if len(trading_days) < self.min_required_days:
            logger.warning(
                "Not enough trading history (%d days, need %d) for price features: "
                "instrument=%s as_of=%s",
                len(trading_days),
                self.min_required_days,
                instrument_id,
                as_of_date,
            )
            return {}

        # Use available days, up to target
        actual_window_days = min(len(trading_days), self.window_days)
        window_days = trading_days[-actual_window_days:]
        start_date = window_days[0]

        df = self.data_reader.read_prices([instrument_id], start_date, as_of_date)
        if df.empty or len(df) < self.min_required_days:
            logger.warning(
                "Insufficient price rows (%d, need %d) for %s between %s and %s",
                len(df),
                self.min_required_days,
                instrument_id,
                start_date,
                as_of_date,
            )
            return {}

        df_sorted = df.sort_values(["trade_date"]).reset_index(drop=True)
        df_window = df_sorted.tail(actual_window_days)
        closes = df_window["close"].astype(float).to_numpy()

        if closes.shape[0] < self.min_required_days:
            logger.warning(
                "Price history length (%d) below minimum (%d) for %s",
                closes.shape[0],
                self.min_required_days,
                instrument_id,
            )
            return {}

        log_rets = np.zeros_like(closes, dtype=float)
        log_rets[1:] = np.log(closes[1:] / closes[:-1])

        sigma = float(np.std(log_rets[1:], ddof=1)) if log_rets.shape[0] > 1 else 0.0

        running_max = np.maximum.accumulate(closes)
        drawdowns = closes / running_max - 1.0
        max_dd = float(drawdowns.min())  # negative

        if closes[0] > 0.0:
            trend = float((closes[-1] - closes[0]) / closes[0])
        else:
            trend = 0.0

        return {
            "instrument_id": instrument_id,
            "price_vol_63d": sigma,
            "price_dd_63d": abs(max_dd),
            "price_trend_63d": trend,
        }

    # ------------------------------------------------------------------
    # Fundamentals-based features
    # ------------------------------------------------------------------

    def _load_latest_statement_values(
        self,
        issuer_id: str,
        as_of_date: date,
        statement_type: str,
    ) -> dict[str, Any] | None:
        """Return the `values` JSON for the latest statement up to as_of_date.

        This reads from historical_db.financial_statements when available.
        If the DatabaseManager stub used in unit tests does not expose a
        historical connection, fundamentals are silently skipped.
        """

        if not hasattr(self.db_manager, "get_historical_connection"):
            return None

        sql = """
            SELECT values
            FROM financial_statements
            WHERE issuer_id = %s
              AND statement_type = %s
              AND (period_end IS NULL OR period_end <= %s)
            ORDER BY period_end DESC
            LIMIT 1
        """

        with self.db_manager.get_historical_connection() as conn:  # type: ignore[attr-defined]
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (issuer_id, statement_type, as_of_date))
                row = cursor.fetchone()
            finally:
                cursor.close()

        if row is None:
            return None
        (values,) = row
        return values or {}

    def _load_latest_ratios_metrics(
        self, issuer_id: str, as_of_date: date
    ) -> dict[str, Any] | None:
        """Return the latest metrics JSON from fundamental_ratios, if any."""

        if not hasattr(self.db_manager, "get_historical_connection"):
            return None

        sql = """
            SELECT metrics
            FROM fundamental_ratios
            WHERE issuer_id = %s
              AND period_end <= %s
            ORDER BY period_end DESC
            LIMIT 1
        """

        with self.db_manager.get_historical_connection() as conn:  # type: ignore[attr-defined]
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (issuer_id, as_of_date))
                row = cursor.fetchone()
            finally:
                cursor.close()

        if row is None:
            return None
        (metrics,) = row
        return metrics or {}

    def _build_fundamental_features(self, issuer_id: str, as_of_date: date) -> dict[str, Any]:
        """Build a small set of fundamental features from statements/ratios.

        We keep this intentionally lightweight: levels and a few simple
        derived ratios that are robust across issuers.
        """

        is_vals = self._load_latest_statement_values(issuer_id, as_of_date, "IS") or {}
        bs_vals = self._load_latest_statement_values(issuer_id, as_of_date, "BS") or {}
        ratios = self._load_latest_ratios_metrics(issuer_id, as_of_date) or {}

        # Levels
        revenue = float(is_vals.get("totalRevenue") or 0.0)
        gross_profit = float(is_vals.get("grossProfit") or 0.0)
        op_income = float(is_vals.get("operatingIncome") or 0.0)
        ebit = float(is_vals.get("ebit") or 0.0)
        ebitda = float(is_vals.get("ebitda") or 0.0)
        net_income = float(is_vals.get("netIncome") or 0.0)

        total_assets = float(bs_vals.get("totalAssets") or 0.0)
        total_liab = float(bs_vals.get("totalLiab") or 0.0)
        equity = float(bs_vals.get("totalStockholderEquity") or 0.0)
        cash = float(bs_vals.get("cash") or 0.0)

        # Simple margins
        gross_margin = float(gross_profit / revenue) if revenue > 0.0 else 0.0
        op_margin = float(op_income / revenue) if revenue > 0.0 else 0.0
        net_margin = float(net_income / revenue) if revenue > 0.0 else 0.0

        # Leverage
        leverage = float(total_liab / equity) if equity > 0.0 else 0.0

        fundamentals: dict[str, Any] = {
            "currency": is_vals.get("currency_symbol") or bs_vals.get("currency_symbol"),
            "revenue": revenue,
            "gross_profit": gross_profit,
            "operating_income": op_income,
            "ebit": ebit,
            "ebitda": ebitda,
            "net_income": net_income,
            "total_assets": total_assets,
            "total_liabilities": total_liab,
            "equity": equity,
            "cash": cash,
            "gross_margin": gross_margin,
            "op_margin": op_margin,
            "net_margin": net_margin,
            "leverage": leverage,
        }

        # Selected valuation metrics from ratios.metrics, if present.
        for key in [
            "PERatio",
            "PEGRatio",
            "TrailingPE",
            "PriceBookMRQ",
            "PriceSalesTTM",
            "DividendYield",
            "EarningsShare",
            "BookValue",
        ]:
            if key in ratios and ratios[key] is not None:
                fundamentals[key] = ratios[key]

        return fundamentals

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_structured(self, issuer_id: str, as_of_date: date) -> dict[str, Any]:
        """Build structured profile fields for an issuer."""

        row = self._load_issuer_row(issuer_id)
        if row is None:
            raise ValueError(f"Unknown issuer_id {issuer_id!r} when building profile")

        issuer_type, name, country, sector, industry, metadata = row

        structured: dict[str, Any] = {
            "issuer_id": issuer_id,
            "name": name,
            "issuer_type": issuer_type,
            "country": country,
            "sector": sector,
            "industry": industry,
            "issuer_metadata": metadata or {},
        }

        instrument_id = self._load_representative_instrument(issuer_id)
        if instrument_id is not None:
            price_features = self._compute_price_features(instrument_id, as_of_date)
            if price_features:
                structured["numeric_features"] = price_features

        # Fundamentals are optional; we attempt to load them but tolerate
        # missing data or environments without a historical connection.
        try:
            fundamentals = self._build_fundamental_features(issuer_id, as_of_date)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to build fundamentals for issuer %s: %s", issuer_id, exc)
            fundamentals = {}
        if fundamentals:
            structured["fundamentals"] = fundamentals

        # Optional issuer×day news features. We require a historical DB
        # connection to be present on the DatabaseManager; unit tests that
        # use stub DB managers will therefore skip this block.
        if self.include_news_features and hasattr(self.db_manager, "get_historical_connection"):
            try:
                news = load_issuer_news_features(
                    issuer_id=issuer_id,
                    as_of_date=as_of_date,
                    db_manager=self.db_manager,  # type: ignore[arg-type]
                    model_id=self.news_model_id,
                )
                if (
                    news.embedding is not None
                    or news.n_articles > 0
                    or news.days_since_last_news is not None
                ):
                    structured["news_features"] = {
                        "model_id": news.model_id,
                        "source_type": "NEWS_ISSUER_DAY",
                        "embedding_source_id": f"{issuer_id}:{as_of_date.isoformat()}",
                        "has_embedding": news.embedding is not None,
                        "n_articles": news.n_articles,
                        "days_since_last_news": news.days_since_last_news,
                    }
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Failed to load news features for issuer %s: %s", issuer_id, exc)

        return structured

    def build_risk_flags(self, structured: dict[str, Any]) -> dict[str, float]:
        """Build simple numeric risk flags from structured features.

        The initial implementation focuses on volatility and drawdown
        based flags derived from recent price history if available.
        """

        numeric = structured.get("numeric_features") or {}
        vol = float(numeric.get("price_vol_63d", 0.0))
        dd = float(numeric.get("price_dd_63d", 0.0))

        vol_flag = 0.0
        if self.vol_ref > 0.0:
            vol_flag = min(1.0, vol / self.vol_ref)

        dd_flag = 0.0
        if self.dd_ref > 0.0:
            dd_flag = min(1.0, dd / self.dd_ref)

        # Leverage-based flag from fundamentals if available.
        fundamentals = structured.get("fundamentals") or {}
        leverage = float(fundamentals.get("leverage", 0.0))
        lev_flag = 0.0
        if self.lev_ref > 0.0 and leverage > 0.0:
            lev_flag = min(1.0, leverage / self.lev_ref)

        # Simple news recency flag in [0, 1]. If news is very recent,
        # `news_recency_flag` is near 1; if there has been no news for a
        # long period (or never), it decays towards 0.
        news_recency_flag = 0.0
        news_features = structured.get("news_features") or {}
        days_since_last_news = news_features.get("days_since_last_news")
        if isinstance(days_since_last_news, (int, float)) and days_since_last_news >= 0:
            horizon = 30.0  # days; beyond this we treat news as "stale"
            d = float(days_since_last_news)
            news_recency_flag = max(0.0, 1.0 - min(d, horizon) / horizon)

        return {
            "vol_flag": float(vol_flag),
            "dd_flag": float(dd_flag),
            "leverage_flag": float(lev_flag),
            "news_recency_flag": float(news_recency_flag),
        }
