"""Prometheus v2 – Synthetic Scenario Engine package.

This package exposes types and helpers for generating synthetic
stress scenarios used by Portfolio & Risk, Stability, and
Meta-Orchestrator components.
"""

from .types import ScenarioRequest, ScenarioSetRef
from .storage import ScenarioStorage, ScenarioPathRow
from .engine import SyntheticScenarioEngine