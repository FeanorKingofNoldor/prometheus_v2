"""Prometheus v2: Tests for ProfileService.

These tests verify that ProfileService orchestrates storage, feature
building, and embedding correctly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict

import numpy as np

from prometheus.profiles import (
    ProfileSnapshot,
    ProfileStorage,
    ProfileFeatureBuilder,
    ProfileEmbedderModel,
    ProfileService,
)


class _StubStorage(ProfileStorage):
    snapshots: Dict[tuple[str, date], ProfileSnapshot]

    def __init__(self) -> None:  # type: ignore[no-untyped-def]
        self.snapshots = {}

    def save_snapshot(self, snapshot: ProfileSnapshot) -> None:  # type: ignore[override]
        self.snapshots[(snapshot.issuer_id, snapshot.as_of_date)] = snapshot

    def load_snapshot(self, issuer_id: str, as_of_date: date):  # type: ignore[override]
        return self.snapshots.get((issuer_id, as_of_date))

    def load_latest_snapshot(self, issuer_id: str):  # type: ignore[override]
        latest_key = None
        for (iss, d) in self.snapshots.keys():
            if iss == issuer_id and (latest_key is None or d > latest_key[1]):
                latest_key = (iss, d)
        return self.snapshots.get(latest_key) if latest_key else None


class _StubFeatureBuilder(ProfileFeatureBuilder):
    structured_payload: Dict[str, object]
    flags_payload: Dict[str, float]

    def __init__(self):  # type: ignore[no-untyped-def]
        self.structured_payload = {"issuer_type": "COMPANY", "sector": "TECH", "country": "US"}
        self.flags_payload = {"vol_flag": 0.2, "dd_flag": 0.3}

    def build_structured(self, issuer_id, as_of_date):  # type: ignore[override, no-untyped-def]
        data = dict(self.structured_payload)
        data["issuer_id"] = issuer_id
        return data

    def build_risk_flags(self, structured):  # type: ignore[override, no-untyped-def]
        return dict(self.flags_payload)


@dataclass
class _StubEmbedder(ProfileEmbedderModel):
    def embed(self, structured, risk_flags):  # type: ignore[override, no-untyped-def]
        # Very simple embedder: return 2D vector [vol_flag, dd_flag].
        return np.array([risk_flags.get("vol_flag", 0.0), risk_flags.get("dd_flag", 0.0)], dtype=np.float32)


class TestProfileService:
    def test_get_snapshot_builds_and_saves_when_missing(self) -> None:
        storage = _StubStorage()
        builder = _StubFeatureBuilder()
        embedder = _StubEmbedder()
        service = ProfileService(storage=storage, feature_builder=builder, embedder=embedder)

        issuer_id = "ISS_TEST"
        as_of = date(2024, 3, 4)

        snapshot = service.get_snapshot(issuer_id, as_of)

        assert snapshot.issuer_id == issuer_id
        assert snapshot.as_of_date == as_of
        assert snapshot.structured["issuer_type"] == "COMPANY"
        assert snapshot.risk_flags["vol_flag"] == builder.flags_payload["vol_flag"]
        assert (issuer_id, as_of) in storage.snapshots

        # Second call should load from storage, not rebuild.
        snapshot2 = service.get_snapshot(issuer_id, as_of)
        assert snapshot2 is snapshot

    def test_embed_profile_uses_embedder(self) -> None:
        storage = _StubStorage()
        builder = _StubFeatureBuilder()
        embedder = _StubEmbedder()
        service = ProfileService(storage=storage, feature_builder=builder, embedder=embedder)

        issuer_id = "ISS_TEST"
        as_of = date(2024, 3, 4)

        embedding = service.embed_profile(issuer_id, as_of)

        assert embedding.shape == (2,)
        assert embedding[0] == builder.flags_payload["vol_flag"]
        assert embedding[1] == builder.flags_payload["dd_flag"]
