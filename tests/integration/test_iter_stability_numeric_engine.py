"""Integration tests for the Stability (STAB) engine.

These tests validate that the basic price-based StabilityModel and
StabilityEngine can:
- Build features from real ``prices_daily`` data via DataReader.
- Compute stability vectors and soft-target states.
- Persist results into ``stability_vectors`` and ``soft_target_classes``.
- Replay latest state and history via StabilityEngine.
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
from prometheus.stability import (
    StabilityEngine,
    StabilityStorage,
    BasicPriceStabilityModel,
)


@pytest.mark.integration
class TestStabilityEngineNumericIntegration:
    """Integration tests for StabilityEngine with BasicPriceStabilityModel."""

    def _insert_price_history(self, db_manager: DatabaseManager) -> tuple[str, list[date]]:
        """Insert synthetic price history for a single instrument.

        Returns the instrument_id and the list of trading days used.
        """

        calendar = TradingCalendar()
        start = date(2024, 1, 1)
        trading_days = calendar.trading_days_between(start, start + timedelta(days=90))
        trading_days = trading_days[:63]

        instrument_id = f"TEST_STAB_{generate_uuid()[:8]}"

        writer = DataWriter(db_manager=db_manager)
        price = 100.0
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
                    volume=1_000_000.0,
                    currency="USD",
                    metadata={"source": "iter_stability_numeric"},
                )
            )
            price += 0.5

        writer.write_prices(bars)
        return instrument_id, trading_days

    def _cleanup(self, db_manager: DatabaseManager, instrument_id: str, entity_type: str, entity_id: str) -> None:
        """Remove test artefacts from stability and prices tables."""

        with db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM soft_target_classes WHERE entity_type = %s AND entity_id = %s",
                (entity_type, entity_id),
            )
            cursor.execute(
                "DELETE FROM stability_vectors WHERE entity_type = %s AND entity_id = %s",
                (entity_type, entity_id),
            )
            conn.commit()
            cursor.close()

        with db_manager.get_historical_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM prices_daily WHERE instrument_id = %s",
                (instrument_id,),
            )
            conn.commit()
            cursor.close()

    def test_stability_engine_persists_vector_and_soft_target(self) -> None:
        config = get_config()
        db_manager = DatabaseManager(config)

        instrument_id, trading_days = self._insert_price_history(db_manager)

        calendar = TradingCalendar()
        reader = DataReader(db_manager=db_manager)
        model = BasicPriceStabilityModel(data_reader=reader, calendar=calendar, window_days=63)

        storage = StabilityStorage(db_manager=db_manager)
        engine = StabilityEngine(model=model, storage=storage)

        entity_type = "INSTRUMENT"
        entity_id = instrument_id

        try:
            as_of = trading_days[-1]
            state = engine.score_entity(as_of, entity_type, entity_id)

            # stability_vectors row exists
            with db_manager.get_runtime_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT entity_type, entity_id, as_of_date, overall_score
                    FROM stability_vectors
                    WHERE entity_type = %s AND entity_id = %s AND as_of_date = %s
                    """,
                    (entity_type, entity_id, as_of),
                )
                row = cursor.fetchone()
                cursor.close()

            assert row is not None
            ent_type_db, ent_id_db, as_of_db, overall_db = row
            assert ent_type_db == entity_type
            assert ent_id_db == entity_id
            assert as_of_db == as_of
            assert overall_db == pytest.approx(state.soft_target_score)

            # soft_target_classes row exists
            with db_manager.get_runtime_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT entity_type, entity_id, as_of_date, soft_target_class, soft_target_score
                    FROM soft_target_classes
                    WHERE entity_type = %s AND entity_id = %s AND as_of_date = %s
                    """,
                    (entity_type, entity_id, as_of),
                )
                row = cursor.fetchone()
                cursor.close()

            assert row is not None
            ent_type_db, ent_id_db, as_of_db, class_db, score_db = row
            assert ent_type_db == entity_type
            assert ent_id_db == entity_id
            assert as_of_db == as_of
            assert class_db == state.soft_target_class.value
            assert score_db == pytest.approx(state.soft_target_score)

            # Latest state and history from engine
            latest = engine.get_latest_state(entity_type, entity_id)
            assert latest is not None
            assert latest.soft_target_class == state.soft_target_class

            history = engine.get_history(entity_type, entity_id, as_of, as_of)
            assert len(history) == 1
            assert history[0].soft_target_score == pytest.approx(state.soft_target_score)
        finally:
            self._cleanup(db_manager, instrument_id, entity_type, entity_id)
