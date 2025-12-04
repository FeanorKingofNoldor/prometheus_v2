"""Prometheus v2 – Text encoder infrastructure.

This module implements the *infrastructure* for text encoders as
specified in the architecture docs. It focuses on:

- A small document wrapper with source metadata.
- A model protocol for text encoders.
- A persistence helper around the ``text_embeddings`` table.
- A service that ties model + store together.

No stub models are provided here; real models must implement the
:class:`TextEmbeddingModel` protocol and be passed in by callers.
"""

from __future__ import annotations

# ============================================================================
# Imports
# ============================================================================

from dataclasses import dataclass
from typing import List, Protocol

import numpy as np
from numpy.typing import NDArray
from psycopg2.extras import Json

from prometheus.core.database import DatabaseManager
from prometheus.core.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# Data structures
# ============================================================================


@dataclass(frozen=True)
class TextDoc:
    """Text document with minimal source metadata.

    Attributes:
        source_type: Logical source type (e.g. "NEWS", "FILING", "CALL").
        source_id: Identifier in the corresponding table (stringified).
        text: Raw text content to be embedded.
    """

    source_type: str
    source_id: str
    text: str


# ============================================================================
# Model protocol
# ============================================================================


class TextEmbeddingModel(Protocol):
    """Protocol for text encoders that map documents to embedding vectors."""

    def embed_batch(self, docs: List[TextDoc]) -> NDArray[np.float_]:  # pragma: no cover - interface
        """Embed a batch of text documents.

        Implementations should return a 2D array of shape
        (batch_size, embedding_dim).
        """


# ============================================================================
# Store
# ============================================================================


@dataclass
class TextEmbeddingStore:
    """Persistence helper for text embeddings.

    Embeddings are stored in the ``text_embeddings`` table in
    historical_db.
    """

    db_manager: DatabaseManager

    def save_embeddings(
        self,
        docs: List[TextDoc],
        model_id: str,
        vectors: NDArray[np.float_],
    ) -> None:
        """Persist embeddings for a batch of documents.

        Args:
            docs: Documents corresponding to rows in ``vectors``.
            model_id: Identifier of the encoder model used.
            vectors: 2D array of shape (len(docs), embedding_dim).
        """

        if vectors.shape[0] != len(docs):
            raise ValueError(
                f"Vector batch size {vectors.shape[0]} does not match number of docs {len(docs)}"
            )

        sql = """
            INSERT INTO text_embeddings (
                source_type,
                source_id,
                model_id,
                vector,
                vector_ref,
                created_at
            ) VALUES (%s, %s, %s, %s, %s, NOW())
            ON CONFLICT (source_type, source_id, model_id) DO UPDATE
            SET vector = EXCLUDED.vector,
                vector_ref = EXCLUDED.vector_ref
        """

        # Ensure float32 storage.
        vec32 = np.asarray(vectors, dtype=np.float32)

        with self.db_manager.get_historical_connection() as conn:
            cursor = conn.cursor()
            try:
                for doc, row in zip(docs, vec32, strict=True):
                    raw = row.tobytes()
                    cursor.execute(
                        sql,
                        (
                            doc.source_type,
                            doc.source_id,
                            model_id,
                            raw,
                            None,
                        ),
                    )
                conn.commit()
            finally:
                cursor.close()


# ============================================================================
# Service
# ============================================================================


@dataclass
class TextEmbeddingService:
    """High-level façade combining a text model and persistence store."""

    model: TextEmbeddingModel
    store: TextEmbeddingStore
    model_id: str

    def embed_and_store(self, docs: List[TextDoc]) -> NDArray[np.float_]:
        """Embed documents and persist their embeddings.

        Returns the embeddings produced by the model.
        """

        if not docs:
            return np.zeros((0, 0), dtype=np.float32)

        vectors = self.model.embed_batch(docs)
        self.store.save_embeddings(docs, self.model_id, vectors)
        return vectors
