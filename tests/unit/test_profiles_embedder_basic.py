"""Prometheus v2: Tests for BasicProfileEmbedder.

These tests verify that the basic profile embedder is deterministic and
sensitive to risk flags and categorical fields.
"""

from __future__ import annotations

from prometheus.profiles.embedder import BasicProfileEmbedder


class TestBasicProfileEmbedder:
    def test_deterministic_for_same_input(self) -> None:
        embedder = BasicProfileEmbedder(embedding_dim=8)

        structured = {"issuer_type": "COMPANY", "sector": "TECH", "country": "US"}
        risk_flags = {"vol_flag": 0.3, "dd_flag": 0.5}

        v1 = embedder.embed(structured, risk_flags)
        v2 = embedder.embed(structured, risk_flags)

        assert v1.shape[0] == 8
        assert (v1 == v2).all()

    def test_changes_in_flags_and_categories_affect_embedding(self) -> None:
        embedder = BasicProfileEmbedder(embedding_dim=8)

        structured_a = {"issuer_type": "COMPANY", "sector": "TECH", "country": "US"}
        structured_b = {"issuer_type": "COMPANY", "sector": "UTILITIES", "country": "US"}

        risk_flags_low = {"vol_flag": 0.1, "dd_flag": 0.2}
        risk_flags_high = {"vol_flag": 0.8, "dd_flag": 0.9}

        va = embedder.embed(structured_a, risk_flags_low)
        vb = embedder.embed(structured_a, risk_flags_high)
        vc = embedder.embed(structured_b, risk_flags_low)

        # Risk flags affect the first two coordinates.
        assert va[0] != vb[0] or va[1] != vb[1]

        # Sector change affects hashed coordinates.
        assert (va[2:] != vc[2:]).any()
