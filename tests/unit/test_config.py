"""
Prometheus v2: Tests for Configuration Management

Test suite for ``prometheus.core.config``. Covers:
- Default configuration values
- Environment variable overrides
- .env loading behaviour
"""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from prometheus.core.config import PrometheusConfig, get_config, load_config


class TestPrometheusConfig:
    """Tests for the PrometheusConfig settings model."""

    def test_default_values(self) -> None:
        """Default values should match sensible local-development defaults."""

        config = PrometheusConfig()

        assert config.historical_db_host == "localhost"
        assert config.historical_db_port == 5432
        assert config.runtime_db_host == "localhost"
        assert config.runtime_db_port == 5432
        assert config.log_level.upper() == "INFO"
        assert config.environment == "development"

    def test_env_var_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Environment variables must override default values."""

        monkeypatch.setenv("HISTORICAL_DB_HOST", "test-host")
        monkeypatch.setenv("HISTORICAL_DB_PORT", "5439")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        config = PrometheusConfig()

        assert config.historical_db_host == "test-host"
        assert config.historical_db_port == 5439
        assert config.log_level.upper() == "DEBUG"

    def test_database_properties_return_databaseconfig(self) -> None:
        """Database helper properties should return DatabaseConfig objects."""

        config = PrometheusConfig()

        hist_db = config.historical_db
        assert hist_db.host == config.historical_db_host
        assert hist_db.port == config.historical_db_port
        assert hist_db.name == config.historical_db_name

        runtime_db = config.runtime_db
        assert runtime_db.host == config.runtime_db_host
        assert runtime_db.port == config.runtime_db_port
        assert runtime_db.name == config.runtime_db_name


class TestLoadConfig:
    """Tests for the top-level load_config function."""

    def test_load_from_explicit_env_file(self, tmp_path: Path) -> None:
        """An explicit env_file should be loaded when it exists."""

        env_path = tmp_path / ".env.test"
        env_path.write_text("HISTORICAL_DB_HOST=from_env_file\nRUNTIME_DB_PORT=5440\n")

        config = load_config(env_file=env_path)

        assert config.historical_db_host == "from_env_file"
        assert config.runtime_db_port == 5440

    def test_missing_explicit_env_file_raises(self, tmp_path: Path) -> None:
        """A missing explicit env file should raise FileNotFoundError."""

        missing = tmp_path / "does_not_exist.env"
        with pytest.raises(FileNotFoundError):
            load_config(env_file=missing)


class TestGetConfigSingleton:
    """Tests for the get_config singleton accessor."""

    def test_get_config_returns_singleton(self) -> None:
        """get_config should always return the same instance within a process."""

        config_1 = get_config()
        config_2 = get_config()

        assert config_1 is config_2
        # Basic sanity check on a field
        assert isinstance(config_1.historical_db_host, str)
