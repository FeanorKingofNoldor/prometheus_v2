"""Unit tests for EODHD fundamentals ingestion helpers.

These tests mock the HTTP layer and database writes so that we can
validate parsing and basic persistence behaviour without real network or
PostgreSQL access.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List
from unittest.mock import MagicMock, patch

import pytest

from prometheus.data_ingestion.eodhd_fundamentals import (
    StatementSnapshot,
    fetch_fundamentals_for_symbol,
    write_financial_statements,
    write_fundamental_ratios,
)


@dataclass
class _StubConn:
    """Very small connection stub capturing executed SQL parameters."""

    executed: List[Dict] | None = None

    def cursor(self):  # type: ignore[no-untyped-def]
        cur = MagicMock()
        executed: List[Dict] = []

        def _execute(sql, params=None):  # type: ignore[no-untyped-def]
            executed.append({"sql": sql, "params": params})

        cur.execute.side_effect = _execute

        def _close():  # type: ignore[no-untyped-def]
            self.executed = executed

        cur.close.side_effect = _close
        return cur

    def __enter__(self):  # type: ignore[no-untyped-def]
        return self

    def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
        return False

    def commit(self) -> None:  # pragma: no cover - no-op
        return None


@dataclass
class _StubDbManager:
    conn: _StubConn

    def get_historical_connection(self):  # type: ignore[no-untyped-def]
        return self.conn


class TestFetchFundamentals:
    @patch("requests.get")
    def test_fetch_parses_basic_structure(self, get_mock: MagicMock) -> None:
        """Parser should turn EODHD JSON into StatementSnapshot objects."""

        # Arrange mock HTTP response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "General": {"CurrencyCode": "USD"},
            "Financials": {
                "Income_Statement": {
                    "yearly": {
                        "2024-12-31": {
                            "date": "2024-12-31",
                            "filing_date": "2025-02-10",
                            "currency_symbol": "USD",
                            "totalRevenue": 100.0,
                        },
                    },
                },
            },
            "Highlights": {"PERatio": 20.0},
            "Valuation": {"TrailingPE": 19.5},
        }
        get_mock.return_value = mock_resp

        # Minimal stub client exposing base URL and token attributes
        client = MagicMock()
        client._base_url = "https://eodhd.com/api"
        client._api_token = "dummy"

        statements, ratios = fetch_fundamentals_for_symbol(
            symbol="TEST.US",
            issuer_id="TEST",
            client=client,
        )

        assert statements
        snap = statements[0]
        assert isinstance(snap, StatementSnapshot)
        assert snap.issuer_id == "TEST"
        assert snap.statement_type == "IS"
        assert snap.frequency == "ANNUAL"
        assert snap.period_end == date(2024, 12, 31)
        assert snap.report_date == date(2025, 2, 10)
        assert snap.currency == "USD"
        assert snap.values["totalRevenue"] == 100.0

        # Ratios should be keyed by frequency:period_end
        assert ratios
        key = next(iter(ratios.keys()))
        assert key.startswith("ANNUAL:")
        assert ratios[key]["PERatio"] == 20.0
        assert ratios[key]["TrailingPE"] == 19.5


class TestWriteHelpers:
    def test_write_financial_statements_uses_expected_sql(self) -> None:
        conn = _StubConn()
        db = _StubDbManager(conn=conn)

        snap = StatementSnapshot(
            issuer_id="TEST",
            statement_type="IS",
            frequency="ANNUAL",
            fiscal_year=2024,
            fiscal_period="2024A",
            period_end=date(2024, 12, 31),
            report_date=date(2025, 2, 10),
            currency="USD",
            values={"totalRevenue": 100.0},
        )

        rows = write_financial_statements([snap], db_manager=db)  # type: ignore[arg-type]
        assert rows == 1
        assert conn.executed is not None
        assert len(conn.executed) == 1
        entry = conn.executed[0]
        params = entry["params"]
        # issuer_id, fiscal_period, fiscal_year, statement_type, report_date, period_start, period_end
        assert params[0] == "TEST"
        assert params[1] == "2024A"
        assert params[2] == 2024
        assert params[3] == "IS"
        assert params[6] == date(2024, 12, 31)

    def test_write_fundamental_ratios_inserts_row(self) -> None:
        conn = _StubConn()
        db = _StubDbManager(conn=conn)

        ratios_by_period = {"ANNUAL:2024-12-31": {"ROE": 0.15}}
        rows = write_fundamental_ratios("TEST", ratios_by_period, db_manager=db)  # type: ignore[arg-type]
        assert rows == 1
        assert conn.executed is not None
        assert len(conn.executed) == 1
        params = conn.executed[0]["params"]
        # issuer_id, period_start, period_end, frequency, roe
        assert params[0] == "TEST"
        assert params[2] == date(2024, 12, 31)
        assert params[3] == "ANNUAL"
        assert params[4] == 0.15
