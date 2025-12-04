"""Unit tests for EODHD client and price ingestion helpers.

These tests deliberately avoid real network and database access by
mocking the HTTP layer and providing a stub DataWriter implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from prometheus.data.types import PriceBar
from prometheus.data_ingestion.eodhd_client import EodhdBar, EodhdClient
from prometheus.data_ingestion.eodhd_prices import (
    EodhdIngestionResult,
    ingest_eodhd_prices_for_instrument,
    ingest_eodhd_prices_for_instruments,
)


@dataclass
class _StubWriter:
    """Simple in‑memory writer capturing PriceBars for inspection."""

    written: List[PriceBar] | None = None

    def write_prices(self, bars):  # type: ignore[no-untyped-def]
        self.written = list(bars)


class TestEodhdClient:
    """Tests for the thin EODHD HTTP client."""

    @patch("prometheus.data_ingestion.eodhd_client.requests.Session")
    def test_get_eod_prices_parses_response(self, session_cls: MagicMock) -> None:
        """Client should parse JSON rows into EodhdBar objects."""

        # Arrange HTTP mock
        mock_session = MagicMock()
        session_cls.return_value = mock_session

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "date": "2024-01-02",
                "open": 10.0,
                "high": 11.0,
                "low": 9.5,
                "close": 10.5,
                "adjusted_close": 10.4,
                "volume": 1_000_000,
            },
            {
                "date": "2024-01-03",
                "open": 10.5,
                "high": 11.5,
                "low": 10.0,
                "close": 11.0,
                "adjusted_close": 10.9,
                "volume": 1_100_000,
            },
        ]
        mock_session.get.return_value = mock_response

        client = EodhdClient(api_token="dummy-token")

        # Act
        bars = client.get_eod_prices("TEST.US")

        # Assert
        assert len(bars) == 2
        first = bars[0]
        assert isinstance(first, EodhdBar)
        assert first.trade_date == date(2024, 1, 2)
        assert first.open == 10.0
        assert first.adjusted_close == 10.4
        assert first.volume == 1_000_000


class TestEodhdPriceIngestion:
    """Tests for the price ingestion helpers that use the client."""

    def test_ingest_single_instrument_writes_price_bars(self) -> None:
        """Single‑instrument helper should convert and write bars."""

        # Stub client returning two bars
        client = MagicMock()
        client.get_eod_prices.return_value = [
            EodhdBar(
                trade_date=date(2024, 1, 2),
                open=10.0,
                high=11.0,
                low=9.5,
                close=10.5,
                adjusted_close=10.4,
                volume=1_000_000,
            ),
            EodhdBar(
                trade_date=date(2024, 1, 3),
                open=10.5,
                high=11.5,
                low=10.0,
                close=11.0,
                adjusted_close=10.9,
                volume=1_100_000,
            ),
        ]

        writer = _StubWriter()

        result = ingest_eodhd_prices_for_instrument(
            instrument_id="TEST_INST",
            eodhd_symbol="TEST.US",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            currency="USD",
            client=client,
            writer=writer,
        )

        assert isinstance(result, EodhdIngestionResult)
        assert result.instrument_id == "TEST_INST"
        assert result.eodhd_symbol == "TEST.US"
        assert result.bars_written == 2

        assert writer.written is not None
        assert len(writer.written) == 2
        bar0 = writer.written[0]
        assert bar0.instrument_id == "TEST_INST"
        assert bar0.currency == "USD"
        assert bar0.metadata == {"source": "eodhd"}

    def test_ingest_multiple_instruments_aggregates_results(self) -> None:
        """Multi‑instrument helper should reuse client/writer and aggregate results."""

        client = MagicMock()
        # Same two bars for simplicity
        client.get_eod_prices.return_value = [
            EodhdBar(
                trade_date=date(2024, 1, 2),
                open=10.0,
                high=11.0,
                low=9.5,
                close=10.5,
                adjusted_close=10.4,
                volume=1_000_000,
            ),
            EodhdBar(
                trade_date=date(2024, 1, 3),
                open=10.5,
                high=11.5,
                low=10.0,
                close=11.0,
                adjusted_close=10.9,
                volume=1_100_000,
            ),
        ]

        writer = _StubWriter()

        mapping = {"INST1": "AAA.US", "INST2": "BBB.US"}
        currency_by_instrument = {"INST1": "USD", "INST2": "USD"}

        results = ingest_eodhd_prices_for_instruments(
            mapping=mapping,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            default_currency="USD",
            currency_by_instrument=currency_by_instrument,
            client=client,
            writer=writer,
        )

        assert len(results) == 2
        assert {r.instrument_id for r in results} == {"INST1", "INST2"}
        assert all(r.bars_written == 2 for r in results)

        # Writer is reused; last call should still produce two bars.
        assert writer.written is not None
        assert len(writer.written) == 2
