"""
Prometheus v2: Iteration 2 Data Access Integration Test

This integration test validates:
- TradingCalendar behaviour over a date range
- Writing price data via DataWriter into prices_daily (historical_db)
- Reading price data via DataReader
- Consistency between calendar trading days and stored price rows
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from prometheus.core.config import get_config
from prometheus.core.database import DatabaseManager
from prometheus.core.ids import generate_uuid
from prometheus.core.time import US_EQ, TradingCalendar
from prometheus.data.types import PriceBar
from prometheus.data.writer import DataWriter
from prometheus.data.reader import DataReader


@pytest.mark.integration
class TestIteration2DataAccess:
    """Integration tests for Iteration 2 data access layer."""

    def test_calendar_and_price_read_write(self) -> None:
        """Write price data for trading days and read it back consistently.

        Scenario:
        - Create a temporary instrument in the historical_db.
        - Use TradingCalendar to determine trading days in a month.
        - Write one PriceBar per trading day via DataWriter.
        - Read prices back via DataReader and verify:
          - Number of rows == number of trading days.
          - Trade dates match the trading-day set exactly.
        """

        config = get_config()
        db_manager = DatabaseManager(config)

        # Insert a temporary instrument into historical_db so foreign keys
        # are satisfied if present.
        with db_manager.get_historical_connection() as conn:
            cursor = conn.cursor()
            instrument_id = f"TEST_INST2_{generate_uuid()[:8]}"
            issuer_id = f"TEST_ISS2_{generate_uuid()[:8]}"
            market_id = f"TEST_MKT2_{generate_uuid()[:8]}"

            # Core entity inserts (mirroring Iteration 1 pattern)
            cursor.execute(
                """
                INSERT INTO markets (market_id, name, region, timezone)
                VALUES (%s, %s, %s, %s)
                """,
                (market_id, "Test Market 2", "US", "America/New_York"),
            )

            cursor.execute(
                """
                INSERT INTO issuers (issuer_id, issuer_type, name)
                VALUES (%s, %s, %s)
                """,
                (issuer_id, "CORPORATION", "Test Corp 2"),
            )

            cursor.execute(
                """
                INSERT INTO instruments (
                    instrument_id,
                    issuer_id,
                    market_id,
                    asset_class,
                    symbol,
                    currency
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (instrument_id, issuer_id, market_id, "EQUITY", "TST2", "USD"),
            )

            conn.commit()
            cursor.close()

        # Determine trading days for January 2024
        calendar = TradingCalendar()
        start = date(2024, 1, 1)
        end = date(2024, 1, 31)
        trading_days = calendar.trading_days_between(start, end)

        # Build price bars (simple synthetic OHLCV series)
        bars = []
        price = 100.0
        for d in trading_days:
            bars.append(
                PriceBar(
                    instrument_id=instrument_id,
                    trade_date=d,
                    open=price,
                    high=price + 1.0,
                    low=price - 1.0,
                    close=price + 0.5,
                    adjusted_close=price + 0.5,
                    volume=1_000_000.0,
                    currency="USD",
                    metadata={"source": "iter2_test"},
                )
            )
            price += 0.5

        writer = DataWriter(db_manager=db_manager)
        writer.write_prices(bars)

        reader = DataReader(db_manager=db_manager)
        df = reader.read_prices([instrument_id], start, end)

        # Verify row count and dates
        assert len(df) == len(trading_days)
        returned_dates = set(df["trade_date"].tolist())
        assert returned_dates == set(trading_days)

        # Basic sanity check on price progression
        df_sorted = df.sort_values(["trade_date"]).reset_index(drop=True)
        first_close = df_sorted.loc[0, "close"]
        last_close = df_sorted.loc[len(df_sorted) - 1, "close"]
        assert last_close > first_close

        # Cleanup: remove inserted price rows and core entities
        with db_manager.get_historical_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM prices_daily WHERE instrument_id = %s",
                (instrument_id,),
            )
            cursor.execute(
                "DELETE FROM instruments WHERE instrument_id = %s",
                (instrument_id,),
            )
            cursor.execute(
                "DELETE FROM issuers WHERE issuer_id = %s",
                (issuer_id,),
            )
            cursor.execute(
                "DELETE FROM markets WHERE market_id = %s",
                (market_id,),
            )
            conn.commit()
            cursor.close()
