"""Prometheus v2 – Meta-Orchestrator (Kronos) package.

This package contains the minimal Meta-Orchestrator implementation used
for evaluating and selecting sleeves based on backtest results.
"""

from __future__ import annotations

from prometheus.meta.types import EngineDecision, DecisionOutcome, BacktestRunRecord, SleeveEvaluation
from prometheus.meta.storage import MetaStorage
from prometheus.meta.engine import MetaOrchestrator

__all__ = [
    "EngineDecision",
    "DecisionOutcome",
    "BacktestRunRecord",
    "SleeveEvaluation",
    "MetaStorage",
    "MetaOrchestrator",
]