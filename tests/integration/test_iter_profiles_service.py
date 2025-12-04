"""Integration tests for the Profiles subsystem.

These tests validate that ProfileService can:
- Read issuer metadata and prices from the DB.
- Build and persist a profile snapshot into `profiles`.
- Produce an embedding for downstream engines.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from prometheus.core.config import get_config
from prometheus.core.database import DatabaseManager
from prometheus.core.ids import generate_uuid
from prometheus.core.time import TradingCalendar
from prometheus.data.types import PriceBar
from prometheus.data.writer import DataWriter
from prometheus.data.reader import DataReader
from prometheus.profiles import (
    ProfileService,
    ProfileStorage,
    ProfileFeatureBuilder,
    BasicProfileEmbedder,
)


def _profiles_table_exists(db_manager: DatabaseManager) -> bool:
    """Return True if the `profiles` table exists in the runtime DB.

    This lets the integration test skip cleanly when migrations (0007)
    have not yet been applied in the local environment.
    """

    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'profiles'
                )
                """
            )
            (exists,) = cursor.fetchone()
        finally:
            cursor.close()

    return bool(exists)


@pytest.mark.integration
class TestProfileServiceIntegration:
    def _insert_issuer_and_instrument(self, db_manager: DatabaseManager) -> tuple[str, str]:
        issuer_id = f"PROF_ISS_{generate_uuid()[:8]}"
        instrument_id = f"PROF_INST_{generate_uuid()[:8]}"
        market_id = "US_EQ"

        with db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()

            # Ensure a market row exists to satisfy the foreign key on instruments.market_id.
            cursor.execute(
                """
                INSERT INTO markets (market_id, name, region, timezone)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (market_id) DO NOTHING
                """,
                (market_id, "US Equities", "US", "America/New_York"),
            )

            cursor.execute(
                """
                INSERT INTO issuers (issuer_id, issuer_type, name)
                VALUES (%s, %s, %s)
                """,
                (issuer_id, "COMPANY", "Profile Test Corp"),
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
                (instrument_id, issuer_id, market_id, "EQUITY", "PTC", "USD"),
            )
            conn.commit()
            cursor.close()

        return issuer_id, instrument_id

    def _insert_price_history(self, db_manager: DatabaseManager, instrument_id: str) -> list[date]:
        calendar = TradingCalendar()
        start = date(2024, 1, 1)
        trading_days = calendar.trading_days_between(start, start + timedelta(days=90))
        trading_days = trading_days[:63]

        writer = DataWriter(db_manager=db_manager)
        price = 50.0
        bars: list[PriceBar] = []
        for d in trading_days:
            bars.append(
                PriceBar(
                    instrument_id=instrument_id,
                    trade_date=d,
                    open=price,
                    high=price + 1.0,
                    low=price - 1.0,
                    close=price,
                    adjusted_close=price,
                    volume=500_000.0,
                    currency="USD",
                    metadata={"source": "iter_profiles"},
                )
            )
            price += 0.2

        writer.write_prices(bars)
        return trading_days

    def _cleanup(self, db_manager: DatabaseManager, issuer_id: str, instrument_id: str) -> None:
        with db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM profiles WHERE issuer_id = %s", (issuer_id,))
            cursor.execute("DELETE FROM instruments WHERE instrument_id = %s", (instrument_id,))
            cursor.execute("DELETE FROM issuers WHERE issuer_id = %s", (issuer_id,))
            conn.commit()
            cursor.close()

        with db_manager.get_historical_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM prices_daily WHERE instrument_id = %s", (instrument_id,))
            conn.commit()
            cursor.close()

    def test_profile_service_builds_and_persists_snapshot(self) -> None:
        config = get_config()
        db_manager = DatabaseManager(config)

        # If the `profiles` table has not been created yet (e.g. Alembic
        # migration 0007 not applied), skip rather than failing with an
        # UndefinedTable error.
        if not _profiles_table_exists(db_manager):
            pytest.skip("profiles table does not exist; run Alembic migration 0007 to enable this test")

        issuer_id, instrument_id = self._insert_issuer_and_instrument(db_manager)
        trading_days = self._insert_price_history(db_manager, instrument_id)

        try:
            as_of = trading_days[-1]

            reader = DataReader(db_manager=db_manager)
            calendar = TradingCalendar()
            storage = ProfileStorage(db_manager=db_manager)
            feature_builder = ProfileFeatureBuilder(db_manager=db_manager, data_reader=reader, calendar=calendar)
            embedder = BasicProfileEmbedder(embedding_dim=16)
            service = ProfileService(storage=storage, feature_builder=feature_builder, embedder=embedder)

            snapshot = service.get_snapshot(issuer_id, as_of)
            embedding = service.embed_profile(issuer_id, as_of)

            assert snapshot.issuer_id == issuer_id
            assert snapshot.as_of_date == as_of
            assert snapshot.structured.get("issuer_id") == issuer_id
            assert "numeric_features" in snapshot.structured
            assert "vol_flag" in snapshot.risk_flags
            assert "dd_flag" in snapshot.risk_flags

            assert embedding.shape[0] == 16

            # Verify a row exists in profiles table.
            with db_manager.get_runtime_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT issuer_id, as_of_date, structured, risk_flags
                    FROM profiles
                    WHERE issuer_id = %s AND as_of_date = %s
                    """,
                    (issuer_id, as_of),
                )
                row = cursor.fetchone()
                cursor.close()

            assert row is not None
        finally:
            self._cleanup(db_manager, issuer_id, instrument_id)
