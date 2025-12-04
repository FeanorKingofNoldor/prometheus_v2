"""Prometheus v2 – Joint encoder infrastructure.

This module provides infrastructure for joint text+numeric embeddings in
line with the architecture docs. It defines:

- A JointExample dataclass capturing joint_type, as_of_date, entity_scope
  and optionally precomputed numeric/text embeddings.
- A JointEmbeddingModel protocol (no implementation here).
- A JointEmbeddingStore around the ``joint_embeddings`` table.
- A JointEmbeddingService that ties model + store together.

As with other encoders, the actual model must implement the protocol and
be supplied by callers; this module deliberately contains no toy models.
"""

from __future__ import annotations

# ============================================================================
# Imports
# ============================================================================

from dataclasses import dataclass
from datetime import date
from typing import List, Mapping, Protocol

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
class JointExample:
    """Single example for joint encoding.

    Attributes:
        joint_type: Logical type of joint embedding (e.g. "REGIME_WINDOW",
            "EPISODE", "MACRO_STATE").
        as_of_date: Date associated with this example.
        entity_scope: JSON-serialisable description of what this
            embedding covers (e.g. entity ids, region, instruments).
        numeric_embedding: Optional precomputed numeric embedding vector.
        text_embedding: Optional precomputed text embedding vector.

    The joint model is free to interpret numeric/text embeddings as it
    sees fit; this class exists to carry structured metadata alongside
    the input representations.
    """

    joint_type: str
    as_of_date: date
    entity_scope: Mapping[str, object]
    numeric_embedding: NDArray[np.float_] | None = None
    text_embedding: NDArray[np.float_] | None = None


# ============================================================================
# Model protocol
# ============================================================================


class JointEmbeddingModel(Protocol):
    """Protocol for joint encoders mapping examples to joint embeddings."""

    def embed_batch(self, examples: List[JointExample]) -> NDArray[np.float_]:  # pragma: no cover - interface
        """Embed a batch of joint examples into a shared space."""


# ============================================================================
# Store
# ============================================================================


@dataclass
class JointEmbeddingStore:
    """Persistence helper for joint embeddings.

    Embeddings are stored in the ``joint_embeddings`` table in
    historical_db.
    """

    db_manager: DatabaseManager

    def save_embeddings(
        self,
        examples: List[JointExample],
        model_id: str,
        vectors: NDArray[np.float_],
    ) -> None:
        """Persist embeddings for a batch of joint examples."""

        if vectors.shape[0] != len(examples):
            raise ValueError(
                f"Vector batch size {vectors.shape[0]} does not match number of examples {len(examples)}"
            )

        sql = """
            INSERT INTO joint_embeddings (
                joint_type,
                as_of_date,
                entity_scope,
                model_id,
                vector,
                vector_ref,
                created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """

        vec32 = np.asarray(vectors, dtype=np.float32)

        with self.db_manager.get_historical_connection() as conn:
            cursor = conn.cursor()
            try:
                for example, row in zip(examples, vec32, strict=True):
                    raw = row.tobytes()
                    cursor.execute(
                        sql,
                        (
                            example.joint_type,
                            example.as_of_date,
                            Json(dict(example.entity_scope)),
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
class JointEmbeddingService:
    """High-level façade combining joint model and store."""

    model: JointEmbeddingModel
    store: JointEmbeddingStore
    model_id: str

    def embed_and_store(self, examples: List[JointExample]) -> NDArray[np.float_]:
        """Embed examples and persist their joint embeddings."""

        if not examples:
            return np.zeros((0, 0), dtype=np.float32)

        vectors = self.model.embed_batch(examples)
        self.store.save_embeddings(examples, self.model_id, vectors)
        return vectors
