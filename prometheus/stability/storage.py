"""Prometheus v2 – Stability storage helpers.

This module provides a thin abstraction around reading and writing
stability vectors and soft-target classifications in the runtime
database. It mirrors the approach used by :mod:`prometheus.regime.storage`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from psycopg2.extras import Json

from prometheus.core.database import DatabaseManager
from prometheus.core.ids import generate_uuid
from prometheus.core.logging import get_logger
from prometheus.core.types import MetadataDict
from prometheus.stability.types import SoftTargetClass, StabilityVector, SoftTargetState


logger = get_logger(__name__)


@dataclass
class StabilityStorage:
    """Persistence helper for stability vectors and soft-target classes.
    
    This class provides database operations for the Stability Engine,
    handling persistence of stability vectors and soft-target
    classifications.
    
    Attributes:
        db_manager: DatabaseManager instance for connection management
    
    Example:
        >>> storage = StabilityStorage(db_manager)
        >>> vector = StabilityVector(...)
        >>> storage.save_stability_vector(vector)
    """

    db_manager: DatabaseManager

    # ========================================================================
    # Public API: Stability Vectors
    # ========================================================================

    def save_stability_vector(self, vector: StabilityVector) -> None:
        """Insert a stability vector into ``stability_vectors`` table.
        
        Stores the multi-dimensional stability assessment for an entity,
        including component scores and overall stability metric.
        
        Args:
            vector: StabilityVector containing entity info and scores
        
        Raises:
            psycopg2.Error: If database insert fails
        
        Example:
            >>> vector = StabilityVector(
            ...     entity_type="issuer",
            ...     entity_id="AAPL",
            ...     as_of_date=date(2024, 1, 15),
            ...     components={"volatility": 0.2, "correlation": 0.5},
            ...     overall_score=0.75,
            ... )
            >>> storage.save_stability_vector(vector)
        """

        sql = """
            INSERT INTO stability_vectors (
                stability_id,
                entity_type,
                entity_id,
                as_of_date,
                vector_components,
                overall_score,
                metadata,
                created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """

        stability_id = generate_uuid()
        components_payload = Json(vector.components)
        metadata_payload = Json(vector.metadata or {})

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    sql,
                    (
                        stability_id,
                        vector.entity_type,
                        vector.entity_id,
                        vector.as_of_date,
                        components_payload,
                        vector.overall_score,
                        metadata_payload,
                    ),
                )
                conn.commit()
            finally:
                cursor.close()

    # ========================================================================
    # Public API: Soft-Target Classifications
    # ========================================================================

    def save_soft_target(self, state: SoftTargetState) -> None:
        """Insert a soft-target classification into ``soft_target_classes``.
        
        Stores the soft-target classification including class label,
        score, and component flags (weak_profile, instability, etc.).
        
        Args:
            state: SoftTargetState with classification results
        
        Raises:
            psycopg2.Error: If database insert fails
        
        Example:
            >>> state = SoftTargetState(
            ...     entity_type="issuer",
            ...     entity_id="AAPL",
            ...     as_of_date=date(2024, 1, 15),
            ...     soft_target_class=SoftTargetClass.GOOD,
            ...     soft_target_score=0.85,
            ...     weak_profile=False,
            ...     instability=False,
            ...     high_fragility=False,
            ...     complacent_pricing=False,
            ... )
            >>> storage.save_soft_target(state)
        """

        sql = """
            INSERT INTO soft_target_classes (
                soft_target_id,
                entity_type,
                entity_id,
                as_of_date,
                soft_target_class,
                soft_target_score,
                weak_profile,
                instability,
                high_fragility,
                complacent_pricing,
                metadata,
                created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """

        soft_target_id = generate_uuid()
        metadata_payload = Json(state.metadata or {})

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    sql,
                    (
                        soft_target_id,
                        state.entity_type,
                        state.entity_id,
                        state.as_of_date,
                        state.soft_target_class.value,
                        state.soft_target_score,
                        state.weak_profile,
                        state.instability,
                        state.high_fragility,
                        state.complacent_pricing,
                        metadata_payload,
                    ),
                )
                conn.commit()
            finally:
                cursor.close()

    def get_latest_state(self, entity_type: str, entity_id: str) -> Optional[SoftTargetState]:
        """Return the most recent soft-target state for an entity, if any.
        
        Args:
            entity_type: Type of entity (e.g., "issuer", "instrument")
            entity_id: Unique identifier for the entity
        
        Returns:
            SoftTargetState for most recent date, or None if no records exist
        
        Raises:
            psycopg2.Error: If database query fails
        
        Example:
            >>> latest = storage.get_latest_state("issuer", "AAPL")
            >>> if latest:
            ...     print(latest.soft_target_class, latest.soft_target_score)
        """

        sql = """
            SELECT as_of_date,
                   entity_type,
                   entity_id,
                   soft_target_class,
                   soft_target_score,
                   weak_profile,
                   instability,
                   high_fragility,
                   complacent_pricing,
                   metadata
            FROM soft_target_classes
            WHERE entity_type = %s AND entity_id = %s
            ORDER BY as_of_date DESC
            LIMIT 1
        """

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (entity_type, entity_id))
                row = cursor.fetchone()
            finally:
                cursor.close()

        if row is None:
            return None

        (
            as_of_date,
            ent_type,
            ent_id,
            soft_class,
            soft_score,
            weak_profile,
            instability,
            high_fragility,
            complacent_pricing,
            metadata,
        ) = row

        return SoftTargetState(
            as_of_date=as_of_date,
            entity_type=ent_type,
            entity_id=ent_id,
            soft_target_class=SoftTargetClass(soft_class),
            soft_target_score=soft_score,
            weak_profile=weak_profile,
            instability=instability,
            high_fragility=high_fragility,
            complacent_pricing=complacent_pricing,
            metadata=metadata,
        )

    def get_history(
        self,
        entity_type: str,
        entity_id: str,
        start_date: date,
        end_date: date,
    ) -> list[SoftTargetState]:
        """Return soft-target history for an entity between two dates."""

        sql = """
            SELECT as_of_date,
                   entity_type,
                   entity_id,
                   soft_target_class,
                   soft_target_score,
                   weak_profile,
                   instability,
                   high_fragility,
                   complacent_pricing,
                   metadata
            FROM soft_target_classes
            WHERE entity_type = %s
              AND entity_id = %s
              AND as_of_date BETWEEN %s AND %s
            ORDER BY as_of_date ASC
        """

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (entity_type, entity_id, start_date, end_date))
                rows = cursor.fetchall()
            finally:
                cursor.close()

        history: list[SoftTargetState] = []
        for (
            as_of_date,
            ent_type,
            ent_id,
            soft_class,
            soft_score,
            weak_profile,
            instability,
            high_fragility,
            complacent_pricing,
            metadata,
        ) in rows:
            history.append(
                SoftTargetState(
                    as_of_date=as_of_date,
                    entity_type=ent_type,
                    entity_id=ent_id,
                    soft_target_class=SoftTargetClass(soft_class),
                    soft_target_score=soft_score,
                    weak_profile=weak_profile,
                    instability=instability,
                    high_fragility=high_fragility,
                    complacent_pricing=complacent_pricing,
                    metadata=metadata,
                )
            )

        return history

    def get_top_soft_targets(self, as_of_date: date, limit: int = 10) -> list[SoftTargetState]:
        """Return top-N soft targets by score for a given date."""

        sql = """
            SELECT as_of_date,
                   entity_type,
                   entity_id,
                   soft_target_class,
                   soft_target_score,
                   weak_profile,
                   instability,
                   high_fragility,
                   complacent_pricing,
                   metadata
            FROM soft_target_classes
            WHERE as_of_date = %s
            ORDER BY soft_target_score DESC
            LIMIT %s
        """

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (as_of_date, limit))
                rows = cursor.fetchall()
            finally:
                cursor.close()

        results: list[SoftTargetState] = []
        for (
            as_of_date,
            ent_type,
            ent_id,
            soft_class,
            soft_score,
            weak_profile,
            instability,
            high_fragility,
            complacent_pricing,
            metadata,
        ) in rows:
            results.append(
                SoftTargetState(
                    as_of_date=as_of_date,
                    entity_type=ent_type,
                    entity_id=ent_id,
                    soft_target_class=SoftTargetClass(soft_class),
                    soft_target_score=soft_score,
                    weak_profile=weak_profile,
                    instability=instability,
                    high_fragility=high_fragility,
                    complacent_pricing=complacent_pricing,
                    metadata=metadata,
                )
            )

        return results

    def get_transition_matrix(self, entity_type: str) -> dict[str, dict[str, float]]:
        """Return empirical soft-target transition probabilities for ``entity_type``.

        The matrix is derived from counts of consecutive soft-target
        states in ``soft_target_classes`` as::

            P(to | from) = count(from -> to) / sum_to count(from -> to)

        If no transitions exist for the requested entity_type, an empty
        dict is returned.
        """

        sql = """
            SELECT
                entity_id,
                as_of_date,
                soft_target_class
            FROM soft_target_classes
            WHERE entity_type = %s
            ORDER BY entity_id, as_of_date
        """

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (entity_type,))
                rows = cursor.fetchall()
            finally:
                cursor.close()

        if not rows:
            return {}

        # Compute counts of consecutive transitions per (entity_id).
        counts: dict[str, dict[str, int]] = {}
        prev_by_entity: dict[str, str] = {}

        for ent_id, as_of, soft_class in rows:
            soft_str = str(soft_class)
            ent_key = str(ent_id)
            if ent_key in prev_by_entity:
                from_class = prev_by_entity[ent_key]
                to_class = soft_str
                inner = counts.setdefault(from_class, {})
                inner[to_class] = inner.get(to_class, 0) + 1

            prev_by_entity[ent_key] = soft_str

        if not counts:
            return {}

        # Convert counts to probabilities.
        matrix: dict[str, dict[str, float]] = {}
        for from_class, to_counts in counts.items():
            total = float(sum(to_counts.values()))
            if total <= 0.0:
                continue
            matrix[from_class] = {
                to_class: count / total for to_class, count in to_counts.items()
            }

        return matrix
