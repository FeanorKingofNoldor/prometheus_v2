"""
Prometheus v2: Configuration Management

This module provides centralised configuration management for Prometheus v2.
It loads configuration from environment variables (optionally via a .env
file), with strongly typed access via Pydantic BaseSettings.

Key responsibilities:
- Load and validate configuration from environment variables
- Provide typed configuration objects for database and logging
- Expose a cached global configuration accessor for convenience

External dependencies:
- pydantic: Data validation and settings management
- pydantic-settings: Environment variable integration for settings
- python-dotenv: Optional .env loading for local development

Database tables accessed:
- None (configuration only)

Thread safety: Thread-safe (configuration is immutable after initial load)

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

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# ============================================================================
# Data Models
# ============================================================================


class DatabaseConfig(BaseModel):
    """Database connection configuration.

    This structure describes a single PostgreSQL database connection,
    including connection parameters and basic pooling configuration. It is
    intentionally minimal; more advanced pooling behaviour is handled in
    the database module.

    Attributes:
        host: Database host name or IP address.
        port: TCP port for the PostgreSQL instance.
        name: Database name.
        user: Database user for connections.
        password: Password for the database user.
        pool_size: Maximum number of connections in the pool.
        max_overflow: Maximum number of connections above pool_size.
        pool_timeout: Timeout (in seconds) when acquiring a connection.
        echo: Whether to echo SQL statements (for debugging).
    """

    host: str
    port: int
    name: str
    user: str
    password: str
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    echo: bool = False


class LoggingConfig(BaseModel):
    """Logging configuration for Prometheus.

    Attributes:
        level: Log level name (e.g. "INFO", "DEBUG").
        file: Path to the primary log file.
    """

    level: str = "INFO"
    file: str = "prometheus.log"


class ExecutionRiskConfig(BaseModel):
    """Execution risk limits for live/paper trading.

    All values are loaded from environment variables via :class:`PrometheusConfig`.
    A value of ``0`` or ``False`` typically means "disabled" for that
    particular check.

    Attributes:
        enabled: Master switch for the risk wrapper.
        max_order_notional: Maximum notional per single order (account
            currency). ``0`` disables this check.
        max_position_notional: Maximum notional per single instrument
            position after applying the order. ``0`` disables this check.
        max_leverage: Maximum gross exposure divided by equity. ``0``
            disables this check.
    """

    enabled: bool = True
    max_order_notional: float = 0.0
    max_position_notional: float = 0.0
    max_leverage: float = 0.0


class PrometheusConfig(BaseSettings):
    """Main Prometheus configuration loaded from environment variables.

    Environment variables use the following mapping by default:

    - HISTORICAL_DB_* for historical database
    - RUNTIME_DB_* for runtime database
    - LOG_LEVEL / LOG_FILE for logging
    - ENVIRONMENT for environment name (development/staging/production)

    Environment variables take precedence over any other configuration
    source. For this early iteration we do not merge YAML configs, but
    this can be added later if needed.
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    # Historical DB
    historical_db_host: str = Field(default="localhost", alias="HISTORICAL_DB_HOST")
    historical_db_port: int = Field(default=5432, alias="HISTORICAL_DB_PORT")
    historical_db_name: str = Field(
        default="prometheus_historical", alias="HISTORICAL_DB_NAME"
    )
    historical_db_user: str = Field(default="prometheus", alias="HISTORICAL_DB_USER")
    historical_db_password: str = Field(default="", alias="HISTORICAL_DB_PASSWORD")

    # Runtime DB
    runtime_db_host: str = Field(default="localhost", alias="RUNTIME_DB_HOST")
    runtime_db_port: int = Field(default=5432, alias="RUNTIME_DB_PORT")
    runtime_db_name: str = Field(default="prometheus_runtime", alias="RUNTIME_DB_NAME")
    runtime_db_user: str = Field(default="prometheus", alias="RUNTIME_DB_USER")
    runtime_db_password: str = Field(default="", alias="RUNTIME_DB_PASSWORD")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_file: str = Field(default="prometheus.log", alias="LOG_FILE")

    # Environment
    environment: str = Field(default="development", alias="ENVIRONMENT")

    # Execution risk (optional, env-driven)
    execution_risk_enabled: bool = Field(default=False, alias="EXEC_RISK_ENABLED")
    execution_risk_max_order_notional: float = Field(
        default=0.0, alias="EXEC_RISK_MAX_ORDER_NOTIONAL"
    )
    execution_risk_max_position_notional: float = Field(
        default=0.0, alias="EXEC_RISK_MAX_POSITION_NOTIONAL"
    )
    execution_risk_max_leverage: float = Field(
        default=0.0, alias="EXEC_RISK_MAX_LEVERAGE"
    )

    @property
    def historical_db(self) -> DatabaseConfig:
        """Return database configuration for the historical DB."""

        return DatabaseConfig(
            host=self.historical_db_host,
            port=self.historical_db_port,
            name=self.historical_db_name,
            user=self.historical_db_user,
            password=self.historical_db_password,
        )

    @property
    def runtime_db(self) -> DatabaseConfig:
        """Return database configuration for the runtime DB."""

        return DatabaseConfig(
            host=self.runtime_db_host,
            port=self.runtime_db_port,
            name=self.runtime_db_name,
            user=self.runtime_db_user,
            password=self.runtime_db_password,
        )

    @property
    def execution_risk(self) -> ExecutionRiskConfig:
        """Return execution risk configuration.

        Environment variables:
        - EXEC_RISK_ENABLED
        - EXEC_RISK_MAX_ORDER_NOTIONAL
        - EXEC_RISK_MAX_POSITION_NOTIONAL
        - EXEC_RISK_MAX_LEVERAGE
        """

        return ExecutionRiskConfig(
            enabled=self.execution_risk_enabled,
            max_order_notional=self.execution_risk_max_order_notional,
            max_position_notional=self.execution_risk_max_position_notional,
            max_leverage=self.execution_risk_max_leverage,
        )


