"""Prometheus v2: Tests for joint encoder infrastructure.

These tests cover:
- JointExample structure.
- JointEmbeddingService orchestration using in-memory stubs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Mapping

import numpy as np
import pytest

from prometheus.encoders import (
    JointEmbeddingModel,
    JointEmbeddingService,
    JointEmbeddingStore,
    JointExample,
)
from prometheus.encoders.models_joint_simple import SimpleAverageJointModel, IdentityNumericJointModel


@dataclass
class _DummyJointModel(JointEmbeddingModel):
    """Deterministic joint model for testing.

    It concatenates numeric and text embeddings if present, otherwise
    falls back to zeros.
    """

    def embed_batch(self, examples: List[JointExample]) -> np.ndarray:  # type: ignore[override]
        vectors = []
        for ex in examples:
            parts = []
            if ex.numeric_embedding is not None:
                parts.append(np.asarray(ex.numeric_embedding, dtype=np.float32))
            if ex.text_embedding is not None:
                parts.append(np.asarray(ex.text_embedding, dtype=np.float32))
            if not parts:
                parts.append(np.zeros(1, dtype=np.float32))
            vectors.append(np.concatenate(parts))
        return np.stack(vectors, axis=0)


class _StubStore(JointEmbeddingStore):
    """In-memory stub for JointEmbeddingStore.

    Overrides save_embeddings to avoid DB access and capture calls.
    """

    def __init__(self) -> None:  # type: ignore[no-untyped-def]
        self.saved = []  # type: ignore[attr-defined]

    def save_embeddings(  # type: ignore[override]
        self,
        examples: List[JointExample],
        model_id: str,
        vectors: np.ndarray,
    ) -> None:
        self.saved.append((examples, model_id, vectors))


class TestJointEmbeddingService:
    """Tests for JointEmbeddingService behaviour."""

    def test_embed_and_store(self) -> None:
        examples = [
            JointExample(
                joint_type="REGIME_WINDOW",
                as_of_date=date(2024, 1, 5),
                entity_scope={"region": "US"},
                numeric_embedding=np.array([1.0, 2.0], dtype=np.float32),
                text_embedding=np.array([0.5, 0.5], dtype=np.float32),
            ),
            JointExample(
                joint_type="REGIME_WINDOW",
                as_of_date=date(2024, 1, 6),
                entity_scope={"region": "US"},
                numeric_embedding=np.array([3.0, 4.0], dtype=np.float32),
                text_embedding=np.array([1.0, 0.0], dtype=np.float32),
            ),
        ]

        model = _DummyJointModel()
        store = _StubStore()
        service = JointEmbeddingService(model=model, store=store, model_id="dummy_joint_v1")

        vectors = service.embed_and_store(examples)

        # Each vector should be concatenation of numeric + text parts.
        assert vectors.shape == (2, 4)
        np.testing.assert_allclose(vectors[0], np.array([1.0, 2.0, 0.5, 0.5], dtype=np.float32))
        np.testing.assert_allclose(vectors[1], np.array([3.0, 4.0, 1.0, 0.0], dtype=np.float32))

        assert len(store.saved) == 1
        saved_examples, saved_model_id, saved_vectors = store.saved[0]
        assert saved_examples == examples
        assert saved_model_id == "dummy_joint_v1"
        np.testing.assert_allclose(saved_vectors, vectors)

    def test_empty_examples_returns_empty_array(self) -> None:
        model = _DummyJointModel()
        store = _StubStore()
        service = JointEmbeddingService(model=model, store=store, model_id="dummy_joint_v1")

        vectors = service.embed_and_store([])
        assert vectors.shape == (0, 0)
        assert store.saved == []


class TestIdentityNumericJointModel:
    """Tests for the IdentityNumericJointModel behaviour."""

    def test_passes_through_numeric_embeddings(self) -> None:
        examples = [
            JointExample(
                joint_type="STAB_FRAGILITY_V0",
                as_of_date=date(2024, 2, 1),
                entity_scope={"entity_type": "INSTRUMENT", "entity_id": "AAA"},
                numeric_embedding=np.array([1.0, 2.0, 3.0], dtype=np.float32),
                text_embedding=None,
            ),
            JointExample(
                joint_type="STAB_FRAGILITY_V0",
                as_of_date=date(2024, 2, 2),
                entity_scope={"entity_type": "INSTRUMENT", "entity_id": "BBB"},
                numeric_embedding=np.array([4.0, 5.0, 6.0], dtype=np.float32),
                text_embedding=None,
            ),
        ]

        model = IdentityNumericJointModel()
        vectors = model.embed_batch(examples)

        assert vectors.shape == (2, 3)
        np.testing.assert_allclose(vectors[0], examples[0].numeric_embedding)
        np.testing.assert_allclose(vectors[1], examples[1].numeric_embedding)

    def test_raises_when_numeric_embedding_missing(self) -> None:
        examples = [
            JointExample(
                joint_type="STAB_FRAGILITY_V0",
                as_of_date=date(2024, 2, 1),
                entity_scope={"entity_type": "INSTRUMENT", "entity_id": "AAA"},
                numeric_embedding=None,
                text_embedding=None,
            ),
        ]

        model = IdentityNumericJointModel()
        with pytest.raises(ValueError):
            _ = model.embed_batch(examples)


class TestSimpleAverageJointModel:
    """Tests for the SimpleAverageJointModel behaviour."""

    def test_weighted_average_combines_numeric_and_text(self) -> None:
        examples = [
            JointExample(
                joint_type="REGIME_CONTEXT_V0",
                as_of_date=date(2024, 1, 5),
                entity_scope={"region": "US"},
                numeric_embedding=np.array([1.0, 3.0], dtype=np.float32),
                text_embedding=np.array([3.0, 1.0], dtype=np.float32),
            ),
            JointExample(
                joint_type="REGIME_CONTEXT_V0",
                as_of_date=date(2024, 1, 6),
                entity_scope={"region": "US"},
                numeric_embedding=np.array([0.0, 2.0], dtype=np.float32),
                text_embedding=np.array([2.0, 0.0], dtype=np.float32),
            ),
        ]

        # numeric_weight : text_weight = 2 : 1
        model = SimpleAverageJointModel(numeric_weight=2.0, text_weight=1.0)
        vectors = model.embed_batch(examples)

        assert vectors.shape == (2, 2)
        # Expected: (2*num + 1*text) / 3
        expected0 = (2.0 * np.array([1.0, 3.0]) + np.array([3.0, 1.0])) / 3.0
        expected1 = (2.0 * np.array([0.0, 2.0]) + np.array([2.0, 0.0])) / 3.0
        np.testing.assert_allclose(vectors[0], expected0.astype(np.float32))
        np.testing.assert_allclose(vectors[1], expected1.astype(np.float32))

    def test_raises_on_missing_branch_or_mismatched_shapes(self) -> None:
        # Missing numeric branch.
        ex_missing_num = JointExample(
            joint_type="REGIME_CONTEXT_V0",
            as_of_date=date(2024, 1, 5),
            entity_scope={"region": "US"},
            numeric_embedding=None,
            text_embedding=np.array([1.0, 2.0], dtype=np.float32),
        )

        model = SimpleAverageJointModel()
        with pytest.raises(ValueError):
            _ = model.embed_batch([ex_missing_num])

        # Mismatched shapes.
        ex_bad_shapes = JointExample(
            joint_type="REGIME_CONTEXT_V0",
            as_of_date=date(2024, 1, 5),
            entity_scope={"region": "US"},
            numeric_embedding=np.array([1.0, 2.0], dtype=np.float32),
            text_embedding=np.array([1.0, 2.0, 3.0], dtype=np.float32),
        )

        with pytest.raises(ValueError):
            _ = model.embed_batch([ex_bad_shapes])
