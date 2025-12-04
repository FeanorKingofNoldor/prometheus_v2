# ITERATION 1: Foundation & Database Core - DETAILED EXECUTION PLAN

**Duration**: 2-3 days  
**Status**: READY TO START  
**Branch**: `iter-1-foundation`

---

## ⚠️ BEFORE YOU START: READ CODING STANDARDS

**MANDATORY**: Before writing any code, read these files:

1. **[CODING_STANDARDS.md](CODING_STANDARDS.md)** - Complete coding standards guide
2. **[CODING_STANDARDS_QUICK_REF.md](CODING_STANDARDS_QUICK_REF.md)** - Quick reference card

**Key requirements for ALL code**:
- ✅ File headers with metadata (author, created, version, etc.)
- ✅ Google-style docstrings for all functions
- ✅ Complete type hints (mypy --strict compatible)
- ✅ Inline comments explaining "why", not "what"
- ✅ Section dividers for organization
- ✅ Consistent naming conventions

**Copy-paste templates are provided in CODING_STANDARDS_QUICK_REF.md**

---

## Quick Start

```bash
# 1. Create feature branch
git checkout -b iter-1-foundation

# 2. Follow the steps below in order
# 3. Run tests after each step
# 4. When all exit criteria met, merge to main
```

---

## STEP 1: Project Structure Setup (30 minutes)

### 1.1 Create Directory Structure

```bash
cd /home/feanor/coding_projects/prometheus_v2

# Create all package directories
mkdir -p prometheus/{core,data,encoders,profiles,regime,stability,assessment,universe,portfolio,meta,synthetic,monitoring,execution,orchestration,scripts}

# Create __init__.py in each package
touch prometheus/__init__.py
touch prometheus/{core,data,encoders,profiles,regime,stability,assessment,universe,portfolio,meta,synthetic,monitoring,execution,orchestration,scripts}/__init__.py

# Create test directories
mkdir -p tests/{unit,integration,fixtures}
touch tests/__init__.py
touch tests/unit/__init__.py
touch tests/integration/__init__.py
touch tests/fixtures/__init__.py

# Create config directories
mkdir -p configs/{core,regime,assessment,universe,portfolio}

# Create docs directory for dev workflows
mkdir -p dev_workflows

# Create migrations directory
mkdir -p migrations/versions
```

### 1.2 Create `pyproject.toml`

```bash
cat > pyproject.toml << 'EOF'
[build-system]
requires = ["setuptools>=68.0.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "prometheus"
version = "0.1.0"
description = "Prometheus v2 - Quantitative Trading System"
readme = "README.md"
requires-python = ">=3.11"
authors = [
    {name = "Prometheus Team"}
]

dependencies = [
    "numpy>=1.24.0",
    "pandas>=2.0.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "psycopg2-binary>=2.9.0",
    "sqlalchemy>=2.0.0",
    "alembic>=1.12.0",
    "python-dateutil>=2.8.0",
    "pyyaml>=6.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "pytest-asyncio>=0.21.0",
    "mypy>=1.5.0",
    "ruff>=0.0.285",
    "pydocstyle>=6.3.0",
    "types-PyYAML",
    "types-python-dateutil",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --strict-markers --tb=short"

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
strict = true

[tool.ruff]
line-length = 100
target-version = "py311"
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "N",   # pep8-naming
    "UP",  # pyupgrade
]
ignore = []

[tool.ruff.per-file-ignores]
"__init__.py" = ["F401"]  # Allow unused imports in __init__.py
"tests/*" = ["D", "ANN"]  # Don't require docstrings/annotations in tests

[tool.coverage.run]
source = ["prometheus"]
omit = ["tests/*", "prometheus/scripts/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
]
EOF
```

### 1.3 Create Configuration Files

```bash
# .env.example
cat > .env.example << 'EOF'
# Database Configuration
HISTORICAL_DB_HOST=localhost
HISTORICAL_DB_PORT=5432
HISTORICAL_DB_NAME=prometheus_historical
HISTORICAL_DB_USER=prometheus
HISTORICAL_DB_PASSWORD=change_me

RUNTIME_DB_HOST=localhost
RUNTIME_DB_PORT=5432
RUNTIME_DB_NAME=prometheus_runtime
RUNTIME_DB_USER=prometheus
RUNTIME_DB_PASSWORD=change_me

# Logging
LOG_LEVEL=INFO
LOG_FILE=prometheus.log

# Environment
ENVIRONMENT=development
EOF

# Base config
cat > configs/core/base.yaml << 'EOF'
database:
  historical:
    pool_size: 5
    max_overflow: 10
    pool_timeout: 30
    echo: false
  runtime:
    pool_size: 5
    max_overflow: 10
    pool_timeout: 30
    echo: false

logging:
  version: 1
  disable_existing_loggers: false
  formatters:
    standard:
      format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
      datefmt: '%Y-%m-%d %H:%M:%S'
    json:
      class: pythonjsonlogger.jsonlogger.JsonFormatter
      format: '%(asctime)s %(name)s %(levelname)s %(message)s'
  handlers:
    console:
      class: logging.StreamHandler
      formatter: standard
      stream: ext://sys.stdout
    file:
      class: logging.handlers.RotatingFileHandler
      formatter: json
      filename: prometheus.log
      maxBytes: 10485760  # 10MB
      backupCount: 5
  loggers:
    prometheus:
      level: INFO
      handlers: [console, file]
      propagate: false
  root:
    level: INFO
    handlers: [console, file]
EOF
```

