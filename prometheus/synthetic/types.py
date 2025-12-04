"""Prometheus v2 – Synthetic Scenario Engine types.

This module defines request/response types used by the Synthetic
Scenario Engine for generating and managing synthetic scenario sets.
The shapes are aligned with the 170_synthetic_scenarios specification
but intentionally minimal for the first implementation iteration.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ScenarioRequest:
    """Request describing a scenario set to be generated.

    Attributes:
        name: Human-readable name of the scenario set.
        description: Longer free-form description of purpose and
            construction.
        category: Scenario category, e.g. "HISTORICAL" or "BOOTSTRAP".
        horizon_days: Number of days in each scenario path (H).
        num_paths: Number of distinct paths to generate.
        markets: Market identifiers (e.g. ["US_EQ"]) used to resolve the
            base universe of instruments.
        base_date_start: Optional start date for the historical window
            used as the sampling base.
        base_date_end: Optional end date for the historical window used
            as the sampling base.
        regime_filter: Optional regime labels to condition sampling on;
            unused in the first iteration but reserved for future
            extensions.
        universe_filter: Optional free-form filter description (e.g.
            sector/asset-class constraints).
        generator_spec: Additional generator parameters (e.g. block
            length for bootstraps); for simple historical windows this
            can remain empty.
    """

    name: str
    description: str
    category: str
    horizon_days: int
    num_paths: int
    markets: List[str]
    base_date_start: Optional[date] = None
    base_date_end: Optional[date] = None
    regime_filter: Optional[List[str]] = None
    universe_filter: Optional[Dict[str, object]] = None
    generator_spec: Optional[Dict[str, object]] = None


@dataclass(frozen=True)
class ScenarioSetRef:
    """Lightweight reference to a stored scenario set."""

    scenario_set_id: str
    name: str
    category: str
    horizon_days: int
    num_paths: int
