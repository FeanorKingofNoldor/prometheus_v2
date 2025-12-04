"""Prometheus v2 – Profile storage helpers.

This module provides a small abstraction around reading and writing
profile snapshots from/to the `profiles` table in the runtime database.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from psycopg2.extras import Json

from prometheus.core.database import DatabaseManager
from prometheus.core.logging import get_logger
from prometheus.profiles.types import ProfileSnapshot


logger = get_logger(__name__)


@dataclass
class ProfileStorage:
    """Persistence helper for profile snapshots in `profiles` table."""

    db_manager: DatabaseManager

    def save_snapshot(self, snapshot: ProfileSnapshot) -> None:
        """Insert or update a profile snapshot.

        Uses INSERT ... ON CONFLICT on (issuer_id, as_of_date) to keep the
        latest structured fields and risk flags.
        """

        sql = """
            INSERT INTO profiles (
                issuer_id,
                as_of_date,
                structured,
                embedding_vector_ref,
                risk_flags,
                created_at
            ) VALUES (%s, %s, %s, %s, %s, NOW())
            ON CONFLICT (issuer_id, as_of_date)
            DO UPDATE SET
                structured = EXCLUDED.structured,
                embedding_vector_ref = EXCLUDED.embedding_vector_ref,
                risk_flags = EXCLUDED.risk_flags
        """

        structured_payload = Json(snapshot.structured)
        risk_flags_payload = Json(snapshot.risk_flags)

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    sql,
                    (
                        snapshot.issuer_id,
                        snapshot.as_of_date,
                        structured_payload,
                        None,  # embedding_vector_ref – reserved for future use
                        risk_flags_payload,
                    ),
                )
                conn.commit()
            finally:
                cursor.close()

    def load_snapshot(self, issuer_id: str, as_of_date: date) -> Optional[ProfileSnapshot]:
        """Load a profile snapshot for an issuer/date if present."""

        sql = """
            SELECT issuer_id, as_of_date, structured, risk_flags
            FROM profiles
            WHERE issuer_id = %s AND as_of_date = %s
            LIMIT 1
        """

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (issuer_id, as_of_date))
                row = cursor.fetchone()
            finally:
                cursor.close()

        if row is None:
            return None

        issuer_id_db, as_of_date_db, structured, risk_flags = row

        return ProfileSnapshot(
            issuer_id=issuer_id_db,
            as_of_date=as_of_date_db,
            structured=structured or {},
            embedding=None,
            risk_flags=risk_flags or {},
        )

    def load_latest_snapshot(self, issuer_id: str) -> Optional[ProfileSnapshot]:
        """Load the latest available profile snapshot for an issuer, if any."""

        sql = """
            SELECT issuer_id, as_of_date, structured, risk_flags
            FROM profiles
            WHERE issuer_id = %s
            ORDER BY as_of_date DESC
            LIMIT 1
        """

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (issuer_id,))
                row = cursor.fetchone()
            finally:
                cursor.close()

        if row is None:
            return None

        issuer_id_db, as_of_date_db, structured, risk_flags = row

        return ProfileSnapshot(
            issuer_id=issuer_id_db,
            as_of_date=as_of_date_db,
            structured=structured or {},
            embedding=None,
            risk_flags=risk_flags or {},
        )