### 1.4 Create README.md

```bash
cat > README.md << 'EOF'
# Prometheus v2

Quantitative trading system built from the ground up with comprehensive architectural design.

## Current Status

**Iteration 1**: Foundation & Database Core ✅ (in progress)

## Quick Start

```bash
# Install dependencies
pip install -e ".[dev]"

# Set up environment
cp .env.example .env
# Edit .env with your database credentials

# Run tests
pytest

# Type checking
mypy prometheus/

# Linting
ruff check prometheus/
```

## Architecture

See `docs/architecture/99_master_architecture.md` for complete system design.

## Development

Each iteration builds on the previous one. See `ITERATION_1_DETAILED.md` for current work.

## Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_config.py -v

# Run with coverage
pytest --cov=prometheus --cov-report=html
```
EOF
```

### 1.5 Install Dependencies

```bash
# Create virtual environment (if not already in one)
python3.11 -m venv venv
source venv/bin/activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

**✅ Checkpoint**: Directory structure created, dependencies installed

---

## STEP 2: Core Infrastructure - Config (1 hour)

### 2.1 Create `prometheus/core/types.py`

```python
"""Common type definitions for Prometheus."""

from typing import Any, Dict, TypeAlias

# Type aliases for clarity
ConfigDict: TypeAlias = Dict[str, Any]
MetadataDict: TypeAlias = Dict[str, Any]
```

### 2.2 Create `prometheus/core/config.py`

```python
"""Configuration management for Prometheus.

Loads configuration from YAML files and environment variables using Pydantic.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseModel):
    """Database connection configuration."""

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
    """Logging configuration."""

    level: str = "INFO"
    file: str = "prometheus.log"
    format: str = "json"


class PrometheusConfig(BaseSettings):
    """Main Prometheus configuration.
    
    Loads from environment variables with PROMETHEUS_ prefix.
    """

    model_config = SettingsConfigDict(
        env_prefix="PROMETHEUS_",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    # Database configs
    historical_db_host: str = Field(default="localhost", alias="HISTORICAL_DB_HOST")
    historical_db_port: int = Field(default=5432, alias="HISTORICAL_DB_PORT")
    historical_db_name: str = Field(default="prometheus_historical", alias="HISTORICAL_DB_NAME")
    historical_db_user: str = Field(default="prometheus", alias="HISTORICAL_DB_USER")
    historical_db_password: str = Field(default="", alias="HISTORICAL_DB_PASSWORD")

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

    @property
    def historical_db(self) -> DatabaseConfig:
        """Get historical database configuration."""
        return DatabaseConfig(
            host=self.historical_db_host,
            port=self.historical_db_port,
            name=self.historical_db_name,
            user=self.historical_db_user,
            password=self.historical_db_password,
        )

    @property
    def runtime_db(self) -> DatabaseConfig:
        """Get runtime database configuration."""
        return DatabaseConfig(
            host=self.runtime_db_host,
            port=self.runtime_db_port,
            name=self.runtime_db_name,
            user=self.runtime_db_user,
            password=self.runtime_db_password,
        )


def load_config(
    env_file: Optional[Path] = None,
    yaml_configs: Optional[Dict[str, Path]] = None,
) -> PrometheusConfig:
    """Load configuration from environment and YAML files.
    
    Args:
        env_file: Path to .env file (defaults to .env in project root)
        yaml_configs: Dict of config name → path (e.g. {"base": Path("configs/base.yaml")})
    
    Returns:
        PrometheusConfig with merged configuration
    
    Raises:
        FileNotFoundError: If specified config files don't exist
        ValueError: If configuration is invalid
    """
    # Load .env file if specified
    if env_file is not None:
        if not env_file.exists():
            raise FileNotFoundError(f"Environment file not found: {env_file}")
        from dotenv import load_dotenv
        load_dotenv(env_file)

    # Load YAML configs if specified (for future use)
    yaml_data: Dict[str, Any] = {}
    if yaml_configs:
        for name, path in yaml_configs.items():
            if not path.exists():
                raise FileNotFoundError(f"Config file not found: {path}")
            with open(path) as f:
                yaml_data[name] = yaml.safe_load(f)

    # Create and return config (env vars take precedence)
    config = PrometheusConfig()
    return config


# Global config instance (lazy-loaded)
_config: Optional[PrometheusConfig] = None


def get_config() -> PrometheusConfig:
    """Get global configuration instance.
    
    Loads configuration on first call, returns cached instance on subsequent calls.
    
    Returns:
        Global PrometheusConfig instance
    """
    global _config
    if _config is None:
        # Try to load .env from project root
        env_file = Path(".env")
        _config = load_config(env_file=env_file if env_file.exists() else None)
    return _config
```

