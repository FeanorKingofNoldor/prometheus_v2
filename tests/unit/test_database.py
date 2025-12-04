"""
Prometheus v2: Tests for Database Connection Management

Test suite for ``prometheus.core.database``. Covers:
- Connection string construction
- Basic connection acquisition (integration, optional)
"""

from __future__ import annotations

import pytest

from prometheus.core.config import DatabaseConfig, get_config
from prometheus.core.database import DatabaseManager


class TestDatabaseManagerUnit:
    """Unit-level tests for DatabaseManager internals."""

    def test_create_connection_string(self) -> None:
        """Connection string should embed host, port, db name, user, and password."""

        db_config = DatabaseConfig(
            host="testhost",
            port=5433,
            name="testdb",
            user="testuser",
            password="testpass",
        )

        conn_str = DatabaseManager._create_connection_string(db_config)

        assert "host=testhost" in conn_str
        assert "port=5433" in conn_str
        assert "dbname=testdb" in conn_str
        assert "user=testuser" in conn_str
        assert "password=testpass" in conn_str


@pytest.mark.integration
class TestDatabaseManagerIntegration:
    """Integration tests that require a running PostgreSQL instance.

    These tests expect that the historical and runtime databases are
    reachable using the credentials provided in the environment (.env).
    """

    def test_get_runtime_connection_executes_simple_query(self) -> None:
        """Should be able to obtain a runtime connection and execute SELECT 1.

        This test will fail if the database is not running or credentials
        are incorrect. It is marked as an integration test and excluded
        from the default test run.
        """

        config = get_config()
        db_manager = DatabaseManager(config)

        with db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            cursor.close()

        assert result is not None
        assert result[0] == 1

    def test_get_historical_connection_executes_simple_query(self) -> None:
        """Should be able to obtain a historical connection and execute SELECT 1."""

        config = get_config()
        db_manager = DatabaseManager(config)

        with db_manager.get_historical_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            cursor.close()

        assert result is not None
        assert result[0] == 1
