"""Prometheus v2 – Profile embedding models.

This module defines a small protocol for profile embedders and a basic
implementation that maps structured fields and risk flags into a fixed
size numeric embedding.

The goal is to provide a deterministic, explainable representation of
issuer profiles using only currently available data (issuer metadata and
simple price-based risk flags).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Protocol

import hashlib
import numpy as np
from numpy.typing import NDArray


class ProfileEmbedderModel(Protocol):
    """Protocol for profile embedding models.

    Implementations map structured profile fields and risk flags into a
    fixed-size embedding vector suitable for downstream engines.
    """

    def embed(self, structured: Mapping[str, object], risk_flags: Mapping[str, float]) -> NDArray[np.float_]:  # pragma: no cover - interface
        """Return an embedding vector for the given profile fields."""


def _hash_to_unit_interval(value: str) -> float:
    """Deterministically map a string to [0, 1]."""

    h = hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
    intval = int(h, 16)
    return (intval % 10_000) / 10_000.0


@dataclass
class BasicProfileEmbedder(ProfileEmbedderModel):
    """Simple deterministic profile embedder.

    The embedding is constructed from a small set of features:

    - Risk flags: vol_flag, dd_flag (if present).
    - Categorical hashes for issuer_type, sector, country.

    These are packed into a fixed-length vector and zero-padded up to
    ``embedding_dim``. There is no learned model here; it is an
    engineered, fully deterministic representation.
    """

    embedding_dim: int = 16

    def embed(self, structured: Mapping[str, object], risk_flags: Mapping[str, float]) -> NDArray[np.float_]:  # type: ignore[override]
        # Numeric risk flags
        vol_flag = float(risk_flags.get("vol_flag", 0.0))
        dd_flag = float(risk_flags.get("dd_flag", 0.0))

        # Categorical fields
        issuer_type = str(structured.get("issuer_type", "UNKNOWN"))
        sector = str(structured.get("sector", "UNKNOWN"))
        country = str(structured.get("country", "UNKNOWN"))

        issuer_type_hash = _hash_to_unit_interval(issuer_type)
        sector_hash = _hash_to_unit_interval(sector)
        country_hash = _hash_to_unit_interval(country)

        # Base feature vector; remaining dimensions are zero-padded.
        features = np.array(
            [
                vol_flag,
                dd_flag,
                issuer_type_hash,
                sector_hash,
                country_hash,
            ],
            dtype=np.float32,
        )

        if self.embedding_dim <= features.shape[0]:
            return features[: self.embedding_dim]

        embedding = np.zeros(self.embedding_dim, dtype=np.float32)
        embedding[: features.shape[0]] = features
        return embedding