### 2.3 Create Unit Test `tests/unit/test_config.py`

```python
"""Tests for configuration management."""

import os
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from prometheus.core.config import PrometheusConfig, load_config


class TestPrometheusConfig:
    """Tests for PrometheusConfig."""

    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        config = PrometheusConfig()
        
        assert config.historical_db_host == "localhost"
        assert config.historical_db_port == 5432
        assert config.runtime_db_host == "localhost"
        assert config.log_level == "INFO"
        assert config.environment == "development"

    def test_env_var_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that environment variables override defaults."""
        monkeypatch.setenv("HISTORICAL_DB_HOST", "testhost")
        monkeypatch.setenv("HISTORICAL_DB_PORT", "5433")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        
        config = PrometheusConfig()
        
        assert config.historical_db_host == "testhost"
        assert config.historical_db_port == 5433
        assert config.log_level == "DEBUG"

    def test_database_properties(self) -> None:
        """Test database configuration properties."""
        config = PrometheusConfig()
        
        hist_db = config.historical_db
        assert hist_db.host == config.historical_db_host
        assert hist_db.port == config.historical_db_port
        assert hist_db.name == config.historical_db_name
        
        runtime_db = config.runtime_db
        assert runtime_db.host == config.runtime_db_host
        assert runtime_db.port == config.runtime_db_port


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_from_env_file(self) -> None:
        """Test loading configuration from .env file."""
        # Create temporary .env file
        with NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write("HISTORICAL_DB_HOST=envhost\n")
            f.write("RUNTIME_DB_PORT=5434\n")
            env_file = Path(f.name)
        
        try:
            config = load_config(env_file=env_file)
            assert config.historical_db_host == "envhost"
            assert config.runtime_db_port == 5434
        finally:
            env_file.unlink()

    def test_missing_env_file_raises(self) -> None:
        """Test that missing env file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError, match="Environment file not found"):
            load_config(env_file=Path("/nonexistent/.env"))
```

### 2.4 Run Tests

```bash
pytest tests/unit/test_config.py -v
mypy prometheus/core/config.py --strict
```

**✅ Checkpoint**: Configuration system working

---

## STEP 3: Core Infrastructure - Logging (30 minutes)

### 3.1 Create `prometheus/core/logging.py`

```python
"""Structured logging setup for Prometheus.

Provides consistent logging across all modules with JSON formatting for production.
"""

import logging
import logging.config
import sys
from pathlib import Path
from typing import Optional

from prometheus.core.config import PrometheusConfig


def setup_logging(config: Optional[PrometheusConfig] = None) -> None:
    """Set up structured logging.
    
    Args:
        config: PrometheusConfig instance (creates new one if None)
    """
    if config is None:
        from prometheus.core.config import get_config
        config = get_config()

    # Simple logging config (JSON formatting can be added later)
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(config.log_file),
        ]
    )

    # Set prometheus package logger level
    logger = logging.getLogger("prometheus")
    logger.setLevel(getattr(logging, config.log_level.upper()))


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a specific module.
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Configured logger instance
    """
    return logging.getLogger(f"prometheus.{name}")
```

### 3.2 Create Unit Test `tests/unit/test_logging.py`

```python
"""Tests for logging setup."""

import logging
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from prometheus.core.config import PrometheusConfig
from prometheus.core.logging import get_logger, setup_logging


class TestLogging:
    """Tests for logging functions."""

    def test_setup_logging_creates_log_file(self) -> None:
        """Test that setup_logging creates log file."""
        with TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            config = PrometheusConfig(log_file=str(log_file))
            
            setup_logging(config)
            
            logger = get_logger("test")
            logger.info("Test message")
            
            assert log_file.exists()
            content = log_file.read_text()
            assert "Test message" in content

    def test_get_logger_returns_correct_logger(self) -> None:
        """Test that get_logger returns properly namespaced logger."""
        logger = get_logger("core.test")
        assert logger.name == "prometheus.core.test"

    def test_log_level_from_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that log level is set from config."""
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        config = PrometheusConfig()
        
        setup_logging(config)
        
        logger = get_logger("test")
        assert logger.level == logging.DEBUG
```

### 3.3 Run Tests

```bash
pytest tests/unit/test_logging.py -v
mypy prometheus/core/logging.py --strict
```

**✅ Checkpoint**: Logging system working

---

## STEP 4: Core Infrastructure - IDs (30 minutes)

### 3.1 Create `prometheus/core/ids.py`

