"""Prometheus v2 – Profile Service.

This module implements a minimal ProfileService that builds and serves
issuer profile snapshots and embeddings backed by the `profiles` table.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

import numpy as np
from numpy.typing import NDArray

from prometheus.core.logging import get_logger
from prometheus.profiles.embedder import ProfileEmbedderModel
from prometheus.profiles.features import ProfileFeatureBuilder
from prometheus.profiles.storage import ProfileStorage
from prometheus.profiles.types import ProfileSnapshot


logger = get_logger(__name__)


@dataclass
class ProfileService:
    """Builds and serves issuer profile snapshots and embeddings."""

    storage: ProfileStorage
    feature_builder: ProfileFeatureBuilder
    embedder: ProfileEmbedderModel

    def get_snapshot(self, issuer_id: str, as_of_date: date) -> ProfileSnapshot:
        """Return or construct the profile snapshot for an issuer/date."""

        existing = self.storage.load_snapshot(issuer_id, as_of_date)
        if existing is not None:
            return existing

        structured = self.feature_builder.build_structured(issuer_id, as_of_date)
        risk_flags = self.feature_builder.build_risk_flags(structured)

        snapshot = ProfileSnapshot(
            issuer_id=issuer_id,
            as_of_date=as_of_date,
            structured=structured,
            embedding=None,
            risk_flags=risk_flags,
        )

        self.storage.save_snapshot(snapshot)

        logger.info(
            "ProfileService.get_snapshot: built new snapshot issuer_id=%s as_of=%s",
            issuer_id,
            as_of_date,
        )

        return snapshot

    def embed_profile(self, issuer_id: str, as_of_date: date) -> NDArray[np.float_]:
        """Return the profile embedding for an issuer/date.

        Embeddings are computed on demand from structured fields and risk
        flags using the configured embedder. They are not yet persisted
        separately; callers should treat this as a pure function.
        """

        snapshot = self.get_snapshot(issuer_id, as_of_date)
        embedding = self.embedder.embed(snapshot.structured, snapshot.risk_flags)
        return embedding