"""Prometheus v2: Tests for text encoder infrastructure.

These tests cover:
- TextDoc dataclass basics.
- TextEmbeddingService orchestration of model + store with in-memory stubs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np

from prometheus.encoders import (
    TextDoc,
    TextEmbeddingModel,
    TextEmbeddingService,
    TextEmbeddingStore,
)


@dataclass
class _DummyTextModel(TextEmbeddingModel):
    """Deterministic text model for testing.

    It maps each document to a 2D vector [len(text), idx] where idx is
    the position in the input batch.
    """

    def embed_batch(self, docs: List[TextDoc]) -> np.ndarray:  # type: ignore[override]
        vectors = []
        for idx, doc in enumerate(docs):
            vectors.append([float(len(doc.text)), float(idx)])
        return np.asarray(vectors, dtype=np.float32)


class _StubStore(TextEmbeddingStore):
    """In-memory stub for TextEmbeddingStore.

    The base class expects a DatabaseManager; for tests we override
    save_embeddings to avoid DB access.
    """

    def __init__(self) -> None:  # type: ignore[no-untyped-def]
        self.saved = []  # type: ignore[attr-defined]

    def save_embeddings(  # type: ignore[override]
        self,
        docs: List[TextDoc],
        model_id: str,
        vectors: np.ndarray,
    ) -> None:
        self.saved.append((docs, model_id, vectors))


class TestTextEmbeddingService:
    """Tests for TextEmbeddingService behaviour."""

    def test_embed_and_store_calls_model_and_store(self) -> None:
        docs = [
            TextDoc(source_type="NEWS", source_id="1", text="hello"),
            TextDoc(source_type="NEWS", source_id="2", text="world!"),
        ]

        model = _DummyTextModel()
        store = _StubStore()
        service = TextEmbeddingService(model=model, store=store, model_id="dummy_text_v1")

        vectors = service.embed_and_store(docs)

        # Check shapes and values from dummy model.
        assert vectors.shape == (2, 2)
        np.testing.assert_allclose(vectors[0], np.array([5.0, 0.0], dtype=np.float32))
        np.testing.assert_allclose(vectors[1], np.array([6.0, 1.0], dtype=np.float32))

        # Store should have received exactly one batch.
        assert len(store.saved) == 1
        saved_docs, saved_model_id, saved_vectors = store.saved[0]
        assert saved_docs == docs
        assert saved_model_id == "dummy_text_v1"
        np.testing.assert_allclose(saved_vectors, vectors)

    def test_empty_docs_returns_empty_array(self) -> None:
        model = _DummyTextModel()
        store = _StubStore()
        service = TextEmbeddingService(model=model, store=store, model_id="dummy_text_v1")

        vectors = service.embed_and_store([])
        assert vectors.shape == (0, 0)
        assert store.saved == []
