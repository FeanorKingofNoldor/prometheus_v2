"""Prometheus v2 – EODHD HTTP client.

This module provides a minimal, well‑typed client for the EODHD
(EOD Historical Data) API, focused on the endpoints we need for
Iteration 2:

- End‑of‑day historical prices for individual symbols.

We deliberately implement our own small wrapper instead of depending on
EODHD's full Python library so that:

- We control error handling and logging behaviour.
- We avoid pulling in unused functionality.
- The client integrates cleanly with our configuration and logging
  infrastructure.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date

import requests

from prometheus.core.logging import get_logger

logger = get_logger(__name__)


class EodhdClientError(Exception):
    """Raised when an EODHD API call fails."""


@dataclass(frozen=True)
class EodhdBar:
    """Single end‑of‑day OHLCV bar returned by EODHD.

    The fields mirror the JSON payload from the EODHD ``/eod`` endpoint.
    """

    trade_date: date
    open: float
    high: float
    low: float
    close: float
    adjusted_close: float
    volume: float


class EodhdClient:
    """Thin HTTP client for the EODHD API.

    Parameters
    ----------
    api_token:
        API token for EODHD. If omitted, the client will read the
        ``EODHD_API_KEY`` environment variable.
    base_url:
        Base URL for the API. Defaults to the public EODHD endpoint.
    timeout_seconds:
        Request timeout in seconds.
    """

    def __init__(
        self,
        api_token: str | None = None,
        base_url: str = "https://eodhd.com/api",
        timeout_seconds: int = 30,
    ) -> None:
        token = api_token or os.getenv("EODHD_API_KEY")
        if not token:
            msg = "EODHD_API_KEY is not set; cannot initialise EodhdClient"
            raise EodhdClientError(msg)

        self._api_token = token
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._session = requests.Session()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_eod_prices(
        self,
        symbol: str,
        start_date: date | None = None,
        end_date: date | None = None,
        adjusted: bool = True,
    ) -> list[EodhdBar]:
        """Fetch end‑of‑day prices for a symbol.

        Parameters
        ----------
        symbol:
            EODHD symbol string, e.g. ``"AAPL.US"``.
        start_date:
            Optional start date (inclusive). If omitted, EODHD returns the
            full available history.
        end_date:
            Optional end date (inclusive).
        adjusted:
            Whether to request adjusted prices. When ``True`` the
            ``adjusted_close`` field from EODHD is used; otherwise we fall
            back to the raw ``close`` field.
        """

        params: dict[str, str] = {"api_token": self._api_token, "fmt": "json"}
        if start_date is not None:
            params["from"] = start_date.isoformat()
        if end_date is not None:
            params["to"] = end_date.isoformat()

        url = f"{self._base_url}/eod/{symbol}"
        logger.info("EodhdClient.get_eod_prices: GET %s params=%s", url, params)

        try:
            response = self._session.get(url, params=params, timeout=self._timeout_seconds)
        except Exception as exc:  # pragma: no cover - network errors
            logger.error("EODHD request failed for symbol %s: %s", symbol, exc)
            raise EodhdClientError(f"EODHD request failed for symbol {symbol!r}") from exc

        if response.status_code != 200:
            # Truncate body in logs to avoid huge messages / leaking secrets.
            body_preview = response.text[:500]
            logger.error(
                "EODHD request failed: status=%s symbol=%s body=%s",
                response.status_code,
                symbol,
                body_preview,
            )
            msg = f"EODHD /eod call failed with status {response.status_code} for symbol {symbol!r}"
            raise EodhdClientError(msg)

        try:
            payload = response.json()
        except ValueError as exc:  # pragma: no cover - defensive
            logger.error("Failed to decode EODHD JSON for symbol %s: %s", symbol, exc)
            raise EodhdClientError("Invalid JSON in EODHD response") from exc

        bars: list[EodhdBar] = []
        for row in payload:
            try:
                trade_date = date.fromisoformat(row["date"])
                open_px = float(row["open"])
                high_px = float(row["high"])
                low_px = float(row["low"])
                close_px = float(row["close"])
                adjusted_close = float(row.get("adjusted_close", close_px))
                volume = float(row.get("volume") or 0.0)
            except KeyError as exc:
                logger.error("Missing expected field in EODHD row for %s: %s", symbol, exc)
                raise EodhdClientError("Missing expected field in EODHD response") from exc

            bars.append(
                EodhdBar(
                    trade_date=trade_date,
                    open=open_px,
                    high=high_px,
                    low=low_px,
                    close=close_px,
                    adjusted_close=adjusted_close,
                    volume=volume,
                )
            )

        logger.info("EodhdClient.get_eod_prices: fetched %d rows for %s", len(bars), symbol)
        return bars

    def get_exchange_details(self, exchange_code: str) -> dict[str, object]:  # type: ignore[misc]
        """Fetch exchange details including trading hours and holidays.

        Parameters
        ----------
        exchange_code:
            Exchange code, e.g. ``"US"`` for US markets, ``"LSE"`` for London.

        Returns
        -------
        dict
            Exchange details including name, code, operating_mic, country,
            currency, trading_hours, and holidays list.

        Raises
        ------
        EodhdClientError:
            If the API request fails or returns non-200 status.
        """
        params: dict[str, str] = {"api_token": self._api_token, "fmt": "json"}
        url = f"{self._base_url}/exchange-details/{exchange_code}"
        logger.info("EodhdClient.get_exchange_details: GET %s", url)

        try:
            response = self._session.get(url, params=params, timeout=self._timeout_seconds)
        except Exception as exc:  # pragma: no cover - network errors
            logger.error("EODHD request failed for exchange %s: %s", exchange_code, exc)
            raise EodhdClientError(f"EODHD request failed for exchange {exchange_code!r}") from exc

        if response.status_code != 200:
            body_preview = response.text[:500]
            logger.error(
                "EODHD request failed: status=%s exchange=%s body=%s",
                response.status_code,
                exchange_code,
                body_preview,
            )
            msg = (
                f"EODHD /exchange-details call failed with status {response.status_code} "
                f"for exchange {exchange_code!r}"
            )
            raise EodhdClientError(msg)

        try:
            payload = response.json()
        except ValueError as exc:  # pragma: no cover - defensive
            logger.error("Failed to decode EODHD JSON for exchange %s: %s", exchange_code, exc)
            raise EodhdClientError("Invalid JSON in EODHD response") from exc

        logger.info("EodhdClient.get_exchange_details: fetched details for %s", exchange_code)
        return payload

    def close(self) -> None:
        """Close the underlying HTTP session.

        This is optional but recommended in long‑running processes.
        """

        self._session.close()


__all__ = ["EodhdClient", "EodhdClientError", "EodhdBar"]
