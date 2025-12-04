"""Prometheus v2 – Numeric window encoder infrastructure.

This module implements the *infrastructure* for numeric time-series
encoders as described in the Prometheus v2 architecture docs. It does
not contain any toy models; instead it focuses on:

- Defining a window specification for entities.
- Building fixed-size numeric windows from historical price data.
- Persisting embeddings into the ``numeric_window_embeddings`` table.
- Providing a thin encoder wrapper that composes a builder, a model, and
  the store.

The actual numeric model must be supplied by the caller via a small
interface; this keeps the core codebase free of stub models while still
providing a solid backbone for real encoders.

Author: Prometheus Team
Created: 2025-11-24
Last Modified: 2025-11-24
Status: Development
Version: v0.1.0
"""

from __future__ import annotations

# ============================================================================
# Imports
# ============================================================================
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol

import numpy as np
from numpy.typing import NDArray
from psycopg2.extras import Json

from prometheus.core.database import DatabaseManager
from prometheus.core.logging import get_logger
from prometheus.core.time import TradingCalendar
from prometheus.data.reader import DataReader

logger = get_logger(__name__)


# ============================================================================
# Window specification
# ============================================================================


@dataclass(frozen=True)
class NumericWindowSpec:
    """Specification of a numeric time window for an entity.

    Attributes:
        entity_type: Logical entity type (e.g. "INSTRUMENT", "MARKET").
        entity_id: Identifier for the entity (e.g. instrument_id).
        window_days: Number of trading days in the lookback window.
        min_required_days: Optional minimum required days. If None, defaults
            to 87% of window_days. If fewer than this many days are available,
            an error is raised.
    """

    entity_type: str
    entity_id: str
    window_days: int
    min_required_days: int | None = None


# ============================================================================
# Window builder
# ============================================================================


class NumericWindowBuilder:
    """Build fixed-size numeric windows from historical prices.

    For the initial implementation, windows are built solely from
    ``prices_daily`` using the following per-day features:

    - Close price
    - Volume
    - Log 1-day return (with 0.0 for the first day)

    This is intentionally simple but fully real logic. Additional
    features (returns from ``returns_daily``, volatility, factors, etc.)
    can be added in later passes without changing the public API.
    """

    def __init__(
        self,
        data_reader: DataReader,
        calendar: TradingCalendar,
    ) -> None:
        # ``calendar`` is accepted for backwards compatibility but is not
        # currently used. We derive windows purely from the observed price
        # rows so that occasional missing sessions do not cause failures.
        self._data_reader = data_reader
        self._calendar = calendar

    def build_window(self, spec: NumericWindowSpec, as_of_date: date) -> NDArray[np.float_]:
        """Build a numeric window for ``spec`` ending at ``as_of_date``.

        The window attempts to contain ``spec.window_days`` observed price
        rows. If at least ``spec.min_required_days`` rows are available,
        uses that and pads to target size if needed. Otherwise raises error.
        """
        if spec.window_days <= 0:
            raise ValueError("window_days must be positive")

        # Determine minimum threshold: default to 87% of target
        min_req = spec.min_required_days
        if min_req is None:
            min_req = max(1, int(spec.window_days * 0.87))

        # Heuristic search range: go back 3x the requested window to
        # account for weekends/holidays and any missing sessions.
        search_start = as_of_date - timedelta(days=spec.window_days * 3)

        df = self._data_reader.read_prices([spec.entity_id], search_start, as_of_date)
        if df.empty or len(df) < min_req:
            raise ValueError(
                f"Insufficient price rows ({len(df)}) for {spec.entity_id} between "
                f"{search_start} and {as_of_date}. Need at least {min_req} rows."
            )

        # Ensure correct ordering and take as many rows as available
        df_sorted = df.sort_values(["trade_date"]).reset_index(drop=True)
        actual_rows = min(len(df_sorted), spec.window_days)
        df_window = df_sorted.tail(actual_rows)

        closes = df_window["close"].astype(float).to_numpy()
        volumes = df_window["volume"].astype(float).to_numpy()

        # If we have fewer than target, pad by repeating the last row
        if closes.shape[0] < spec.window_days:
            logger.warning(
                "NumericWindowEncoder: only %d rows available (target %d) for %s at %s. Padding.",
                closes.shape[0],
                spec.window_days,
                spec.entity_id,
                as_of_date,
            )
            shortfall = spec.window_days - closes.shape[0]
            # Pad with last value
            pad_close = np.full(shortfall, closes[-1], dtype=np.float32)
            pad_volume = np.full(shortfall, volumes[-1], dtype=np.float32)
            closes = np.concatenate([closes, pad_close])
            volumes = np.concatenate([volumes, pad_volume])

        # Compute simple log returns.
        log_returns = np.zeros_like(closes, dtype=float)
        log_returns[1:] = np.log(closes[1:] / closes[:-1])

        features = np.stack([closes, volumes, log_returns], axis=1).astype(np.float32)
        return features


# ============================================================================
# Embedding model & store interfaces
# ============================================================================


class NumericEmbeddingModel(Protocol):
    """Protocol for numeric encoders that map windows to embedding vectors."""

    def encode(
        self, window: NDArray[np.float_]
    ) -> NDArray[np.float_]:  # pragma: no cover - interface
        """Encode a numeric window into a fixed-size embedding vector."""


@dataclass
class NumericEmbeddingStore:
    """Persistence helper for numeric window embeddings.

    Embeddings are stored in the ``numeric_window_embeddings`` table as
    binary vectors together with window specification metadata.
    """

    db_manager: DatabaseManager

    def save_embedding(
        self,
        spec: NumericWindowSpec,
        as_of_date: date,
        model_id: str,
        vector: NDArray[np.float_],
    ) -> None:
        """Persist an embedding for the given spec/date/model.

        The vector is stored as raw bytes (float32) and the window
        specification is captured as JSON for reproducibility.
        """

        sql = """
            INSERT INTO numeric_window_embeddings (
                entity_type,
                entity_id,
                window_spec,
                as_of_date,
                model_id,
                vector,
                vector_ref,
                created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """

        window_spec_payload = {
            "window_days": spec.window_days,
            "entity_type": spec.entity_type,
        }

        # Store as float32 for efficiency.
        vec32 = np.asarray(vector, dtype=np.float32)
        raw = vec32.tobytes()

        with self.db_manager.get_historical_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    sql,
                    (
                        spec.entity_type,
                        spec.entity_id,
                        Json(window_spec_payload),
                        as_of_date,
                        model_id,
                        raw,
                        None,
                    ),
                )
                conn.commit()
            finally:
                cursor.close()


# ============================================================================
# Encoder wrapper
# ============================================================================


@dataclass
class NumericWindowEncoder:
    """High-level façade combining builder, model, and store.

    This encoder is intentionally thin: all modelling is delegated to the
    provided :class:`NumericEmbeddingModel` implementation.
    """

    builder: NumericWindowBuilder
    model: NumericEmbeddingModel
    store: NumericEmbeddingStore
    model_id: str

    def embed_and_store(self, spec: NumericWindowSpec, as_of_date: date) -> NDArray[np.float_]:
        """Build a window, encode it, and persist the embedding.

        Returns the embedding vector produced by the model.
        """

        window = self.builder.build_window(spec, as_of_date)
        embedding = self.model.encode(window)
        self.store.save_embedding(spec, as_of_date, self.model_id, embedding)
        return embedding