```python
"""ID generation utilities for Prometheus.

Provides consistent ID generation across the system.
"""

import uuid
from datetime import date
from typing import Optional


def generate_uuid() -> str:
    """Generate a UUID v4.
    
    Returns:
        UUID string in standard format (with hyphens)
    """
    return str(uuid.uuid4())


def generate_decision_id() -> str:
    """Generate a unique decision ID.
    
    Returns:
        UUID string for decision tracking
    """
    return generate_uuid()


def generate_context_id(
    as_of_date: date,
    portfolio_id: str,
    strategy_id: str,
) -> str:
    """Generate a context ID for grouping related decisions.
    
    Args:
        as_of_date: Date of the decision context
        portfolio_id: Portfolio identifier
        strategy_id: Strategy identifier
    
    Returns:
        Context ID string in format: {date}_{portfolio}_{strategy}
    """
    date_str = as_of_date.strftime("%Y%m%d")
    return f"{date_str}_{portfolio_id}_{strategy_id}"


def generate_run_id(prefix: Optional[str] = None) -> str:
    """Generate a run ID for backtest runs or similar.
    
    Args:
        prefix: Optional prefix for the run ID
    
    Returns:
        Run ID string (prefixed UUID if prefix provided)
    """
    run_uuid = generate_uuid()
    if prefix:
        return f"{prefix}_{run_uuid}"
    return run_uuid
```

### 3.2 Create Unit Test `tests/unit/test_ids.py`

```python
"""Tests for ID generation utilities."""

from datetime import date

import pytest

from prometheus.core.ids import (
    generate_context_id,
    generate_decision_id,
    generate_run_id,
    generate_uuid,
)


class TestIDGeneration:
    """Tests for ID generation functions."""

    def test_generate_uuid_format(self) -> None:
        """Test that generated UUIDs are valid format."""
        uuid_str = generate_uuid()
        
        # UUID v4 format: 8-4-4-4-12 hex digits
        parts = uuid_str.split("-")
        assert len(parts) == 5
        assert len(parts[0]) == 8
        assert len(parts[1]) == 4
        assert len(parts[4]) == 12

    def test_generate_uuid_unique(self) -> None:
        """Test that generated UUIDs are unique."""
        uuids = {generate_uuid() for _ in range(100)}
        assert len(uuids) == 100  # All unique

    def test_generate_decision_id(self) -> None:
        """Test decision ID generation."""
        decision_id = generate_decision_id()
        
        # Should be valid UUID format
        parts = decision_id.split("-")
        assert len(parts) == 5

    def test_generate_context_id_format(self) -> None:
        """Test context ID format."""
        context_id = generate_context_id(
            as_of_date=date(2024, 1, 15),
            portfolio_id="port1",
            strategy_id="strat1",
        )
        
        assert context_id == "20240115_port1_strat1"

    def test_generate_run_id_without_prefix(self) -> None:
        """Test run ID generation without prefix."""
        run_id = generate_run_id()
        
        # Should be valid UUID
        parts = run_id.split("-")
        assert len(parts) == 5

    def test_generate_run_id_with_prefix(self) -> None:
        """Test run ID generation with prefix."""
        run_id = generate_run_id(prefix="backtest")
        
        assert run_id.startswith("backtest_")
        # Rest should be UUID
        uuid_part = run_id.split("_", 1)[1]
        parts = uuid_part.split("-")
        assert len(parts) == 5
```

### 3.3 Run Tests

```bash
pytest tests/unit/test_ids.py -v
mypy prometheus/core/ids.py --strict
```

**✅ Checkpoint**: ID generation working

---

## STEP 5: Database Infrastructure (2-3 hours)

### 5.1 Set Up PostgreSQL Databases

```bash
# Start PostgreSQL (if not running)
sudo systemctl start postgresql

# Create databases
sudo -u postgres psql << EOF
CREATE DATABASE prometheus_historical;
CREATE DATABASE prometheus_runtime;
CREATE USER prometheus WITH PASSWORD 'your_password_here';
GRANT ALL PRIVILEGES ON DATABASE prometheus_historical TO prometheus;
GRANT ALL PRIVILEGES ON DATABASE prometheus_runtime TO prometheus;
\q
EOF

# Update .env with your password
echo "HISTORICAL_DB_PASSWORD=your_password_here" >> .env
echo "RUNTIME_DB_PASSWORD=your_password_here" >> .env
```

### 5.2 Create `prometheus/core/database.py`

