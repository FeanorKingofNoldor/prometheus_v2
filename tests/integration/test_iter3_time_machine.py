"""Prometheus v2: Iteration 3 TimeMachine Integration Test.

This test validates that TimeMachine enforces time-gated access to
historical prices via DataReader:

- Load a block of daily prices for a single instrument.
- Iterate over a subset of trading days.
- For each date, request a lookback window that extends into the future.
- Verify that returned rows never include dates after the current
  simulation date.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from prometheus.core.config import get_config
from prometheus.core.database import DatabaseManager
from prometheus.core.ids import generate_uuid
from prometheus.core.time import TradingCalendar, US_EQ
from prometheus.data.types import PriceBar
from prometheus.data.writer import DataWriter
from prometheus.data.reader import DataReader
from prometheus.execution.time_machine import TimeMachine


@pytest.mark.integration
class TestIteration3TimeMachine:
    """Integration tests for TimeMachine and prices_daily access."""

    def test_time_machine_prevents_lookahead_on_prices(self) -> None:
        """TimeMachine.get_data should never return rows after current_date."""

        config = get_config()
        db_manager = DatabaseManager(config)

        # Insert a temporary instrument into historical_db. We reuse the
        # core schema from previous iterations; foreign keys (if any)
        # are satisfied by creating matching markets and issuers.
        with db_manager.get_historical_connection() as conn:
            cursor = conn.cursor()

            instrument_id = f"TEST_INST3_{generate_uuid()[:8]}"
            issuer_id = f"TEST_ISS3_{generate_uuid()[:8]}"
            market_id = f"TEST_MKT3_{generate_uuid()[:8]}"

            cursor.execute(
                """
                INSERT INTO markets (market_id, name, region, timezone)
                VALUES (%s, %s, %s, %s)
                """,
                (market_id, "Test Market 3", "US", "America/New_York"),
            )

            cursor.execute(
                """
                INSERT INTO issuers (issuer_id, issuer_type, name)
                VALUES (%s, %s, %s)
                """,
                (issuer_id, "CORPORATION", "Test Corp 3"),
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
                (instrument_id, issuer_id, market_id, "EQUITY", "TST3", "USD"),
            )

            conn.commit()
            cursor.close()

        calendar = TradingCalendar()
        start = date(2023, 1, 1)
        end = date(2023, 9, 30)
        trading_days = calendar.trading_days_between(start, end)

        # Build and write synthetic price data for each trading day.
        writer = DataWriter(db_manager=db_manager)
        price = 50.0
        bars = []
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
                    volume=500_000.0,
                    currency="USD",
                    metadata={"source": "iter3_test"},
                )
            )
            price += 0.25

        writer.write_prices(bars)

        reader = DataReader(db_manager=db_manager)
        tm = TimeMachine(
            start_date=start,
            end_date=end,
            market=US_EQ,
            data_reader=reader,
            calendar=calendar,
            strict_mode=False,
        )

        # Use a subset of dates where a 63-day lookback is meaningful.
        lookback_days = 63
        subset_days = trading_days[lookback_days: lookback_days + 40]

        for as_of_date in subset_days:
            tm.set_date(as_of_date)
            window_start = as_of_date - timedelta(days=lookback_days)

            df = tm.get_data(
                "prices_daily",
                {
                    "instrument_ids": [instrument_id],
                    "start_date": window_start,
                    # Intentionally request beyond as_of_date; TimeMachine
                    # must filter out any rows after current_date.
                    "end_date": as_of_date + timedelta(days=10),
                },
            )

            assert not df.empty
            assert df["instrument_id"].nunique() == 1
            assert df["instrument_id"].iloc[0] == instrument_id

            max_date = df["trade_date"].max()
            min_date = df["trade_date"].min()

            assert min_date >= trading_days[0]
            assert max_date <= as_of_date

        # Cleanup: remove inserted data and core entities.
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
