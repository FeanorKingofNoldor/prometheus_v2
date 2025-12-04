"""Tests for NumericRegimeModel (numeric embedding-based RegimeModel).

These tests verify that NumericRegimeModel:
- Delegates embedding to a supplied numeric encoder.
- Assigns regimes based on nearest prototypes in embedding space.
- Computes confidence via a softmax over negative distances.
- Handles configuration errors (unknown regions, mismatched prototype shapes).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pytest

from prometheus.encoders import NumericWindowSpec
from prometheus.regime.model_numeric import (
    NumericRegimeModel,
    NumericWindowEncoderLike,
    RegimePrototype,
)
from prometheus.regime.types import RegimeLabel


@dataclass
class _StubEncoder(NumericWindowEncoderLike):
    """Stub numeric encoder returning a preconfigured embedding."""

    embedding: np.ndarray

    def __post_init__(self) -> None:
        self.calls: list[tuple[NumericWindowSpec, date]] = []

    def embed_and_store(self, spec: NumericWindowSpec, as_of_date: date) -> np.ndarray:  # type: ignore[override]
        self.calls.append((spec, as_of_date))
        return self.embedding


class TestNumericRegimeModelClassification:
    """Tests for basic classification behaviour."""

    def test_classify_uses_encoder_and_nearest_prototype(self) -> None:
        embedding = np.array([0.1, 0.2, 0.3], dtype=np.float32)

        encoder = _StubEncoder(embedding=embedding)

        prototypes = [
            RegimePrototype(label=RegimeLabel.CARRY, center=np.array([0.0, 0.0, 0.0], dtype=np.float32)),
            RegimePrototype(label=RegimeLabel.CRISIS, center=np.array([1.0, 1.0, 1.0], dtype=np.float32)),
        ]

        model = NumericRegimeModel(
            encoder=encoder,
            region_instruments={"US": "SPY"},
            window_days=63,
            prototypes=prototypes,
            temperature=1.0,
        )

        as_of = date(2024, 1, 5)
        state = model.classify(as_of_date=as_of, region="US")

        # Encoder should have been called exactly once with the expected spec.
        assert len(encoder.calls) == 1
        called_spec, called_date = encoder.calls[0]
        assert called_date == as_of
        assert called_spec.entity_type == "INSTRUMENT"
        assert called_spec.entity_id == "SPY"
        assert called_spec.window_days == 63

        # Regime should be assigned to the nearest prototype (CARRY here).
        assert state.regime_label == RegimeLabel.CARRY
        np.testing.assert_allclose(state.regime_embedding, embedding)

        assert state.metadata is not None
        distances = state.metadata["distances"]
        assert set(distances.keys()) == {RegimeLabel.CARRY.value, RegimeLabel.CRISIS.value}

    def test_confidence_behaves_like_softmax_over_distances(self) -> None:
        embedding = np.array([0.0, 0.0], dtype=np.float32)
        encoder = _StubEncoder(embedding=embedding)

        prototypes = [
            RegimePrototype(label=RegimeLabel.CARRY, center=np.array([0.0, 0.0], dtype=np.float32)),
            RegimePrototype(label=RegimeLabel.NEUTRAL, center=np.array([1.0, 0.0], dtype=np.float32)),
            RegimePrototype(label=RegimeLabel.RISK_OFF, center=np.array([2.0, 0.0], dtype=np.float32)),
        ]

        model_cool = NumericRegimeModel(
            encoder=encoder,
            region_instruments={"US": "SPY"},
            window_days=63,
            prototypes=prototypes,
            temperature=1.0,
        )
        state_cool = model_cool.classify(date(2024, 1, 5), "US")

        model_hot = NumericRegimeModel(
            encoder=encoder,
            region_instruments={"US": "SPY"},
            window_days=63,
            prototypes=prototypes,
            temperature=0.1,
        )
        state_hot = model_hot.classify(date(2024, 1, 5), "US")

        assert state_cool.regime_label == RegimeLabel.CARRY
        assert state_hot.regime_label == RegimeLabel.CARRY

        # Lower temperature should yield higher confidence for the best label.
        assert 0.0 <= state_cool.confidence <= 1.0
        assert 0.0 <= state_hot.confidence <= 1.0
        assert state_hot.confidence > state_cool.confidence


class TestNumericRegimeModelConfigurationErrors:
    """Tests for configuration and usage error handling."""

    def test_unknown_region_raises_value_error(self) -> None:
        encoder = _StubEncoder(embedding=np.array([0.0, 0.0], dtype=np.float32))
        prototypes = [
            RegimePrototype(label=RegimeLabel.CARRY, center=np.array([0.0, 0.0], dtype=np.float32)),
        ]

        model = NumericRegimeModel(
            encoder=encoder,
            region_instruments={"US": "SPY"},
            window_days=63,
            prototypes=prototypes,
        )

        with pytest.raises(ValueError):
            model.classify(date(2024, 1, 5), region="EU")

    def test_mismatched_prototype_shapes_raise_on_init(self) -> None:
        encoder = _StubEncoder(embedding=np.array([0.0, 0.0], dtype=np.float32))

        prototypes = [
            RegimePrototype(label=RegimeLabel.CARRY, center=np.array([0.0, 0.0], dtype=np.float32)),
            RegimePrototype(label=RegimeLabel.CRISIS, center=np.array([0.0, 0.0, 0.0], dtype=np.float32)),
        ]

        with pytest.raises(ValueError):
            NumericRegimeModel(
                encoder=encoder,
                region_instruments={"US": "SPY"},
                window_days=63,
                prototypes=prototypes,
            )

    def test_embedding_shape_mismatch_raises(self) -> None:
        # Prototypes in 2D space but encoder returns 3D embedding.
        encoder = _StubEncoder(embedding=np.array([0.0, 0.0, 0.0], dtype=np.float32))
        prototypes = [
            RegimePrototype(label=RegimeLabel.CARRY, center=np.array([0.0, 0.0], dtype=np.float32)),
        ]

        model = NumericRegimeModel(
            encoder=encoder,
            region_instruments={"US": "SPY"},
            window_days=63,
            prototypes=prototypes,
        )

        with pytest.raises(ValueError):
            model.classify(date(2024, 1, 5), region="US")
