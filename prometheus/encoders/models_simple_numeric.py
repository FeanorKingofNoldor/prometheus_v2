"""Simple numeric embedding models for Prometheus v2.

These models provide concrete :class:`NumericEmbeddingModel`
implementations on top of the infrastructure in
:mod:`prometheus.encoders.numeric`.

For Iteration 1 we keep the behaviour deliberately simple and fully
transparent: the encoder flattens the numeric window into a 1D vector.
This is sufficient to wire the Regime/Profiles engines end‑to‑end while
keeping the model component easily swappable for a learned encoder later
on.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from prometheus.encoders.numeric import NumericEmbeddingModel


@dataclass
class FlattenNumericEmbeddingModel(NumericEmbeddingModel):
    """Trivial numeric embedding model that flattens the window.

    Given a window of shape ``(window_days, num_features)``, this model
    returns a 1D vector of length ``window_days * num_features``. The
    output is ``float32`` for efficient storage.

    This is intentionally simple but fully deterministic and suitable as
    a first real encoder; it can be replaced or supplemented by a
    learned model without changing callers.
    """

    def encode(self, window: NDArray[np.float_]) -> NDArray[np.float_]:  # type: ignore[override]
        if window.ndim != 2:
            raise ValueError(f"Expected 2D window, got shape {window.shape}")
        flat = np.asarray(window, dtype=np.float32).ravel()
        return flat


@dataclass
class PadToDimNumericEmbeddingModel(NumericEmbeddingModel):
    """Numeric model that flattens and pads/truncates to a fixed dimension.

    This model is a small adaptation of :class:`FlattenNumericEmbeddingModel`
    that ensures a consistent embedding dimension (e.g. 384) by either
    truncating or zero-padding the flattened window.

    It is suitable as a v0 implementation for encoders such as
    ``num-regime-core-v1`` where we care about a fixed dimensionality but
    do not yet have a learned projection in place.
    """

    target_dim: int = 384

    def encode(self, window: NDArray[np.float_]) -> NDArray[np.float_]:  # type: ignore[override]
        # Re-use the flattening logic for consistency.
        flat = FlattenNumericEmbeddingModel().encode(window)
        d = self.target_dim
        n = flat.shape[0]

        if n == d:
            return flat
        if n > d:
            return flat[:d]

        out = np.zeros(d, dtype=np.float32)
        out[:n] = flat
        return out
