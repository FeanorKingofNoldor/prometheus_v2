"""Integration tests for StabilityEngine with profile-aware STAB model.

This module validates that BasicPriceStabilityModel, when wired to a real
ProfileService and issuer/instrument mapping, correctly propagates
profile-based risk flags into the `weak_profile` field and persists the
result via StabilityEngine and StabilityStorage.
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


def _ensure_market(db_manager: DatabaseManager, market_id: str = "US_EQ") -> None:
    """Ensure a market row exists for the given market_id."""

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


def _insert_issuer_and_instrument(db_manager: DatabaseManager) -> tuple[str, str]:
    issuer_id = f"STAB_PROF_ISS_{generate_uuid()[:8]}"
    instrument_id = f"STAB_PROF_INST_{generate_uuid()[:8]}"
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
                (issuer_id, "COMPANY", "STAB Profile Test Corp"),
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
                (instrument_id, issuer_id, market_id, "EQUITY", "SPTC", "USD"),
            )
            conn.commit()
        finally:
            cursor.close()

    return issuer_id, instrument_id


def _insert_price_history(db_manager: DatabaseManager, instrument_id: str) -> list[date]:
    """Insert synthetic price history for the given instrument.

    The series is moderately volatile so that profile risk flags are
    non-trivial but deterministic.
    """

    calendar = TradingCalendar()
    start = date(2024, 1, 1)
    trading_days = calendar.trading_days_between(start, start + timedelta(days=90))
    trading_days = trading_days[:63]

    writer = DataWriter(db_manager=db_manager)
    price = 100.0
    bars: list[PriceBar] = []
    for i, d in enumerate(trading_days):
        # Alternate small up/down moves to introduce some realised vol.
        if i % 2 == 0:
            price *= 1.01
        else:
            price *= 0.99
        bars.append(
            PriceBar(
                instrument_id=instrument_id,
                trade_date=d,
                open=price,
                high=price * 1.01,
                low=price * 0.99,
                close=price,
                adjusted_close=price,
                volume=750_000.0,
                currency="USD",
                metadata={"source": "iter_stability_with_profiles"},
            )
        )

    writer.write_prices(bars)
    return trading_days


def _cleanup(db_manager: DatabaseManager, issuer_id: str, instrument_id: str) -> None:
    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM soft_target_classes WHERE entity_type = %s AND entity_id = %s",
                ("INSTRUMENT", instrument_id),
            )
            cursor.execute(
                "DELETE FROM stability_vectors WHERE entity_type = %s AND entity_id = %s",
                ("INSTRUMENT", instrument_id),
            )
            cursor.execute("DELETE FROM profiles WHERE issuer_id = %s", (issuer_id,))
            cursor.execute("DELETE FROM instruments WHERE instrument_id = %s", (instrument_id,))
            cursor.execute("DELETE FROM issuers WHERE issuer_id = %s", (issuer_id,))
            conn.commit()
        finally:
            cursor.close()

    with db_manager.get_historical_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM prices_daily WHERE instrument_id = %s",
                (instrument_id,),
            )
            conn.commit()
        finally:
            cursor.close()


@pytest.mark.integration
class TestStabilityEngineWithProfiles:
    """Integration tests for STAB with profile-aware model and service."""

    def test_stability_engine_propagates_weak_profile_from_profiles(self) -> None:
        config = get_config()
        db_manager = DatabaseManager(config)

        issuer_id, instrument_id = _insert_issuer_and_instrument(db_manager)
        trading_days = _insert_price_history(db_manager, instrument_id)

        try:
            as_of = trading_days[-1]

            calendar = TradingCalendar()
            reader = DataReader(db_manager=db_manager)

            # Set up real ProfileService on top of runtime DB.
            profile_storage = ProfileStorage(db_manager=db_manager)
            feature_builder = ProfileFeatureBuilder(
                db_manager=db_manager,
                data_reader=reader,
                calendar=calendar,
            )
            embedder = BasicProfileEmbedder(embedding_dim=16)
            profile_service = ProfileService(
                storage=profile_storage,
                feature_builder=feature_builder,
                embedder=embedder,
            )

            def instrument_to_issuer(eid: str) -> str | None:
                return issuer_id if eid == instrument_id else None

            model = BasicPriceStabilityModel(
                data_reader=reader,
                calendar=calendar,
                window_days=63,
                profile_service=profile_service,
                instrument_to_issuer=instrument_to_issuer,
                weak_profile_threshold=0.5,
            )

            # Build a profile snapshot so we can compute the expected
            # combined risk flag used by BasicPriceStabilityModel.
            snapshot = profile_service.get_snapshot(issuer_id, as_of)
            flags = snapshot.risk_flags
            vol_flag = float(flags.get("vol_flag", 0.0))
            dd_flag = float(flags.get("dd_flag", 0.0))
            lev_flag = float(flags.get("leverage_flag", 0.0))

            w_vol = model.weak_profile_weight_vol
            w_dd = model.weak_profile_weight_dd
            w_lev = model.weak_profile_weight_lev
            weight_sum = w_vol + w_dd + w_lev
            if weight_sum <= 0.0:
                combined = 0.0
            else:
                combined = (w_vol * vol_flag + w_dd * dd_flag + w_lev * lev_flag) / weight_sum

            stability_storage = StabilityStorage(db_manager=db_manager)
            engine = StabilityEngine(model=model, storage=stability_storage)

            state = engine.score_entity(as_of, "INSTRUMENT", instrument_id)

            expected_weak = combined >= model.weak_profile_threshold
            assert state.weak_profile == expected_weak

            # Verify that the persisted soft_target_classes row reflects
            # the same weak_profile flag and score breakdown.
            with db_manager.get_runtime_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT weak_profile, instability, high_fragility, complacent_pricing
                    FROM soft_target_classes
                    WHERE entity_type = %s AND entity_id = %s AND as_of_date = %s
                    """,
                    ("INSTRUMENT", instrument_id, as_of),
                )
                row = cursor.fetchone()
                cursor.close()

            assert row is not None
            weak_db, inst_db, frag_db, comp_db = row
            assert weak_db == state.weak_profile
            assert inst_db == pytest.approx(state.instability)
            assert frag_db == pytest.approx(state.high_fragility)
            assert comp_db == pytest.approx(state.complacent_pricing)
        finally:
            _cleanup(db_manager, issuer_id, instrument_id)
