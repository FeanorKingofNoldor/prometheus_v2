"""Integration tests for the numeric Regime Engine.

These tests validate that the numeric RegimeModel and RegimeEngine can:
- Build numeric windows from real ``prices_daily`` data via DataReader.
- Encode them with a deterministic numeric encoder.
- Persist embeddings into ``numeric_window_embeddings``.
- Persist regime states (including embeddings) into ``regimes``.
- Replay history via RegimeEngine.get_history.
- Compute empirical transition matrices from ``regime_transitions``.
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
from prometheus.encoders.models_simple_numeric import PadToDimNumericEmbeddingModel
from prometheus.regime import (
    RegimeEngine,
    RegimeStorage,
    NumericRegimeModel,
    RegimePrototype,
    RegimeLabel,
    RegimeState,
)


@dataclass
class _MeanModel(NumericEmbeddingModel):
    """Deterministic model that averages features over the time axis."""

    def encode(self, window: np.ndarray) -> np.ndarray:  # type: ignore[override]
        return window.mean(axis=0)


@pytest.mark.integration
class TestRegimeEngineNumericIntegration:
    """Integration tests for RegimeEngine with NumericRegimeModel."""

    def _insert_price_history(self, db_manager: DatabaseManager) -> tuple[str, list[date]]:
        """Insert synthetic price history for a single instrument.

        Returns the instrument_id and the list of trading days used.
        """

        calendar = TradingCalendar()
        start = date(2024, 1, 1)
        trading_days = calendar.trading_days_between(start, start + timedelta(days=30))
        trading_days = trading_days[:10]

        instrument_id = f"TEST_REGIME_{generate_uuid()[:8]}"

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
                    metadata={"source": "iter_regime_numeric"},
                )
            )
            price += 1.0

        writer.write_prices(bars)
        return instrument_id, trading_days

    def _cleanup(self, db_manager: DatabaseManager, instrument_id: str, region: str) -> None:
        """Remove test artefacts from regimes, transitions, and prices tables."""

        with db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM regime_transitions WHERE region = %s", (region,))
            cursor.execute("DELETE FROM regimes WHERE region = %s", (region,))
            conn.commit()
            cursor.close()

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
            conn.commit()
            cursor.close()

    def test_numeric_regime_engine_persists_state_and_embedding(self) -> None:
        """End-to-end test: encoder + model + engine + storage.

        Verifies that calling RegimeEngine.get_regime:
        - writes a numeric embedding into numeric_window_embeddings,
        - writes a regime row into regimes with a stored embedding,
        - allows replay via get_history.
        """

        config = get_config()
        db_manager = DatabaseManager(config)

        instrument_id, trading_days = self._insert_price_history(db_manager)

        calendar = TradingCalendar()
        reader = DataReader(db_manager=db_manager)
        builder = NumericWindowBuilder(reader, calendar)
        store = NumericEmbeddingStore(db_manager=db_manager)
        model = _MeanModel()

        window_days = 5
        spec = NumericWindowSpec(
            entity_type="INSTRUMENT",
            entity_id=instrument_id,
            window_days=window_days,
        )

        encoder = NumericWindowEncoder(
            builder=builder,
            model=model,
            store=store,
            model_id="regime_mean_model_v1",
        )

        region = "TEST_REGIME_NUMERIC"
        regime_model = NumericRegimeModel(
            encoder=encoder,
            region_instruments={region: instrument_id},
            window_days=window_days,
            prototypes=[
                RegimePrototype(
                    label=RegimeLabel.NEUTRAL,
                    center=np.array([100.0, 1_000_000.0, 0.0], dtype=np.float32),
                ),
                RegimePrototype(
                    label=RegimeLabel.CRISIS,
                    center=np.array([500.0, 1_000_000.0, 0.0], dtype=np.float32),
                ),
            ],
            temperature=1.0,
        )

        storage = RegimeStorage(db_manager=db_manager)
        engine = RegimeEngine(model=regime_model, storage=storage)

        try:
            as_of = trading_days[-1]
            state = engine.get_regime(as_of, region=region)

            assert state.as_of_date == as_of
            assert state.region == region
            assert state.regime_label in (RegimeLabel.NEUTRAL, RegimeLabel.CRISIS)
            assert state.regime_embedding is not None
            embedding = state.regime_embedding

            # Verify numeric_window_embeddings row exists and matches the embedding.
            with db_manager.get_historical_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT model_id, vector
                    FROM numeric_window_embeddings
                    WHERE entity_type = %s AND entity_id = %s AND as_of_date = %s
                      AND model_id = %s
                    """,
                    ("INSTRUMENT", instrument_id, as_of, "regime_mean_model_v1"),
                )
                row = cursor.fetchone()
                cursor.close()

            assert row is not None
            model_id_db, vector_bytes = row
            assert model_id_db == "regime_mean_model_v1"
            decoded_vec = np.frombuffer(vector_bytes, dtype=np.float32)
            assert decoded_vec.shape == embedding.shape
            np.testing.assert_allclose(decoded_vec, embedding.astype(np.float32))

            # Verify regimes row exists and stores the regime embedding.
            with db_manager.get_runtime_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT as_of_date, region, regime_label, regime_embedding, confidence, metadata
                    FROM regimes
                    WHERE region = %s AND as_of_date = %s
                    """,
                    (region, as_of),
                )
                row = cursor.fetchone()
                cursor.close()

            assert row is not None
            as_of_db, region_db, label_db, embedding_bytes, confidence_db, metadata_db = row
            assert as_of_db == as_of
            assert region_db == region
            assert label_db == state.regime_label.value
            assert confidence_db == pytest.approx(state.confidence)
            assert metadata_db is not None
            assert embedding_bytes is not None

            decoded_regime_vec = np.frombuffer(embedding_bytes, dtype=np.float32)
            assert decoded_regime_vec.shape == embedding.shape
            np.testing.assert_allclose(decoded_regime_vec, embedding.astype(np.float32))

            # get_history should replay the same single state for this date.
            history = engine.get_history(region, as_of, as_of)
            assert len(history) == 1
            assert history[0].regime_label == state.regime_label
        finally:
            self._cleanup(db_manager, instrument_id, region)

    def test_numeric_regime_engine_with_num_regime_core_encoder_384dim(self) -> None:
        """End-to-end test using num-regime-core-v1 (384-dim numeric encoder).

        This test mirrors the basic numeric regime integration but uses the
        PadToDimNumericEmbeddingModel with ``target_dim=384`` and
        ``model_id='num-regime-core-v1'`` to ensure the full pipeline works
        with our standard 384-dimensional numeric embeddings.
        """

        config = get_config()
        db_manager = DatabaseManager(config)

        instrument_id, trading_days = self._insert_price_history(db_manager)

        calendar = TradingCalendar()
        reader = DataReader(db_manager=db_manager)
        builder = NumericWindowBuilder(reader, calendar)
        store = NumericEmbeddingStore(db_manager=db_manager)
        model = PadToDimNumericEmbeddingModel(target_dim=384)

        window_days = 5
        encoder = NumericWindowEncoder(
            builder=builder,
            model=model,
            store=store,
            model_id="num-regime-core-v1",
        )

        region = "TEST_REGIME_NUMERIC_384"
        neutral_center = np.zeros(384, dtype=np.float32)
        crisis_center = np.ones(384, dtype=np.float32)

        regime_model = NumericRegimeModel(
            encoder=encoder,
            region_instruments={region: instrument_id},
            window_days=window_days,
            prototypes=[
                RegimePrototype(label=RegimeLabel.NEUTRAL, center=neutral_center),
                RegimePrototype(label=RegimeLabel.CRISIS, center=crisis_center),
            ],
            temperature=1.0,
        )

        storage = RegimeStorage(db_manager=db_manager)
        engine = RegimeEngine(model=regime_model, storage=storage)

        try:
            as_of = trading_days[-1]
            state = engine.get_regime(as_of, region=region)

            assert state.as_of_date == as_of
            assert state.region == region
            assert state.regime_embedding is not None
            embedding = state.regime_embedding
            assert embedding.shape == (384,)

            # Verify numeric_window_embeddings row exists and matches the embedding.
            with db_manager.get_historical_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT model_id, vector
                    FROM numeric_window_embeddings
                    WHERE entity_type = %s AND entity_id = %s AND as_of_date = %s
                      AND model_id = %s
                    """,
                    ("INSTRUMENT", instrument_id, as_of, "num-regime-core-v1"),
                )
                row = cursor.fetchone()
                cursor.close()

            assert row is not None
            model_id_db, vector_bytes = row
            assert model_id_db == "num-regime-core-v1"
            decoded_vec = np.frombuffer(vector_bytes, dtype=np.float32)
            assert decoded_vec.shape == embedding.shape
            np.testing.assert_allclose(decoded_vec, embedding.astype(np.float32))

            # Verify regimes row exists and stores the 384-dim regime embedding.
            with db_manager.get_runtime_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT as_of_date, region, regime_label, regime_embedding, confidence, metadata
                    FROM regimes
                    WHERE region = %s AND as_of_date = %s
                    """,
                    (region, as_of),
                )
                row = cursor.fetchone()
                cursor.close()

            assert row is not None
            as_of_db, region_db, label_db, embedding_bytes, confidence_db, metadata_db = row
            assert as_of_db == as_of
            assert region_db == region
            assert label_db == state.regime_label.value
            assert confidence_db == pytest.approx(state.confidence)
            assert metadata_db is not None
            assert embedding_bytes is not None

            decoded_regime_vec = np.frombuffer(embedding_bytes, dtype=np.float32)
            assert decoded_regime_vec.shape == embedding.shape
            np.testing.assert_allclose(decoded_regime_vec, embedding.astype(np.float32))

        finally:
            self._cleanup(db_manager, instrument_id, region)

    def test_transition_matrix_computation_from_db(self) -> None:
        """Compute empirical transition matrix from regime_transitions table."""

        config = get_config()
        db_manager = DatabaseManager(config)
        storage = RegimeStorage(db_manager=db_manager)

        region = "TEST_REGIME_TM"

        # Create a small synthetic sequence of transitions for this region.
        d1 = date(2024, 1, 5)
        d2 = date(2024, 1, 6)
        d3 = date(2024, 1, 7)
        d4 = date(2024, 1, 8)

        s1 = RegimeState(d1, region, RegimeLabel.NEUTRAL, 0.7, None, None)
        s2 = RegimeState(d2, region, RegimeLabel.CARRY, 0.8, None, None)
        s3 = RegimeState(d3, region, RegimeLabel.CARRY, 0.9, None, None)
        s4 = RegimeState(d4, region, RegimeLabel.CRISIS, 0.95, None, None)

        try:
            storage.record_transition(s1, s2)  # NEUTRAL -> CARRY
            storage.record_transition(s2, s3)  # CARRY -> CARRY
            storage.record_transition(s3, s4)  # CARRY -> CRISIS

            matrix = storage.get_transition_matrix(region)

            # From NEUTRAL we only observed NEUTRAL -> CARRY.
            assert matrix[RegimeLabel.NEUTRAL.value][RegimeLabel.CARRY.value] == pytest.approx(1.0)

            # From CARRY we observed one self-transition and one to CRISIS.
            from_carry = matrix[RegimeLabel.CARRY.value]
            assert from_carry[RegimeLabel.CARRY.value] == pytest.approx(0.5)
            assert from_carry[RegimeLabel.CRISIS.value] == pytest.approx(0.5)
        finally:
            # Cleanup only the test region's transitions.
            with db_manager.get_runtime_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM regime_transitions WHERE region = %s",
                    (region,),
                )
                conn.commit()
                cursor.close()