```python
"""Database connection management for Prometheus.

Provides connection pools for historical_db and runtime_db.
"""

from contextlib import contextmanager
from typing import Generator, Optional

import psycopg2
from psycopg2 import pool
from psycopg2.extensions import connection as Connection

from prometheus.core.config import DatabaseConfig, PrometheusConfig
from prometheus.core.logging import get_logger

logger = get_logger("core.database")


class DatabaseManager:
    """Manages database connection pools."""

    def __init__(self, config: PrometheusConfig) -> None:
        """Initialize database manager.
        
        Args:
            config: Prometheus configuration
        """
        self.config = config
        self._historical_pool: Optional[pool.SimpleConnectionPool] = None
        self._runtime_pool: Optional[pool.SimpleConnectionPool] = None
        logger.info("DatabaseManager initialized")

    def _create_connection_string(self, db_config: DatabaseConfig) -> str:
        """Create PostgreSQL connection string.
        
        Args:
            db_config: Database configuration
        
        Returns:
            Connection string for psycopg2
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
        pool_attr: str,
        db_config: DatabaseConfig,
    ) -> pool.SimpleConnectionPool:
        """Get or create a connection pool.
        
        Args:
            pool_attr: Attribute name for the pool (_historical_pool or _runtime_pool)
            db_config: Database configuration
        
        Returns:
            Connection pool
        """
        existing_pool = getattr(self, pool_attr)
        if existing_pool is not None:
            return existing_pool

        conn_string = self._create_connection_string(db_config)
        new_pool = pool.SimpleConnectionPool(
            minconn=1,
            maxconn=db_config.pool_size,
            dsn=conn_string,
        )
        setattr(self, pool_attr, new_pool)
        logger.info(f"Created connection pool for {db_config.name}")
        return new_pool

    @contextmanager
    def get_historical_connection(self) -> Generator[Connection, None, None]:
        """Get a connection to historical_db.
        
        Yields:
            Database connection (auto-returned to pool)
        """
        pool_obj = self._get_or_create_pool(
            "_historical_pool",
            self.config.historical_db,
        )
        conn = pool_obj.getconn()
        try:
            yield conn
        finally:
            pool_obj.putconn(conn)

    @contextmanager
    def get_runtime_connection(self) -> Generator[Connection, None, None]:
        """Get a connection to runtime_db.
        
        Yields:
            Database connection (auto-returned to pool)
        """
        pool_obj = self._get_or_create_pool(
            "_runtime_pool",
            self.config.runtime_db,
        )
        conn = pool_obj.getconn()
        try:
            yield conn
        finally:
            pool_obj.putconn(conn)

    def close_all(self) -> None:
        """Close all connection pools."""
        if self._historical_pool is not None:
            self._historical_pool.closeall()
            logger.info("Closed historical_db connection pool")
        if self._runtime_pool is not None:
            self._runtime_pool.closeall()
            logger.info("Closed runtime_db connection pool")


# Global database manager (lazy-loaded)
_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """Get global database manager instance.
    
    Returns:
        Global DatabaseManager instance
    """
    global _db_manager
    if _db_manager is None:
        from prometheus.core.config import get_config
        _db_manager = DatabaseManager(get_config())
    return _db_manager
```

### 5.3 Set Up Alembic

```bash
# Initialize Alembic
alembic init migrations

# Update alembic.ini (connection string will come from env)
cat > alembic.ini << 'EOF'
[alembic]
script_location = migrations
prepend_sys_path = .
version_path_separator = os

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
EOF
```

### 5.4 Update `migrations/env.py`

```python
"""Alembic environment configuration."""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

# Import your models here when they exist
# from prometheus.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None  # Will be Base.metadata when models exist


def get_url() -> str:
    """Get database URL from environment."""
    # Check which database we're targeting
    db_name = os.environ.get("ALEMBIC_DB", "runtime")
    
    if db_name == "historical":
        host = os.environ.get("HISTORICAL_DB_HOST", "localhost")
        port = os.environ.get("HISTORICAL_DB_PORT", "5432")
        name = os.environ.get("HISTORICAL_DB_NAME", "prometheus_historical")
        user = os.environ.get("HISTORICAL_DB_USER", "prometheus")
        password = os.environ.get("HISTORICAL_DB_PASSWORD", "")
    else:  # runtime (default)
        host = os.environ.get("RUNTIME_DB_HOST", "localhost")
        port = os.environ.get("RUNTIME_DB_PORT", "5432")
        name = os.environ.get("RUNTIME_DB_NAME", "prometheus_runtime")
        user = os.environ.get("RUNTIME_DB_USER", "prometheus")
        password = os.environ.get("RUNTIME_DB_PASSWORD", "")
    
    return f"postgresql://{user}:{password}@{host}:{port}/{name}"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = create_engine(get_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### 5.5 Create First Migration `migrations/versions/0001_core_entities.py`

```bash
# Generate migration file
alembic revision -m "core entities"

