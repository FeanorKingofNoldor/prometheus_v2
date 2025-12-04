"""Prometheus v2 – Regime Engine package.

This package contains the Regime Engine infrastructure and a numeric
embedding-based RegimeModel implementation as specified in the
architecture docs. Higher-level regime models (e.g. joint
text+numeric) can be added in later iterations.
"""

from prometheus.regime.types import RegimeLabel, RegimeState, RegimeIndicators
from prometheus.regime.storage import RegimeStorage
from prometheus.regime.engine import RegimeEngine, RegimeModel
from prometheus.regime.model_numeric import RegimePrototype, NumericRegimeModel
