"""Prometheus v2 – Synthetic scenario storage helpers.

This module provides a thin storage layer around the scenario-related
runtime database tables used by the Synthetic Scenario Engine:

- scenario_sets
- scenario_paths

The goal is to keep database access logic out of the core engine
implementation while remaining explicit and easy to inspect.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from psycopg2.extras import Json

from prometheus.core.database import DatabaseManager
from prometheus.core.ids import generate_uuid
from prometheus.core.logging import get_logger

from .types import ScenarioRequest, ScenarioSetRef


logger = get_logger(__name__)


@dataclass(frozen=True)
class ScenarioPathRow:
    """In-memory representation of a scenario_paths row.

    Attributes:
        scenario_id: Index of the path within the set (0..num_paths-1).
        horizon_index: Step index within the path (0..H).
        instrument_id: Optional instrument identifier.
        factor_id: Optional factor identifier.
        macro_id: Optional macro identifier.
        return_value: Shock as a return relative to baseline.
        price: Optional price level associated with the step.
        shock_metadata: Optional free-form metadata for diagnostics.
    """

    scenario_id: int
    horizon_index: int
    instrument_id: Optional[str]
    factor_id: Optional[str]
    macro_id: Optional[str]
    return_value: float
    price: Optional[float] = None
    shock_metadata: Optional[Dict[str, object]] = None


@dataclass
class ScenarioStorage:
    """Persistence helper for synthetic scenario sets and paths."""

    db_manager: DatabaseManager

    def create_scenario_set(
        self,
        request: ScenarioRequest,
        created_by: Optional[str] = None,
    ) -> ScenarioSetRef:
        """Insert a new scenario set definition and return its reference."""

        scenario_set_id = generate_uuid()

        sql = """
            INSERT INTO scenario_sets (
                scenario_set_id,
                name,
                description,
                category,
                horizon_days,
                num_paths,
                base_universe_filter,
                base_date_start,
                base_date_end,
                regime_filter,
                generator_spec,
                created_at,
                created_by,
                tags,
                metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s, %s)
        """

        base_universe_filter = Json(request.universe_filter or {})
        regime_filter = request.regime_filter
        generator_spec = Json(request.generator_spec or {})

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    sql,
                    (
                        scenario_set_id,
                        request.name,
                        request.description,
                        request.category,
                        request.horizon_days,
                        request.num_paths,
                        base_universe_filter,
                        request.base_date_start,
                        request.base_date_end,
                        regime_filter,
                        generator_spec,
                        created_by,
                        None,
                        Json({}),
                    ),
                )
                conn.commit()
            finally:
                cursor.close()

        return ScenarioSetRef(
            scenario_set_id=scenario_set_id,
            name=request.name,
            category=request.category,
            horizon_days=request.horizon_days,
            num_paths=request.num_paths,
        )

    def save_scenario_paths(
        self,
        scenario_set_id: str,
        rows: Iterable[ScenarioPathRow],
    ) -> None:
        """Persist a batch of scenario paths for a given set.

        Existing rows for the set are not deleted; callers should ensure
        they either insert a complete set in one go or clear previous
        paths first if necessary.
        """

        sql = """
            INSERT INTO scenario_paths (
                scenario_set_id,
                scenario_id,
                horizon_index,
                instrument_id,
                factor_id,
                macro_id,
                return_value,
                price,
                shock_metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        rows = list(rows)
        if not rows:
            return

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                for r in rows:
                    cursor.execute(
                        sql,
                        (
                            scenario_set_id,
                            r.scenario_id,
                            r.horizon_index,
                            r.instrument_id,
                            r.factor_id,
                            r.macro_id,
                            float(r.return_value),
                            r.price,
                            Json(r.shock_metadata or {}),
                        ),
                    )
                conn.commit()
            finally:
                cursor.close()

    def list_scenario_sets(self, category: Optional[str] = None) -> List[ScenarioSetRef]:
        """Return a list of scenario sets, optionally filtered by category."""

        if category is None:
            sql = """
                SELECT scenario_set_id, name, category, horizon_days, num_paths
                FROM scenario_sets
                ORDER BY created_at DESC
            """
            params: tuple[object, ...] = ()
        else:
            sql = """
                SELECT scenario_set_id, name, category, horizon_days, num_paths
                FROM scenario_sets
                WHERE category = %s
                ORDER BY created_at DESC
            """
            params = (category,)

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, params or None)
                rows = cursor.fetchall()
            finally:
                cursor.close()

        return [
            ScenarioSetRef(
                scenario_set_id=set_id,
                name=name,
                category=category_db,
                horizon_days=int(horizon_days),
                num_paths=int(num_paths),
            )
            for set_id, name, category_db, horizon_days, num_paths in rows
        ]

    def get_scenario_set_metadata(self, scenario_set_id: str) -> Dict[str, object]:
        """Return raw metadata for a scenario set.

        The result includes configuration fields that may be useful to
        callers wishing to reconstruct or analyse the set.
        """

        sql = """
            SELECT
                name,
                description,
                category,
                horizon_days,
                num_paths,
                base_universe_filter,
                base_date_start,
                base_date_end,
                regime_filter,
                generator_spec,
                tags,
                metadata
            FROM scenario_sets
            WHERE scenario_set_id = %s
        """

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (scenario_set_id,))
                row = cursor.fetchone()
            finally:
                cursor.close()

        if row is None:
            msg = f"scenario_set not found: {scenario_set_id}"
            raise ValueError(msg)

        (
            name,
            description,
            category,
            horizon_days,
            num_paths,
            base_universe_filter,
            base_date_start,
            base_date_end,
            regime_filter,
            generator_spec,
            tags,
            metadata,
        ) = row

        return {
            "scenario_set_id": scenario_set_id,
            "name": name,
            "description": description,
            "category": category,
            "horizon_days": int(horizon_days),
            "num_paths": int(num_paths),
            "base_universe_filter": base_universe_filter or {},
            "base_date_start": base_date_start,
            "base_date_end": base_date_end,
            "regime_filter": regime_filter or [],
            "generator_spec": generator_spec or {},
            "tags": tags or [],
            "metadata": metadata or {},
        }
