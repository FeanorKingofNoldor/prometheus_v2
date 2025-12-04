"""Prometheus v2: Tests for numeric window encoder infrastructure.

These tests exercise:
- NumericWindowBuilder: construction of fixed-size windows from price data.
- NumericWindowEncoder: composition of builder, model, and store.

The tests intentionally use in-memory stubs for DataReader, models, and
stores so that they do not depend on a real database.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List

import numpy as np
import pandas as pd

from prometheus.core.time import TradingCalendar
from prometheus.encoders import (
    NumericEmbeddingModel,
    NumericEmbeddingStore,
    NumericWindowBuilder,
    NumericWindowEncoder,
    NumericWindowSpec,
)
from prometheus.encoders.models_simple_numeric import (
    FlattenNumericEmbeddingModel,
    PadToDimNumericEmbeddingModel,
)


class _StubDataReader:
    """Stub for DataReader.read_prices using an in-memory DataFrame."""

    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df

    def read_prices(self, instrument_ids, start_date, end_date):  # type: ignore[no-untyped-def]
        # Ignore filters; tests ensure builder validates sizes correctly.
        return self._df


class _StubStore(NumericEmbeddingStore):
    """In-memory stub for NumericEmbeddingStore.

    The base class expects a DatabaseManager, but in these tests we
    override save_embedding to avoid touching a real database.
    """

    def __init__(self) -> None:  # type: ignore[no-untyped-def]
        # Bypass parent initialisation; we don't need a real db_manager.
        self.saved = []  # type: ignore[attr-defined]

    def save_embedding(  # type: ignore[override]
        self,
        spec: NumericWindowSpec,
        as_of_date: date,
        model_id: str,
        vector: np.ndarray,
    ) -> None:
        self.saved.append((spec, as_of_date, model_id, vector))


@dataclass
class _DummyModel(NumericEmbeddingModel):
    """Deterministic test model that averages features over time."""

    def encode(self, window: np.ndarray) -> np.ndarray:  # type: ignore[override]
        # Mean over the time dimension to yield a 1 x F embedding.
        return window.mean(axis=0)


class TestNumericWindowBuilder:
    """Tests for NumericWindowBuilder behaviour."""

    def _build_price_df(self) -> pd.DataFrame:
        instrument_id = "TEST_INST_ENCODING"
        start = date(2024, 1, 1)
        dates: List[date] = [start + timedelta(days=i) for i in range(10)]

        rows = []
        close = 100.0
        volume = 1_000_000.0
        for d in dates:
            rows.append(
                (
                    instrument_id,
                    d,
                    close,
                    close + 1.0,
                    close - 1.0,
                    close,
                    close,
                    volume,
                    "USD",
                    {},
                )
            )
            close += 1.0
            volume += 10_000.0

        df = pd.DataFrame(
            rows,
            columns=[
                "instrument_id",
                "trade_date",
                "open",
                "high",
                "low",
                "close",
                "adjusted_close",
                "volume",
                "currency",
                "metadata",
            ],
        )
        return df

    def test_build_window_returns_expected_shape_and_values(self) -> None:
        df = self._build_price_df()
        reader = _StubDataReader(df)
        calendar = TradingCalendar()

        spec = NumericWindowSpec(entity_type="INSTRUMENT", entity_id="TEST_INST_ENCODING", window_days=5)
        builder = NumericWindowBuilder(reader, calendar)

        as_of = date(2024, 1, 10)
        window = builder.build_window(spec, as_of)

        assert window.shape == (5, 3)

        closes = df.sort_values("trade_date")["close"].to_numpy()[-5:]
        volumes = df.sort_values("trade_date")["volume"].to_numpy()[-5:]

        # First feature column: closes
        np.testing.assert_allclose(window[:, 0], closes.astype(np.float32))

        # Second feature column: volumes
        np.testing.assert_allclose(window[:, 1], volumes.astype(np.float32))

        # Third feature column: log returns, first element ~ 0.0
        log_rets = window[:, 2]
        assert abs(log_rets[0]) < 1e-6
        expected_log_rets = np.zeros_like(closes, dtype=float)
        expected_log_rets[1:] = np.log(closes[1:] / closes[:-1])
        np.testing.assert_allclose(log_rets, expected_log_rets.astype(np.float32), rtol=1e-6, atol=1e-6)


class TestNumericWindowEncoder:
    """Tests for NumericWindowEncoder orchestration."""

    def test_encoder_uses_builder_model_and_store(self) -> None:
        # Simple 3x2 window: rows are [[1, 2], [3, 4], [5, 6]].
        window = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]], dtype=np.float32)

        class _FixedBuilder(NumericWindowBuilder):  # type: ignore[misc]
            def __init__(self) -> None:  # type: ignore[no-untyped-def]
                ...

            def build_window(self, spec: NumericWindowSpec, as_of_date: date) -> np.ndarray:  # type: ignore[override]
                return window

        spec = NumericWindowSpec(entity_type="INSTRUMENT", entity_id="TEST", window_days=3)
        builder = _FixedBuilder()
        model = _DummyModel()
        store = _StubStore()

        encoder = NumericWindowEncoder(builder=builder, model=model, store=store, model_id="dummy_model")
        embedding = encoder.embed_and_store(spec, date(2024, 1, 5))

        # Embedding should be the row-wise mean of the window.
        expected = window.mean(axis=0)
        np.testing.assert_allclose(embedding, expected)

        # Store should have recorded exactly one embedding with matching content.
        assert len(store.saved) == 1
        saved_spec, saved_date, saved_model_id, saved_vector = store.saved[0]
        assert saved_spec == spec
        assert saved_date == date(2024, 1, 5)
        assert saved_model_id == "dummy_model"
        np.testing.assert_allclose(saved_vector, embedding)


class TestPadToDimNumericEmbeddingModel:
    """Tests for the padded numeric embedding model used by num-regime-core-v1.

    These tests are unit-level and do not touch the database; they focus on
    the flatten + pad/truncate behaviour and resulting embedding shape.
    """

    def test_pads_flattened_window_to_target_dim_for_regime_default(self) -> None:
        """63x3 regime-style window should produce a 384-dim embedding.

        This reflects the v0 behaviour for ``num-regime-core-v1``: the
        flattened window (63 days x 3 features) is padded with zeros up to
        the standard 384-dim embedding size.
        """

        window_days = 63
        num_features = 3
        window = np.ones((window_days, num_features), dtype=np.float32)

        model = PadToDimNumericEmbeddingModel(target_dim=384)
        embedding = model.encode(window)

        assert embedding.shape == (384,)
        assert embedding.dtype == np.float32

        # First part of the embedding should match the plain flattened vector.
        flat = FlattenNumericEmbeddingModel().encode(window)
        assert flat.shape[0] == window_days * num_features
        np.testing.assert_allclose(embedding[: flat.shape[0]], flat)

        # Remaining tail should be zero-padded.
        np.testing.assert_allclose(embedding[flat.shape[0] :], 0.0)

    def test_truncates_when_flat_length_exceeds_target_dim(self) -> None:
        """If the flattened window is longer than target_dim, it is truncated."""

        # 400 scalar values arranged as a 200x2 window -> flattened length 400.
        base = np.arange(400, dtype=np.float32)
        window = base.reshape(200, 2)

        model = PadToDimNumericEmbeddingModel(target_dim=384)
        embedding = model.encode(window)

        assert embedding.shape == (384,)
        np.testing.assert_allclose(embedding, base[:384])
