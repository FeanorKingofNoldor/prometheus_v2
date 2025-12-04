"""Prometheus v2 – Numeric embedding-based RegimeModel.

This module provides a concrete implementation of :class:`RegimeModel`
that operates purely on numeric embeddings produced by the
:mod:`prometheus.encoders.numeric` infrastructure.

Key responsibilities:
- Map (as_of_date, region) to a :class:`RegimeState` by:
  - selecting a representative instrument_id for the region,
  - building a numeric window via :class:`NumericWindowSpec`,
  - obtaining an embedding via a numeric encoder,
  - assigning the embedding to the nearest regime prototype,
  - computing a confidence score from distances.

All classification logic here is real and deterministic. There are no
rule-based shortcuts or placeholder stubs; future iterations can refine
how embeddings and prototypes are obtained (e.g. via a model registry or
offline clustering artefacts) without changing this core algorithm.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Mapping, Protocol, Sequence

import numpy as np
from numpy.typing import NDArray

from prometheus.core.logging import get_logger
from prometheus.encoders.numeric import NumericWindowSpec
from prometheus.regime.engine import RegimeModel
from prometheus.regime.types import RegimeLabel, RegimeState

logger = get_logger(__name__)


class NumericWindowEncoderLike(Protocol):
    """Minimal protocol for numeric window encoders.

    This matches the public behaviour of
    :class:`prometheus.encoders.numeric.NumericWindowEncoder` while
    allowing tests to provide lightweight stubs without touching the
    database.
    """

    def embed_and_store(  # pragma: no cover - interface
        self,
        spec: NumericWindowSpec,
        as_of_date: date,
    ) -> NDArray[np.float_]:
        """Encode and persist a numeric window, returning the embedding."""


@dataclass(frozen=True)
class RegimePrototype:
    """Prototype (cluster centre) for a regime in embedding space.

    Attributes:
        label: Regime label associated with this prototype.
        center: Prototype centre vector in the same space as numeric
            embeddings produced by the encoder.
    """

    label: RegimeLabel
    center: NDArray[np.float_]


@dataclass
class NumericRegimeModel(RegimeModel):
    """Numeric-encoder-based implementation of :class:`RegimeModel`.

    This model:
    - Uses a numeric encoder to obtain an embedding for a representative
      instrument for each region over a fixed lookback window.
    - Assigns the embedding to the nearest prototype in embedding space.
    - Derives a confidence score via a softmax over negative distances.

    It makes no assumptions about how prototypes were obtained; they may
    come from offline clustering, expert calibration, or any other
    process, as long as they live in the same embedding space.
    """

    encoder: NumericWindowEncoderLike
    region_instruments: Mapping[str, str]
    window_days: int
    prototypes: Sequence[RegimePrototype]
    temperature: float = 1.0

    def __post_init__(self) -> None:
        if self.window_days <= 0:
            raise ValueError("window_days must be positive")
        if self.temperature <= 0.0:
            raise ValueError("temperature must be positive")
        if not self.prototypes:
            raise ValueError("NumericRegimeModel requires at least one RegimePrototype")

        # Validate prototype shapes.
        first_shape = self.prototypes[0].center.shape
        for proto in self.prototypes[1:]:
            if proto.center.shape != first_shape:
                raise ValueError(
                    "All RegimePrototype centers must have the same shape; "
                    f"got {first_shape} and {proto.center.shape}"
                )

    def _resolve_instrument(self, region: str) -> str:
        try:
            return self.region_instruments[region]
        except KeyError as exc:  # pragma: no cover - simple error path
            raise ValueError(
                f"No instrument configured for region {region!r} in NumericRegimeModel"
            ) from exc

    def _classify_embedding(self, embedding: NDArray[np.float_]) -> tuple[RegimeLabel, float, dict[str, float]]:
        """Assign a regime label given an embedding.

        Returns a tuple of (label, confidence, distances_by_label).
        """

        # Ensure embedding shape matches prototypes.
        expected_shape = self.prototypes[0].center.shape
        if embedding.shape != expected_shape:
            raise ValueError(
                "Embedding shape does not match prototype centers: "
                f"{embedding.shape} != {expected_shape}"
            )

        distances = np.array(
            [float(np.linalg.norm(embedding - proto.center)) for proto in self.prototypes],
            dtype=float,
        )

        # Softmax over negative distances to obtain a pseudo-probability
        # distribution over prototypes.
        logits = -distances / self.temperature
        logits = logits - logits.max()  # numerical stability
        exp_logits = np.exp(logits)
        probs = exp_logits / exp_logits.sum()

        best_index = int(distances.argmin())
        best_proto = self.prototypes[best_index]
        confidence = float(probs[best_index])

        distances_by_label = {
            proto.label.value: float(d) for proto, d in zip(self.prototypes, distances)
        }

        return best_proto.label, confidence, distances_by_label

    def classify(self, as_of_date: date, region: str) -> RegimeState:  # type: ignore[override]
        """Infer the regime state for ``region`` on ``as_of_date``.

        This method:
        - selects the configured representative instrument for the region,
        - builds and encodes a numeric window ending at ``as_of_date``,
        - assigns the embedding to the nearest regime prototype,
        - returns a :class:`RegimeState` with embedding and diagnostics.
        """

        instrument_id = self._resolve_instrument(region)
        spec = NumericWindowSpec(
            entity_type="INSTRUMENT",
            entity_id=instrument_id,
            window_days=self.window_days,
        )

        embedding = self.encoder.embed_and_store(spec, as_of_date)

        label, confidence, distances_by_label = self._classify_embedding(embedding)

        metadata = {
            "window_days": self.window_days,
            "temperature": self.temperature,
            "instrument_id": instrument_id,
            "distances": distances_by_label,
        }

        logger.info(
            "NumericRegimeModel.classify: date=%s region=%s instrument=%s label=%s confidence=%.3f",
            as_of_date,
            region,
            instrument_id,
            label.value,
            confidence,
        )

        return RegimeState(
            as_of_date=as_of_date,
            region=region,
            regime_label=label,
            confidence=confidence,
            regime_embedding=embedding,
            metadata=metadata,
        )
