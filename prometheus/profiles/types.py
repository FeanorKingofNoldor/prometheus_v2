"""Prometheus v2 – Profile subsystem types.

This module defines the in-memory representation of issuer profiles used
by the ProfileService and downstream engines.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Mapping, Optional

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class ProfileSnapshot:
    """Profile snapshot for an issuer at a given date.

    Attributes:
        issuer_id: Identifier of the issuer (company, sovereign, sector, index).
        as_of_date: Date for which the profile is valid.
        structured: Normalised structured fields (fundamentals, metadata,
            simple numeric features, etc.). The exact schema is defined by
            the feature builder and may evolve over time, but it must be
            JSON-serialisable.
        embedding: Optional in-memory embedding vector for the profile.
            Embeddings are not currently stored in the DB; they are
            recomputed on demand by the embedder model.
        risk_flags: Scalar risk flags in [0, 1] derived from structured
            features (e.g. volatility-based, drawdown-based).
    """

    issuer_id: str
    as_of_date: date
    structured: Dict[str, Any]
    embedding: Optional[NDArray[np.float_]]
    risk_flags: Dict[str, float]