# ============================================================================
# Public API
# ============================================================================


def load_config(env_file: Optional[Path] = None) -> PrometheusConfig:
    """Load Prometheus configuration.

    For local development this function will attempt to load a `.env` file
    from the project root if one is present. Environment variables always
    take precedence over values from `.env`.

    Args:
        env_file: Optional explicit path to a `.env` file. If omitted,
            the function will look for `.env` in the current working
            directory.

    Returns:
        A fully populated :class:`PrometheusConfig` instance.

    Raises:
        FileNotFoundError: If an explicit ``env_file`` is provided but
            does not exist.
    """

    if env_file is not None:
        if not env_file.exists():
            msg = f"Environment file not found: {env_file}"
            raise FileNotFoundError(msg)
        # When an explicit env_file is provided, it should take precedence
        # over any existing values so that tests and local runs can
        # reliably control configuration.
        load_dotenv(env_file, override=True)
    else:
        # Best-effort: load .env from CWD if it exists. This is safe
        # because environment variables still take precedence.
        default_env = Path(".env")
        if default_env.exists():
            load_dotenv(default_env)

    return PrometheusConfig()  # type: ignore[call-arg]


_global_config: Optional[PrometheusConfig] = None


def get_config() -> PrometheusConfig:
    """Return the global Prometheus configuration singleton.

    The configuration is loaded on first access (lazy loading) and cached
    for subsequent calls. This should be the primary entrypoint for most
    modules that need configuration values.

    Returns:
        A cached :class:`PrometheusConfig` instance.
    """

    global _global_config
    if _global_config is None:
        _global_config = load_config()
    return _global_config


# TODO(prometheus, 2025-11-24): Add optional YAML config merging
# In a later iteration we may want to merge values from
# configs/core/base.yaml into the Pydantic settings model, allowing
# environment variables to override YAML defaults. For Iteration 1 we
# keep configuration simple and environment-driven.
