"""Prometheus v2 – Fragility Alpha storage helpers.

This module provides a small abstraction around the ``fragility_measures``
runtime table used by the Fragility Alpha Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from psycopg2.extras import Json

from prometheus.core.database import DatabaseManager
from prometheus.core.ids import generate_uuid
from prometheus.core.logging import get_logger

from .types import FragilityClass, FragilityMeasure


logger = get_logger(__name__)


@dataclass
class FragilityStorage:
    """Persistence helper for fragility measures.

    The storage layer intentionally keeps the schema surface small and
    explicit so that other components (Portfolio & Risk, Monitoring,
    Meta-Orchestrator) can depend on it without re-implementing SQL.
    """

    db_manager: DatabaseManager

    def save_measure(self, measure: FragilityMeasure) -> None:
        """Insert a fragility measure into ``fragility_measures``."""

        sql = """
            INSERT INTO fragility_measures (
                fragility_id,
                entity_type,
                entity_id,
                as_of_date,
                fragility_score,
                scenario_losses,
                metadata,
                created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """

        fragility_id = generate_uuid()
        scenario_payload = Json(measure.scenario_losses or {})
        metadata_payload = Json(measure.metadata or {})

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    sql,
                    (
                        fragility_id,
                        measure.entity_type,
                        measure.entity_id,
                        measure.as_of_date,
                        float(measure.fragility_score),
                        scenario_payload,
                        metadata_payload,
                    ),
                )
                conn.commit()
            finally:
                cursor.close()

    def get_latest_measures_for_entities(
        self,
        entity_type: str,
        entity_ids: list[str],
    ) -> dict[str, FragilityMeasure]:
        """Return latest fragility measures for a batch of entities.

        The result is a mapping from ``entity_id`` to
        :class:`FragilityMeasure`. If no measures exist for a given
        ``entity_id`` it is simply omitted from the mapping.
        """

        if not entity_ids:
            return {}

        sql = """
            SELECT DISTINCT ON (entity_id)
                entity_type,
                entity_id,
                as_of_date,
                fragility_score,
                scenario_losses,
                metadata
            FROM fragility_measures
            WHERE entity_type = %s
              AND entity_id = ANY(%s)
            ORDER BY entity_id, as_of_date DESC
        """

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (entity_type, list(entity_ids)))
                rows = cursor.fetchall()
            finally:
                cursor.close()

        results: dict[str, FragilityMeasure] = {}
        for (
            ent_type,
            ent_id,
            as_of_date,
            fragility_score,
            scenario_losses,
            metadata,
        ) in rows:
            components = dict((metadata or {}).get("components", {}))
            class_str = str((metadata or {}).get("class_label", FragilityClass.NONE.value))
            class_label = FragilityClass(class_str)
            results[str(ent_id)] = FragilityMeasure(
                entity_type=ent_type,
                entity_id=str(ent_id),
                as_of_date=as_of_date,
                fragility_score=float(fragility_score),
                class_label=class_label,
                scenario_losses=scenario_losses or {},
                components=components,
                metadata=metadata or {},
            )

        return results

    def get_latest_measure(
        self,
        entity_type: str,
        entity_id: str,
    ) -> Optional[FragilityMeasure]:
        """Return the most recent fragility measure for an entity, if any."""

        sql = """
            SELECT
                entity_type,
                entity_id,
                as_of_date,
                fragility_score,
                scenario_losses,
                metadata
            FROM fragility_measures
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
            ent_type,
            ent_id,
            as_of_date,
            fragility_score,
            scenario_losses,
            metadata,
        ) = row

        components = dict((metadata or {}).get("components", {}))
        class_str = str((metadata or {}).get("class_label", FragilityClass.NONE.value))
        class_label = FragilityClass(class_str)

        return FragilityMeasure(
            entity_type=ent_type,
            entity_id=ent_id,
            as_of_date=as_of_date,
            fragility_score=float(fragility_score),
            class_label=class_label,
            scenario_losses=scenario_losses or {},
            components=components,
            metadata=metadata or {},
        )

    def get_history(
        self,
        entity_type: str,
        entity_id: str,
        start_date: date,
        end_date: date,
    ) -> List[FragilityMeasure]:
        """Return fragility history for an entity between two dates."""

        sql = """
            SELECT
                entity_type,
                entity_id,
                as_of_date,
                fragility_score,
                scenario_losses,
                metadata
            FROM fragility_measures
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

        measures: List[FragilityMeasure] = []
        for (
            ent_type,
            ent_id,
            as_of_date,
            fragility_score,
            scenario_losses,
            metadata,
        ) in rows:
            components = dict((metadata or {}).get("components", {}))
            class_str = str((metadata or {}).get("class_label", FragilityClass.NONE.value))
            class_label = FragilityClass(class_str)
            measures.append(
                FragilityMeasure(
                    entity_type=ent_type,
                    entity_id=ent_id,
                    as_of_date=as_of_date,
                    fragility_score=float(fragility_score),
                    class_label=class_label,
                    scenario_losses=scenario_losses or {},
                    components=components,
                    metadata=metadata or {},
                )
            )

        return measures
