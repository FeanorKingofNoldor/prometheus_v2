"""Simple joint embedding models for v0 shared spaces.

This module provides small, fully deterministic joint encoders that
operate on precomputed numeric and text embeddings and combine them into
joint representations in R^d.

These are deliberately simple (e.g. weighted average) and intended for
v0 workflows and tests. Future iterations can introduce trained
projection heads while keeping the same JointEmbeddingModel API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np
from numpy.typing import NDArray

from prometheus.encoders.joint import JointEmbeddingModel, JointExample


@dataclass
class IdentityNumericJointModel(JointEmbeddingModel):
    """Joint model that passes through numeric embeddings unchanged.

    This is useful for joint spaces that are purely numeric (e.g.
    stability/fragility) where the combination of multiple numeric
    branches happens upstream and the joint model simply standardises the
    interface to ``JointEmbeddingService``.
    """

    def embed_batch(self, examples: List[JointExample]) -> NDArray[np.float_]:  # type: ignore[override]
        if not examples:
            return np.zeros((0, 0), dtype=np.float32)

        vectors: list[NDArray[np.float_]] = []
        for ex in examples:
            if ex.numeric_embedding is None:
                raise ValueError(
                    "IdentityNumericJointModel requires numeric_embedding for each example"
                )
            z_num = np.asarray(ex.numeric_embedding, dtype=np.float32)
            vectors.append(z_num)

        return np.stack(vectors, axis=0).astype(np.float32)


@dataclass
class SimpleAverageJointModel(JointEmbeddingModel):
    """Joint model that averages numeric and text embeddings.

    For each example, this model expects both ``numeric_embedding`` and
    ``text_embedding`` to be present and of the same shape. It then
    computes a weighted average:

        z_joint = (w_num * z_num + w_text * z_text) / (w_num + w_text)

    where ``w_num`` and ``w_text`` are configurable weights. This keeps
    the output dimension identical to the branch dimensions (e.g. 384)
    and provides a simple but real v0 joint embedding.
    """

    numeric_weight: float = 0.5
    text_weight: float = 0.5

    def embed_batch(self, examples: List[JointExample]) -> NDArray[np.float_]:  # type: ignore[override]
        if not examples:
            return np.zeros((0, 0), dtype=np.float32)

        w_num = self.numeric_weight
        w_text = self.text_weight
        weight_sum = w_num + w_text
        if weight_sum <= 0.0:
            raise ValueError("numeric_weight + text_weight must be positive")

        vectors: list[NDArray[np.float_]] = []
        for ex in examples:
            if ex.numeric_embedding is None or ex.text_embedding is None:
                raise ValueError(
                    "SimpleAverageJointModel requires both numeric and text embeddings for each example"
                )

            z_num = np.asarray(ex.numeric_embedding, dtype=np.float32)
            z_text = np.asarray(ex.text_embedding, dtype=np.float32)

            if z_num.shape != z_text.shape:
                raise ValueError(
                    "numeric_embedding and text_embedding must have the same shape; "
                    f"got {z_num.shape} and {z_text.shape}"
                )

            z_joint = (w_num * z_num + w_text * z_text) / weight_sum
            vectors.append(z_joint)

        return np.stack(vectors, axis=0).astype(np.float32)
