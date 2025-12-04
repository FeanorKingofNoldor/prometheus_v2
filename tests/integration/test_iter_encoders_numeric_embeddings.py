"""Prometheus v2: Integration test for numeric window embeddings.

This test validates that the numeric encoder infrastructure can:
- Build a numeric window from real ``prices_daily`` data.
- Encode it via a simple deterministic model.
- Persist the resulting embedding into ``numeric_window_embeddings``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pytest

from prometheus.core.config import get_config
from prometheus.core.database import DatabaseManager
from prometheus.core.ids import generate_uuid
from prometheus.core.time import TradingCalendar
from prometheus.data.types import PriceBar
from prometheus.data.writer import DataWriter
from prometheus.data.reader import DataReader
from prometheus.encoders import (
    NumericEmbeddingModel,
    NumericEmbeddingStore,
    NumericWindowBuilder,
    NumericWindowEncoder,
    NumericWindowSpec,
)


@dataclass
class _MeanModel(NumericEmbeddingModel):
    """Deterministic model that averages features over the time axis."""

    def encode(self, window: np.ndarray) -> np.ndarray:  # type: ignore[override]
        return window.mean(axis=0)


@pytest.mark.integration
class TestNumericEmbeddingsIntegration:
    """Integration tests for numeric window encoder with Postgres DB."""

    def test_embed_and_persist_numeric_window(self) -> None:
        config = get_config()
        db_manager = DatabaseManager(config)

        # Insert minimal instrument + price history into historical_db.
        with db_manager.get_historical_connection() as conn:
            cursor = conn.cursor()

            instrument_id = f"TEST_ENC_{generate_uuid()[:8]}"
            issuer_id = f"TEST_ENC_ISS_{generate_uuid()[:8]}"
            market_id = f"TEST_ENC_MKT_{generate_uuid()[:8]}"

            cursor.execute(
                """
                INSERT INTO markets (market_id, name, region, timezone)
                VALUES (%s, %s, %s, %s)
                """,
                (market_id, "Encoder Test Market", "US", "America/New_York"),
            )

            cursor.execute(
                """
                INSERT INTO issuers (issuer_id, issuer_type, name)
                VALUES (%s, %s, %s)
                """,
                (issuer_id, "CORPORATION", "Encoder Test Corp"),
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
                (instrument_id, issuer_id, market_id, "EQUITY", "ENC", "USD"),
            )

            conn.commit()
            cursor.close()

        # Build a small block of price history.
        calendar = TradingCalendar()
        start = date(2024, 1, 1)
        trading_days = calendar.trading_days_between(start, start + timedelta(days=30))
        trading_days = trading_days[:10]

        writer = DataWriter(db_manager=db_manager)
        price = 100.0
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
                    volume=1_000_000.0,
                    currency="USD",
                    metadata={"source": "iter_encoders_numeric"},
                )
            )
            price += 1.0

        writer.write_prices(bars)

        reader = DataReader(db_manager=db_manager)
        builder = NumericWindowBuilder(reader, calendar)
        store = NumericEmbeddingStore(db_manager=db_manager)
        model = _MeanModel()

        spec = NumericWindowSpec(
            entity_type="INSTRUMENT",
            entity_id=instrument_id,
            window_days=5,
        )

        encoder = NumericWindowEncoder(
            builder=builder,
            model=model,
            store=store,
            model_id="mean_model_v1",
        )

        as_of = trading_days[-1]
        embedding = encoder.embed_and_store(spec, as_of)

        # Verify that a row was persisted into numeric_window_embeddings.
        with db_manager.get_historical_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT entity_type, entity_id, as_of_date, model_id, vector
                FROM numeric_window_embeddings
                WHERE entity_type = %s AND entity_id = %s AND as_of_date = %s
                  AND model_id = %s
                """,
                ("INSTRUMENT", instrument_id, as_of, "mean_model_v1"),
            )
            row = cursor.fetchone()
            cursor.close()

        assert row is not None
        ent_type, ent_id, as_of_db, model_id_db, vector_bytes = row
        assert ent_type == "INSTRUMENT"
        assert ent_id == instrument_id
        assert as_of_db == as_of
        assert model_id_db == "mean_model_v1"

        # Decode the stored vector and compare to the embedding.
        decoded = np.frombuffer(vector_bytes, dtype=np.float32)
        assert decoded.shape == embedding.shape
        np.testing.assert_allclose(decoded, embedding.astype(np.float32))

        # Cleanup inserted rows.
        with db_manager.get_historical_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM numeric_window_embeddings WHERE entity_id = %s",
                (instrument_id,),
            )
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