# This will create migrations/versions/{hash}_core_entities.py
# Edit that file with the following content:
```

```python
"""core entities

Revision ID: 0001
Create Date: 2024-11-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create core entity tables."""
    # markets
    op.create_table(
        'markets',
        sa.Column('market_id', sa.String(50), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('region', sa.String(50), nullable=False),
        sa.Column('timezone', sa.String(50), nullable=False),
        sa.Column('calendar_spec', postgresql.JSONB, nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # issuers
    op.create_table(
        'issuers',
        sa.Column('issuer_id', sa.String(50), primary_key=True),
        sa.Column('issuer_type', sa.String(50), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('country', sa.String(50), nullable=True),
        sa.Column('sector', sa.String(100), nullable=True),
        sa.Column('industry', sa.String(100), nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # instruments
    op.create_table(
        'instruments',
        sa.Column('instrument_id', sa.String(50), primary_key=True),
        sa.Column('issuer_id', sa.String(50), sa.ForeignKey('issuers.issuer_id')),
        sa.Column('market_id', sa.String(50), sa.ForeignKey('markets.market_id')),
        sa.Column('asset_class', sa.String(50), nullable=False),
        sa.Column('symbol', sa.String(50), nullable=False),
        sa.Column('exchange', sa.String(50), nullable=True),
        sa.Column('currency', sa.String(10), nullable=False),
        sa.Column('multiplier', sa.Float, nullable=True),
        sa.Column('maturity_date', sa.Date, nullable=True),
        sa.Column('underlying_instrument_id', sa.String(50), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='ACTIVE'),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # portfolios
    op.create_table(
        'portfolios',
        sa.Column('portfolio_id', sa.String(50), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('base_currency', sa.String(10), nullable=False),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # strategies
    op.create_table(
        'strategies',
        sa.Column('strategy_id', sa.String(50), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create indexes
    op.create_index('idx_instruments_issuer', 'instruments', ['issuer_id'])
    op.create_index('idx_instruments_market', 'instruments', ['market_id'])
    op.create_index('idx_instruments_status', 'instruments', ['status'])


def downgrade() -> None:
    """Drop core entity tables."""
    op.drop_table('strategies')
    op.drop_table('portfolios')
    op.drop_table('instruments')
    op.drop_table('issuers')
    op.drop_table('markets')
```

### 5.6 Apply Migration

```bash
# Load environment
source .env

# Apply to runtime_db
ALEMBIC_DB=runtime alembic upgrade head

# Apply to historical_db (same schema for now)
ALEMBIC_DB=historical alembic upgrade head
```

### 5.7 Create Unit Test `tests/unit/test_database.py`

```python
"""Tests for database management."""

import pytest
from psycopg2.extensions import connection as Connection

from prometheus.core.config import PrometheusConfig
from prometheus.core.database import DatabaseManager


class TestDatabaseManager:
    """Tests for DatabaseManager."""

    def test_create_connection_string(self) -> None:
        """Test connection string creation."""
        config = PrometheusConfig(
            historical_db_host="testhost",
            historical_db_port=5433,
            historical_db_name="testdb",
            historical_db_user="testuser",
            historical_db_password="testpass",
        )
        
        db_manager = DatabaseManager(config)
        conn_string = db_manager._create_connection_string(config.historical_db)
        
        assert "host=testhost" in conn_string
        assert "port=5433" in conn_string
        assert "dbname=testdb" in conn_string
        assert "user=testuser" in conn_string
        assert "password=testpass" in conn_string

    @pytest.mark.integration
    def test_get_runtime_connection(self) -> None:
        """Test getting runtime database connection."""
        from prometheus.core.config import get_config
        
        config = get_config()
        db_manager = DatabaseManager(config)
        
        with db_manager.get_runtime_connection() as conn:
            assert isinstance(conn, Connection)
            
            # Test query
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1
            cursor.close()

    @pytest.mark.integration
    def test_get_historical_connection(self) -> None:
        """Test getting historical database connection."""
        from prometheus.core.config import get_config
        
        config = get_config()
        db_manager = DatabaseManager(config)
        
        with db_manager.get_historical_connection() as conn:
            assert isinstance(conn, Connection)
            
            # Test query
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            assert result[0] == 1
            cursor.close()
```

**✅ Checkpoint**: Database connections working, migrations applied

---

## STEP 6: Integration Test (1 hour)

### 6.1 Create `tests/integration/test_iter1_foundation.py`

```python
"""Integration test for Iteration 1 - Foundation & Database Core.

This test validates:
1. Configuration loads correctly
2. Database connections work
3. Can insert and query core entities
4. Logging works correctly
"""

import logging
from datetime import datetime
from tempfile import TemporaryDirectory

import pytest

from prometheus.core.config import PrometheusConfig, load_config
from prometheus.core.database import DatabaseManager
from prometheus.core.ids import generate_uuid
from prometheus.core.logging import get_logger, setup_logging


@pytest.mark.integration
class TestIteration1Foundation:
    """Integration tests for Iteration 1."""

    def test_complete_foundation_workflow(self) -> None:
        """Test complete foundation workflow: config → db → logging → CRUD."""
        # Step 1: Load configuration
        config = PrometheusConfig()
        assert config.historical_db_host is not None
        assert config.runtime_db_host is not None
        
        # Step 2: Set up logging
        with TemporaryDirectory() as tmpdir:
            config.log_file = f"{tmpdir}/test.log"
            setup_logging(config)
            logger = get_logger("test.integration")
            
            logger.info("Starting foundation integration test")
            
            # Step 3: Initialize database manager
            db_manager = DatabaseManager(config)
            
            # Step 4: Test runtime_db operations
            with db_manager.get_runtime_connection() as conn:
                cursor = conn.cursor()
                
                # Insert test market
                market_id = f"TEST_MARKET_{generate_uuid()[:8]}"
                cursor.execute(
                    """
                    INSERT INTO markets (market_id, name, region, timezone)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (market_id, "Test Market", "US", "America/New_York")
                )
                
                # Insert test issuer
                issuer_id = f"TEST_ISSUER_{generate_uuid()[:8]}"
                cursor.execute(
                    """
                    INSERT INTO issuers (issuer_id, issuer_type, name)
                    VALUES (%s, %s, %s)
                    """,
                    (issuer_id, "CORPORATION", "Test Corp")
                )
                
                # Insert test instrument
                instrument_id = f"TEST_INST_{generate_uuid()[:8]}"
                cursor.execute(
                    """
                    INSERT INTO instruments 
                    (instrument_id, issuer_id, market_id, asset_class, symbol, currency)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (instrument_id, issuer_id, market_id, "EQUITY", "TEST", "USD")
                )
                
                # Insert test portfolio
                portfolio_id = f"TEST_PORT_{generate_uuid()[:8]}"
                cursor.execute(
                    """
                    INSERT INTO portfolios (portfolio_id, name, base_currency)
                    VALUES (%s, %s, %s)
                    """,
                    (portfolio_id, "Test Portfolio", "USD")
                )
                
                # Insert test strategy
                strategy_id = f"TEST_STRAT_{generate_uuid()[:8]}"
                cursor.execute(
                    """
                    INSERT INTO strategies (strategy_id, name)
                    VALUES (%s, %s)
                    """,
                    (strategy_id, "Test Strategy")
                )
                
                conn.commit()
                
                # Step 5: Query everything back
                cursor.execute("SELECT market_id, name FROM markets WHERE market_id = %s", (market_id,))
                market_result = cursor.fetchone()
                assert market_result is not None
                assert market_result[0] == market_id
                assert market_result[1] == "Test Market"
                
                cursor.execute("SELECT issuer_id, name FROM issuers WHERE issuer_id = %s", (issuer_id,))
                issuer_result = cursor.fetchone()
                assert issuer_result is not None
                assert issuer_result[1] == "Test Corp"
                
                cursor.execute("SELECT instrument_id, symbol FROM instruments WHERE instrument_id = %s", (instrument_id,))
                instrument_result = cursor.fetchone()
                assert instrument_result is not None
                assert instrument_result[1] == "TEST"
                
                cursor.execute("SELECT portfolio_id, name FROM portfolios WHERE portfolio_id = %s", (portfolio_id,))
                portfolio_result = cursor.fetchone()
                assert portfolio_result is not None
                assert portfolio_result[1] == "Test Portfolio"
                
                cursor.execute("SELECT strategy_id, name FROM strategies WHERE strategy_id = %s", (strategy_id,))
                strategy_result = cursor.fetchone()
                assert strategy_result is not None
                assert strategy_result[1] == "Test Strategy"
                
                # Step 6: Rollback (cleanup)
                conn.rollback()
                
                # Verify rollback worked
                cursor.execute("SELECT COUNT(*) FROM markets WHERE market_id = %s", (market_id,))
                count = cursor.fetchone()[0]
                assert count == 0
                
                cursor.close()
            
            logger.info("Foundation integration test completed successfully")
            
            # Step 7: Verify logging worked
            with open(config.log_file) as f:
                log_content = f.read()
                assert "Starting foundation integration test" in log_content
                assert "completed successfully" in log_content
            
            # Close database connections
            db_manager.close_all()
```

### 6.2 Run Integration Test

```bash
# Run integration test
pytest tests/integration/test_iter1_foundation.py -v -s

# Run all tests
pytest -v

# Check coverage
pytest --cov=prometheus --cov-report=term-missing
```

**✅ Checkpoint**: All tests passing

---

## STEP 7: Validation & Cleanup (30 minutes)

### 7.1 Run Full Validation Suite

```bash
# Type checking
mypy prometheus/core --strict

# Linting
ruff check prometheus/

# All tests
pytest -v

# Coverage
pytest --cov=prometheus --cov-report=html
open htmlcov/index.html  # View coverage report
```

### 7.2 Create Dev Workflow Doc

```bash
cat > dev_workflows/ITER1_FOUNDATION.md << 'EOF'
# Iteration 1: Foundation & Database Core - Developer Guide

## What Was Built

- Project structure and packaging
- Configuration system (YAML + env vars)
- Structured logging
- ID generation utilities
- Database connection management
- Core entity tables (markets, issuers, instruments, portfolios, strategies)

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Set up environment
cp .env.example .env
# Edit .env with database credentials

# Run migrations
ALEMBIC_DB=runtime alembic upgrade head
ALEMBIC_DB=historical alembic upgrade head

# Run tests
pytest
```

## Usage Examples

### Configuration

```python
from prometheus.core.config import get_config

config = get_config()
print(config.historical_db_host)
print(config.log_level)
```

### Database

```python
from prometheus.core.database import get_db_manager

db = get_db_manager()

with db.get_runtime_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM markets LIMIT 10")
    results = cursor.fetchall()
    cursor.close()
```

### Logging

```python
from prometheus.core.logging import setup_logging, get_logger

setup_logging()
logger = get_logger("my_module")

logger.info("Something happened")
logger.error("Something went wrong")
```

### IDs

```python
from prometheus.core.ids import generate_uuid, generate_context_id
from datetime import date

uuid = generate_uuid()
context_id = generate_context_id(date.today(), "port1", "strat1")
```

## Testing

```bash
# Unit tests only
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v -m integration

# Specific test
pytest tests/unit/test_config.py::TestPrometheusConfig::test_default_values -v
```

## Database Operations

```bash
# Create new migration
alembic revision -m "description"

# Apply migrations
ALEMBIC_DB=runtime alembic upgrade head

# Rollback
ALEMBIC_DB=runtime alembic downgrade -1

# Check status
ALEMBIC_DB=runtime alembic current
```
EOF
```

### 7.3 Update Project README

```bash
# Update README with iteration status
sed -i 's/in progress/✅ COMPLETE/' README.md
```

### 7.4 Commit and Tag

```bash
# Stage all changes
git add .

# Commit
git commit -m "Iteration 1: Foundation & Database Core

- Project structure and packaging setup
- Configuration system (Pydantic + YAML + env vars)
- Structured logging with file and console handlers
- ID generation utilities (UUID, context_id, run_id)
- Database connection management (pooling for historical_db + runtime_db)
- Alembic migrations setup
- Core entity tables (5 tables: markets, issuers, instruments, portfolios, strategies)
- Comprehensive unit and integration tests
- Developer workflow documentation

All tests passing. Type checking clean. Coverage > 80%.

Exit Criteria Met:
✅ Can insert and query core entities
✅ Configuration loads from env vars
✅ Database connections pool correctly
✅ Logging outputs to file and console
✅ All code passes mypy --strict
✅ All tests pass"

# Merge to main
git checkout main
git merge iter-1-foundation

# Tag
git tag v0.1.0 -m "Iteration 1: Foundation & Database Core"

# Push
git push origin main
git push origin v0.1.0
```

---

## EXIT CRITERIA ✅

Iteration 1 is complete when ALL of the following are true:

- [x] Project structure created with all packages
- [x] `pyproject.toml` configured with dependencies
- [x] Configuration system loads from YAML + env vars
- [x] Logging outputs to console and file
- [x] ID generation functions work
- [x] Database connections pool correctly
- [x] Can connect to both historical_db and runtime_db
- [x] Core entity tables created (5 tables)
- [x] Alembic migrations work
- [x] Can INSERT into all 5 core tables
- [x] Can SELECT from all 5 core tables
- [x] All unit tests pass (config, logging, ids, database)
- [x] Integration test passes (full workflow)
- [x] `mypy prometheus/core --strict` passes with no errors
- [x] Code coverage ≥ 80% for new code
- [x] Dev workflow documentation created

---

## TROUBLESHOOTING

### Database Connection Issues

```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Check databases exist
psql -U prometheus -l

# Test connection
psql -U prometheus -d prometheus_runtime -c "SELECT 1;"

# Check .env file is loaded
python -c "from prometheus.core.config import get_config; print(get_config().historical_db_host)"
```

### Migration Issues

```bash
# Check current version
ALEMBIC_DB=runtime alembic current

# Show history
ALEMBIC_DB=runtime alembic history

# Force downgrade and re-upgrade
ALEMBIC_DB=runtime alembic downgrade base
ALEMBIC_DB=runtime alembic upgrade head
```

### Test Failures

```bash
# Run with verbose output
pytest tests/integration/test_iter1_foundation.py -v -s

# Run specific test
pytest tests/unit/test_database.py::TestDatabaseManager::test_get_runtime_connection -v

# Skip integration tests if database not set up
pytest -v -m "not integration"
```

---

## NEXT ITERATION

When Iteration 1 is complete and all exit criteria are met, proceed to:

**ITERATION 2: Time & Calendar + Data Access Layer**

See the main iterative implementation plan for details.

---

**CONGRATULATIONS!** 🎉

You now have a solid foundation for Prometheus v2. All core infrastructure is in place and tested. You can build with confidence.
