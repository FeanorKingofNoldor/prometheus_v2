"""
Prometheus v2: Logging Setup

This module provides centralised logging configuration and helper
functions for obtaining namespaced loggers. It uses a simple configuration
for Iteration 1 and can be extended later to support JSON logging and
more complex routing.

Key responsibilities:
- Configure root logging handlers and formats
- Provide a helper to obtain module-specific loggers

External dependencies:
- logging: Python standard library logging framework

Database tables accessed:
- None (logging only)

Thread safety: Thread-safe (logging module is process-global and
thread-safe under normal usage)

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

import logging
import sys
from typing import Optional

from prometheus.core.config import PrometheusConfig, get_config

# ============================================================================
# Public API
# ============================================================================


def setup_logging(config: Optional[PrometheusConfig] = None) -> None:
    """Configure application-wide logging.

    This function initialises the root logger and the ``prometheus``
    namespace logger. It is idempotent: calling it multiple times will not
    attach duplicate handlers.

    For Iteration 1 we use a simple text formatter and both console and
    file handlers. In later iterations this can be extended to support
    structured JSON logging and log routing based on configuration.

    Args:
        config: Optional configuration object. If omitted, the global
            configuration will be loaded via :func:`get_config`.
    """

    if config is None:
        config = get_config()

    root_logger = logging.getLogger()

    # Avoid attaching duplicate handlers if setup_logging is called again.
    if root_logger.handlers:
        return

    log_level = getattr(logging, config.log_level.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(config.log_file)
    file_handler.setFormatter(formatter)

    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Configure the prometheus namespace logger explicitly
    prometheus_logger = logging.getLogger("prometheus")
    prometheus_logger.setLevel(log_level)


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger for the given module.

    Args:
        name: Module-level ``__name__`` or any descriptive logger name.

    Returns:
        A :class:`logging.Logger` instance under the ``prometheus``
        namespace.
    """

    # Ensure logging is configured at least once before returning a logger.
    setup_logging()
    return logging.getLogger(f"prometheus.{name}")


# TODO(prometheus, 2025-11-24): Integrate YAML-based logging configuration
# Once the system grows, we may want to support loading a full logging
# configuration dictionary from configs/core/base.yaml and applying it via
# logging.config.dictConfig. For Iteration 1 a simple formatter is
# sufficient.
