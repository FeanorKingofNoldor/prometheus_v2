"""
Prometheus v2: Tests for Logging Setup

Test suite for ``prometheus.core.logging``. Covers:
- Basic logger configuration
- File and console handlers
- Namespaced logger retrieval
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import logging

import pytest

from prometheus.core.config import PrometheusConfig
from prometheus.core.logging import get_logger, setup_logging


class TestLogging:
    """Tests for logging configuration and helpers."""

    def test_setup_logging_creates_log_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """setup_logging should create a log file and write messages to it."""

        with TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"

            # Ensure we start from a clean logging configuration so
            # setup_logging attaches handlers for this test-specific file.
            root_logger = logging.getLogger()
            for handler in list(root_logger.handlers):
                root_logger.removeHandler(handler)

            # Configure log file via environment variable so that
            # PrometheusConfig picks it up correctly.
            monkeypatch.setenv("LOG_FILE", str(log_file))
            config = PrometheusConfig()

            setup_logging(config)
            logger = get_logger("test.logging")

            logger.info("Test log message")

            assert log_file.exists()
            content = log_file.read_text()
            assert "Test log message" in content

    def test_get_logger_returns_namespaced_logger(self) -> None:
        """get_logger should prefix loggers with the 'prometheus.' namespace."""

        logger = get_logger("core.test")
        assert logger.name == "prometheus.core.test"
        # Ensure logger has at least one handler attached via setup_logging
        assert logger.handlers or logging.getLogger().handlers
