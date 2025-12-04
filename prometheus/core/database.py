"""
Prometheus v2: Database Connection Management

This module provides connection pooling and convenience helpers for
connecting to the historical and runtime PostgreSQL databases. It uses
psycopg2's ``SimpleConnectionPool`` for Iteration 1, with a thin wrapper
that exposes context managers for acquiring connections.

Key responsibilities:
- Maintain connection pools for historical_db and runtime_db
- Provide context managers to acquire/release connections safely
- Encapsulate connection string construction from configuration

External dependencies:
- psycopg2-binary: PostgreSQL client and connection pooling

Database tables accessed:
- None directly (this module is infrastructure only)

Thread safety: Thread-safe under normal psycopg2 pool usage. The
DatabaseManager should be treated as a process-wide singleton.

Author: Prometheus Team
Created: 2025-11-24
Last Modified: 2025-11-24
Status: Development
Version: v0.1.0
"""

# ============================================================================
# Imports
# ============================================================================

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, Optional

from psycopg2 import pool
from psycopg2.extensions import connection as PsycopgConnection

from prometheus.core.config import DatabaseConfig, PrometheusConfig, get_config
from prometheus.core.logging import get_logger

# ============================================================================
# Module Setup
# ============================================================================

logger = get_logger(__name__)


class DatabaseError(Exception):
    """Raised when a database connection or operation fails."""


class DatabaseManager:
    """Manage connection pools for Prometheus databases.

    The :class:`DatabaseManager` is responsible for creating and managing
    connection pools for both the historical and runtime databases. It
    exposes context managers that yield psycopg2 connections and
    automatically return them to the pool.

    Typical usage::

        from prometheus.core.database import get_db_manager

        db = get_db_manager()
        with db.get_historical_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            cursor.close()

    Attributes:
        config: Global Prometheus configuration instance.
        _historical_pool: Connection pool for the historical DB.
        _runtime_pool: Connection pool for the runtime DB.
    """

    def __init__(self, config: PrometheusConfig) -> None:
        """Initialise the database manager with configuration.

        Args:
            config: Loaded Prometheus configuration.
        """

        self.config = config
        self._historical_pool: Optional[pool.SimpleConnectionPool] = None
        self._runtime_pool: Optional[pool.SimpleConnectionPool] = None
        logger.info("DatabaseManager initialised")

    # ======================================================================
    # Internal helpers
    # ======================================================================

    @staticmethod
    def _create_connection_string(db_config: DatabaseConfig) -> str:
        """Build a PostgreSQL connection string from configuration.

        Args:
            db_config: Database configuration.

        Returns:
            A DSN string suitable for psycopg2.
        """

        return (
            f"host={db_config.host} "
            f"port={db_config.port} "
            f"dbname={db_config.name} "
            f"user={db_config.user} "
            f"password={db_config.password}"
        )

    def _get_or_create_pool(
        self,
        attr_name: str,
        db_config: DatabaseConfig,
    ) -> pool.SimpleConnectionPool:
        """Return an existing pool or create a new one.

        Args:
            attr_name: Attribute name for the pool ("_historical_pool" or
                "_runtime_pool").
            db_config: Database configuration for the target database.

        Returns:
            A :class:`psycopg2.pool.SimpleConnectionPool` instance.

        Raises:
            DatabaseError: If the pool cannot be created.
        """

        existing = getattr(self, attr_name)
        if existing is not None:
            return existing

        dsn = self._create_connection_string(db_config)
        try:
            new_pool = pool.SimpleConnectionPool(
                minconn=1,
                maxconn=db_config.pool_size,
                dsn=dsn,
            )
        except Exception as exc:  # pragma: no cover - connection errors
            logger.error(f"Failed to create connection pool: {exc}")
            raise DatabaseError("Failed to create database connection pool") from exc

        setattr(self, attr_name, new_pool)
        logger.info("Created connection pool for database '%s'", db_config.name)
        return new_pool

    # ======================================================================
    # Public context managers
    # ======================================================================

    @contextmanager
    def get_historical_connection(self) -> Generator[PsycopgConnection, None, None]:
        """Yield a connection to the historical database.

        Yields:
            A psycopg2 connection object. The connection is returned to the
            pool when the context manager exits.

        Raises:
            DatabaseError: If a connection cannot be acquired.
        """

        pool_obj = self._get_or_create_pool("_historical_pool", self.config.historical_db)
        try:
            conn = pool_obj.getconn()
        except Exception as exc:  # pragma: no cover - connection errors
            logger.error(f"Failed to acquire historical_db connection: {exc}")
            raise DatabaseError("Failed to acquire historical_db connection") from exc

        try:
            yield conn
        finally:
            pool_obj.putconn(conn)

    @contextmanager
    def get_runtime_connection(self) -> Generator[PsycopgConnection, None, None]:
        """Yield a connection to the runtime database.

        Yields:
            A psycopg2 connection object. The connection is returned to the
            pool when the context manager exits.

        Raises:
            DatabaseError: If a connection cannot be acquired.
        """

        pool_obj = self._get_or_create_pool("_runtime_pool", self.config.runtime_db)
        try:
            conn = pool_obj.getconn()
        except Exception as exc:  # pragma: no cover - connection errors
            logger.error(f"Failed to acquire runtime_db connection: {exc}")
            raise DatabaseError("Failed to acquire runtime_db connection") from exc

        try:
            yield conn
        finally:
            pool_obj.putconn(conn)

    # ======================================================================
    # Lifecycle
    # ======================================================================

    def close_all(self) -> None:
        """Close all connection pools.

        This method should be called during graceful shutdown to ensure
        all connections are closed cleanly.
        """

        if self._historical_pool is not None:
            self._historical_pool.closeall()
            self._historical_pool = None
            logger.info("Closed historical_db connection pool")

        if self._runtime_pool is not None:
            self._runtime_pool.closeall()
            self._runtime_pool = None
            logger.info("Closed runtime_db connection pool")


# ============================================================================
# Global Accessor
# ============================================================================

_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """Return the global :class:`DatabaseManager` singleton.

    The manager is created on first access using the global configuration
    from :func:`prometheus.core.config.get_config`.

    Returns:
        A :class:`DatabaseManager` instance.
    """

    global _db_manager
    if _db_manager is None:
        config = get_config()
        _db_manager = DatabaseManager(config)
    return _db_manager


# TODO(prometheus, 2025-11-24): Add SQLAlchemy engine integration
# In a later iteration we may want to expose SQLAlchemy Engine objects
# alongside raw psycopg2 connections to support ORM usage and more
# advanced transaction management. For Iteration 1 we keep the database
# layer minimal and explicit.
