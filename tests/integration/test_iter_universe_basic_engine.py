"""Integration tests for the basic Universe engine.

These tests validate that BasicUniverseModel and UniverseEngine can:
- Enumerate real instruments from the DB.
- Use 63d price history for liquidity filters.
- Consume profile-aware STAB soft-target states from the DB.
- Persist universe membership decisions into ``universe_members``.
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
from prometheus.stability import (
    StabilityEngine,
    StabilityStorage,
    BasicPriceStabilityModel,
)
from prometheus.universe import (
    UniverseEngine,
    UniverseStorage,
    BasicUniverseModel,
)


def _ensure_market(db_manager: DatabaseManager, market_id: str = "US_EQ") -> None:
    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO markets (market_id, name, region, timezone)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (market_id) DO NOTHING
                """,
                (market_id, "US Equities", "US", "America/New_York"),
            )
            conn.commit()
        finally:
            cursor.close()


def _insert_issuer_and_instrument(db_manager: DatabaseManager, symbol: str, name: str) -> tuple[str, str]:
    issuer_id = f"UNIV_ISS_{generate_uuid()[:8]}"
    instrument_id = f"UNIV_INST_{generate_uuid()[:8]}"
    market_id = "US_EQ"

    _ensure_market(db_manager, market_id)

    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO issuers (issuer_id, issuer_type, name)
                VALUES (%s, %s, %s)
                """,
                (issuer_id, "COMPANY", name),
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
                (instrument_id, issuer_id, market_id, "EQUITY", symbol, "USD"),
            )
            conn.commit()
        finally:
            cursor.close()

    return issuer_id, instrument_id


def _insert_price_history_stable(db_manager: DatabaseManager, instrument_id: str) -> list[date]:
    """Stable-ish uptrend with decent volume."""

    calendar = TradingCalendar()
    start = date(2024, 1, 1)
    trading_days = calendar.trading_days_between(start, start + timedelta(days=90))
    trading_days = trading_days[:63]

    writer = DataWriter(db_manager=db_manager)
    price = 100.0
    bars: list[PriceBar] = []
    for d in trading_days:
        price *= 1.002
        bars.append(
            PriceBar(
                instrument_id=instrument_id,
                trade_date=d,
                open=price,
                high=price * 1.01,
                low=price * 0.99,
                close=price,
                adjusted_close=price,
                volume=500_000.0,
                currency="USD",
                metadata={"source": "iter_universe"},
            )
        )

    writer.write_prices(bars)
    return trading_days


def _insert_price_history_fragile(db_manager: DatabaseManager, instrument_id: str) -> list[date]:
    """High-vol drawdown series to trigger fragile/weak profile exclusion."""

    calendar = TradingCalendar()
    start = date(2024, 1, 1)
    trading_days = calendar.trading_days_between(start, start + timedelta(days=90))
    trading_days = trading_days[:63]

    writer = DataWriter(db_manager=db_manager)
    price = 100.0
    bars: list[PriceBar] = []
    for i, d in enumerate(trading_days):
        if i < 20:
            price *= 1.01
        else:
            price *= 0.97
        bars.append(
            PriceBar(
                instrument_id=instrument_id,
                trade_date=d,
                open=price,
                high=price * 1.02,
                low=price * 0.98,
                close=price,
                adjusted_close=price,
                volume=500_000.0,
                currency="USD",
                metadata={"source": "iter_universe"},
            )
        )

    writer.write_prices(bars)
    return trading_days


def _cleanup(db_manager: DatabaseManager, issuer_ids: list[str], instrument_ids: list[str]) -> None:
    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM universe_members WHERE entity_id = ANY(%s)",
                (instrument_ids,),
            )
            cursor.execute(
                "DELETE FROM soft_target_classes WHERE entity_type = 'INSTRUMENT' AND entity_id = ANY(%s)",
                (instrument_ids,),
            )
            cursor.execute(
                "DELETE FROM stability_vectors WHERE entity_type = 'INSTRUMENT' AND entity_id = ANY(%s)",
                (instrument_ids,),
            )
            cursor.execute("DELETE FROM profiles WHERE issuer_id = ANY(%s)", (issuer_ids,))
            cursor.execute("DELETE FROM instruments WHERE instrument_id = ANY(%s)", (instrument_ids,))
            cursor.execute("DELETE FROM issuers WHERE issuer_id = ANY(%s)", (issuer_ids,))
            conn.commit()
        finally:
            cursor.close()

    with db_manager.get_historical_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM prices_daily WHERE instrument_id = ANY(%s)", (instrument_ids,))
            conn.commit()
        finally:
            cursor.close()


@pytest.mark.integration
class TestBasicUniverseEngineIntegration:
    """Integration tests for BasicUniverseModel and UniverseEngine."""

    def test_universe_engine_builds_and_persists_members(self) -> None:
        config = get_config()
        db_manager = DatabaseManager(config)

        # Two instruments: one relatively stable, one fragile with weak profile.
        issuer_stable, inst_stable = _insert_issuer_and_instrument(db_manager, "STBL", "Stable Corp")
        issuer_fragile, inst_fragile = _insert_issuer_and_instrument(db_manager, "FRGL", "Fragile Corp")

        days_stable = _insert_price_history_stable(db_manager, inst_stable)
        days_fragile = _insert_price_history_fragile(db_manager, inst_fragile)

        try:
            as_of = min(days_stable[-1], days_fragile[-1])

            calendar = TradingCalendar()
            reader = DataReader(db_manager=db_manager)

            # Real ProfileService
            profile_storage = ProfileStorage(db_manager=db_manager)
            feature_builder = ProfileFeatureBuilder(db_manager=db_manager, data_reader=reader, calendar=calendar)
            embedder = BasicProfileEmbedder(embedding_dim=16)
            profile_service = ProfileService(storage=profile_storage, feature_builder=feature_builder, embedder=embedder)

            # Profile-aware STAB engine
            stab_storage = StabilityStorage(db_manager=db_manager)

            def instrument_to_issuer(eid: str) -> str | None:
                if eid == inst_stable:
                    return issuer_stable
                if eid == inst_fragile:
                    return issuer_fragile
                return None

            stab_model = BasicPriceStabilityModel(
                data_reader=reader,
                calendar=calendar,
                window_days=63,
                profile_service=profile_service,
                instrument_to_issuer=instrument_to_issuer,
                weak_profile_threshold=0.6,
            )

            stab_engine = StabilityEngine(model=stab_model, storage=stab_storage)

            # Score both instruments to populate stability_vectors and soft_target_classes.
            stab_engine.score_entity(as_of, "INSTRUMENT", inst_stable)
            stab_engine.score_entity(as_of, "INSTRUMENT", inst_fragile)

            # Universe engine wired to BasicUniverseModel.
            univ_storage = UniverseStorage(db_manager=db_manager)
            univ_model = BasicUniverseModel(
                db_manager=db_manager,
                calendar=calendar,
                data_reader=reader,
                profile_service=profile_service,
                stability_storage=stab_storage,
                market_ids=("US_EQ",),
                min_avg_volume=100_000.0,
                max_soft_target_score=80.0,
                exclude_breakers=True,
                exclude_weak_profile_when_fragile=True,
                # Disable capacity caps for this targeted integration test
                # so that both instruments show up as candidates and only
                # fragility/profile logic controls inclusion.
                max_universe_size=None,
                sector_max_names=None,
                min_price=0.0,
            )
            univ_engine = UniverseEngine(model=univ_model, storage=univ_storage)

            universe_id = "CORE_EQ"
            members = univ_engine.build_and_save(as_of, universe_id)

            # We should have at least entries for both instruments.
            entity_ids = {m.entity_id for m in members}
            assert inst_stable in entity_ids
            assert inst_fragile in entity_ids

            # Stable instrument should be included; fragile+weak_profile should be excluded.
            stable_member = next(m for m in members if m.entity_id == inst_stable)
            fragile_member = next(m for m in members if m.entity_id == inst_fragile)

            assert stable_member.included is True
            assert fragile_member.included is False

            # Check that members were persisted in universe_members.
            persisted = univ_storage.get_universe(as_of, universe_id, included_only=False)
            persisted_ids = {m.entity_id for m in persisted}
            assert {inst_stable, inst_fragile} <= persisted_ids
        finally:
            _cleanup(db_manager, [issuer_stable, issuer_fragile], [inst_stable, inst_fragile])
