"""
Prometheus v2: ID Generation Utilities

This module contains helper functions for generating unique identifiers
used throughout the system. Centralising ID generation ensures
consistency and makes it easier to change ID formats in future
iterations.

Key responsibilities:
- Generate UUID-based identifiers
- Provide human-readable context IDs for decision grouping
- Provide run IDs for backtests and experiments

External dependencies:
- uuid: Standard library UUID generation
- datetime: For date-based context IDs

Database tables accessed:
- None (pure utility functions)

Thread safety: Thread-safe (stateless functions)

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

import uuid
from datetime import date
from typing import Optional

# ============================================================================
# Public API
# ============================================================================


def generate_uuid() -> str:
    """Generate a random UUIDv4 string.

    Returns:
        A UUID string in standard 8-4-4-4-12 hexadecimal format.
    """

    return str(uuid.uuid4())


def generate_decision_id() -> str:
    """Generate a unique identifier for a decision.

    Returns:
        A UUIDv4 string suitable for use as a primary key in
        ``engine_decisions`` or related tables.
    """

    return generate_uuid()


def generate_context_id(as_of_date: date, portfolio_id: str, strategy_id: str) -> str:
    """Generate a human-readable context ID for grouping decisions.

    The context ID ties together a set of decisions made for a specific
    date, portfolio, and strategy. It is used as a stable grouping key
    across decision, execution, and outcome tables.

    Args:
        as_of_date: Date for which decisions are being made.
        portfolio_id: Identifier of the portfolio.
        strategy_id: Identifier of the strategy.

    Returns:
        A string of the form ``YYYYMMDD_portfolioId_strategyId``.
    """

    date_str = as_of_date.strftime("%Y%m%d")
    return f"{date_str}_{portfolio_id}_{strategy_id}"


def generate_run_id(prefix: Optional[str] = None) -> str:
    """Generate a unique run ID for backtests or experiments.

    Args:
        prefix: Optional prefix to prepend to the UUID (e.g. "backtest",
            "experiment"). If provided, the returned ID will be of the form
            ``prefix_uuid``.

    Returns:
        A unique run identifier string.
    """

    base_id = generate_uuid()
    if prefix:
        return f"{prefix}_{base_id}"
    return base_id
