"""Prometheus v2 – Regime storage helpers.

This module provides a small abstraction around writing and reading
regime assignments and transitions from the database. It is intentionally
minimal for Iteration 4 and focuses on:

- Inserting new rows into the ``regimes`` table.
- Fetching the latest regime for a region.
- Recording regime transitions into ``regime_transitions`` when labels
  change over time.

Database tables accessed (runtime_db via DatabaseManager):
- regimes
- regime_transitions

Thread safety: Not thread-safe; intended for single-threaded engine
runs.

Author: Prometheus Team
Created: 2025-11-24
Last Modified: 2025-11-24
Status: Development
Version: v0.4.0
"""

from __future__ import annotations

# ============================================================================
# Imports
# ============================================================================

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from prometheus.core.database import DatabaseManager
from prometheus.core.ids import generate_uuid
from prometheus.core.logging import get_logger
from prometheus.core.types import MetadataDict
from prometheus.regime.types import RegimeLabel, RegimeState
from psycopg2.extras import Json

import numpy as np

# ============================================================================
# Module setup
# ============================================================================

logger = get_logger(__name__)


@dataclass
class RegimeStorage:
    """Persistence helper for regime states and transitions.
    
    This class provides a clean abstraction over database operations for
    the Regime Engine, handling all reads and writes to the regimes and
    regime_transitions tables in the runtime database.
    
    Attributes:
        db_manager: DatabaseManager instance for connection management
    
    Example:
        >>> storage = RegimeStorage(db_manager)
        >>> state = RegimeState(...)
        >>> storage.save_regime(state)
    """

    db_manager: DatabaseManager

    # ========================================================================
    # Public API: Regime State Persistence
    # ========================================================================

    def save_regime(self, state: RegimeState) -> None:
        """Insert a regime record into the ``regimes`` table.

        For Iteration 4 we always insert a new row; deduplication and
        model-id based uniqueness can be added in a later iteration if
        needed. The regime embedding (if present) is stored as float32
        bytes for potential downstream retrieval.
        
        Args:
            state: RegimeState object containing all regime information
                including label, confidence, and optional embedding
        
        Raises:
            psycopg2.Error: If database insert fails due to connection
                issues, constraint violations, or other database errors
        
        Example:
            >>> state = RegimeState(
            ...     as_of_date=date(2024, 1, 15),
            ...     region="US",
            ...     regime_label=RegimeLabel.CARRY,
            ...     confidence=0.87,
            ... )
            >>> storage.save_regime(state)
        """

        sql = """
            INSERT INTO regimes (
                regime_record_id,
                as_of_date,
                region,
                regime_label,
                regime_embedding,
                embedding_ref,
                confidence,
                metadata,
                created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """

        regime_id = generate_uuid()

        # If a regime embedding is present, store it as float32 bytes for
        # potential downstream use. This mirrors the storage pattern used
        # for numeric_window_embeddings.
        if state.regime_embedding is not None:
            vec32 = np.asarray(state.regime_embedding, dtype=np.float32)
            embedding_bytes = vec32.tobytes()
        else:
            embedding_bytes = None

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    sql,
                    (
                        regime_id,
                        state.as_of_date,
                        state.region,
                        state.regime_label.value,
                        embedding_bytes,
                        None,
                        state.confidence,
                        Json(state.metadata or {}),
                    ),
                )
                conn.commit()
            finally:
                cursor.close()

    def get_latest_regime(self, region: str) -> Optional[RegimeState]:
        """Return the most recent regime for ``region``, if any.

        Queries the regimes table for the most recent regime classification
        based on as_of_date ordering. The regime embedding is not included
        in the returned state to minimize data transfer.
        
        Args:
            region: Region code (e.g., "US", "EU", "GLOBAL")
        
        Returns:
            RegimeState object for the most recent date, or None if no
            regimes have been recorded for the specified region
        
        Raises:
            psycopg2.Error: If database query fails
        
        Example:
            >>> latest = storage.get_latest_regime("US")
            >>> if latest:
            ...     print(latest.regime_label, latest.confidence)
        """

        sql = """
            SELECT as_of_date, region, regime_label, confidence, metadata
            FROM regimes
            WHERE region = %s
            ORDER BY as_of_date DESC
            LIMIT 1
        """

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (region,))
                row = cursor.fetchone()
            finally:
                cursor.close()

        if row is None:
            return None

        as_of_date, region_value, regime_label, confidence, metadata = row
        label_enum = RegimeLabel(regime_label)
        metadata_dict: MetadataDict | None = metadata

        return RegimeState(
            as_of_date=as_of_date,
            region=region_value,
            regime_label=label_enum,
            confidence=confidence,
            regime_embedding=None,
            metadata=metadata_dict,
        )

    # ========================================================================
    # Public API: Regime History
    # ========================================================================

    def get_history(self, region: str, start_date: date, end_date: date) -> list[RegimeState]:
        """Return regime history for ``region`` between two dates (inclusive).
        
        Retrieves all regime classifications for the specified region within
        the date range, ordered chronologically. Useful for backtesting,
        analysis, and visualization of regime changes over time.
        
        Args:
            region: Region code (e.g., "US", "EU", "GLOBAL")
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
        
        Returns:
            List of RegimeState objects ordered by as_of_date ascending.
            Returns empty list if no regimes exist in the specified range.
        
        Raises:
            psycopg2.Error: If database query fails
        
        Example:
            >>> history = storage.get_history(
            ...     region="US",
            ...     start_date=date(2024, 1, 1),
            ...     end_date=date(2024, 3, 31),
            ... )
            >>> print(f"Found {len(history)} regime records")
        """

        sql = """
            SELECT as_of_date, region, regime_label, confidence, metadata
            FROM regimes
            WHERE region = %s
              AND as_of_date BETWEEN %s AND %s
            ORDER BY as_of_date ASC
        """

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (region, start_date, end_date))
                rows = cursor.fetchall()
            finally:
                cursor.close()

        history: list[RegimeState] = []
        for as_of_date, region_value, regime_label, confidence, metadata in rows:
            label_enum = RegimeLabel(regime_label)
            metadata_dict: MetadataDict | None = metadata
            history.append(
                RegimeState(
                    as_of_date=as_of_date,
                    region=region_value,
                    regime_label=label_enum,
                    confidence=confidence,
                    regime_embedding=None,
                    metadata=metadata_dict,
                )
            )

        return history

    # ========================================================================
    # Public API: Regime Transitions
    # ========================================================================

    def record_transition(self, previous: RegimeState, current: RegimeState) -> None:
        """Record a regime transition into ``regime_transitions``.

        A transition is recorded whenever consecutive regime labels for a
        given region differ. This enables transition probability analysis
        and regime change event detection. The transition metadata includes
        confidence scores from both states.
        
        Args:
            previous: RegimeState before the transition
            current: RegimeState after the transition (must be different label)
        
        Raises:
            psycopg2.Error: If database insert fails
        
        Example:
            >>> prev = RegimeState(..., regime_label=RegimeLabel.CARRY)
            >>> curr = RegimeState(..., regime_label=RegimeLabel.CRISIS)
            >>> storage.record_transition(prev, curr)
        """

        sql = """
            INSERT INTO regime_transitions (
                transition_id,
                region,
                from_regime_label,
                to_regime_label,
                as_of_date,
                metadata,
                created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """

        transition_id = generate_uuid()
        metadata = Json(
            {
                "previous_confidence": previous.confidence,
                "current_confidence": current.confidence,
            }
        )

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    sql,
                    (
                        transition_id,
                        current.region,
                        previous.regime_label.value,
                        current.regime_label.value,
                        current.as_of_date,
                        metadata,
                    ),
                )
                conn.commit()
            finally:
                cursor.close()

    def get_transition_matrix(self, region: str) -> dict[str, dict[str, float]]:
        """Return empirical transition probabilities for ``region``.

        Calculates transition probabilities from historical regime change
        counts stored in the regime_transitions table. The matrix shows
        P(to_label | from_label) for all observed transitions.
        
        The calculation is::

            P(to | from) = count(from -> to) / sum_to count(from -> to)
        
        Args:
            region: Region code (e.g., "US", "EU", "GLOBAL")
        
        Returns:
            Nested dict mapping from_label -> to_label -> probability.
            Returns empty dict if no transitions exist for the region.
        
        Raises:
            psycopg2.Error: If database query fails
        
        Example:
            >>> matrix = storage.get_transition_matrix("US")
            >>> if "CARRY" in matrix and "CRISIS" in matrix["CARRY"]:
            ...     prob = matrix["CARRY"]["CRISIS"]
            ...     print(f"P(CRISIS | CARRY) = {prob:.2%}")
        """

        sql = """
            SELECT from_regime_label, to_regime_label, COUNT(*) AS cnt
            FROM regime_transitions
            WHERE region = %s
            GROUP BY from_regime_label, to_regime_label
        """

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (region,))
                rows = cursor.fetchall()
            finally:
                cursor.close()

        if not rows:
            return {}

        counts: dict[str, dict[str, int]] = {}
        for from_label, to_label, cnt in rows:
            inner = counts.setdefault(from_label, {})
            inner[to_label] = inner.get(to_label, 0) + int(cnt)

        matrix: dict[str, dict[str, float]] = {}
        for from_label, to_counts in counts.items():
            total = float(sum(to_counts.values()))
            if total <= 0.0:
                # Should not happen with COUNT(*), but guard against it.
                continue
            matrix[from_label] = {
                to_label: count / total for to_label, count in to_counts.items()
            }

        return matrix
