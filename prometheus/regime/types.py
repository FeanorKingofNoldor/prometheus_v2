"""Prometheus v2 – Regime Engine Types.

This module defines core data structures and enums used by the simplified
Regime Engine in Iteration 4.

Key responsibilities:
- Define the canonical representation of a regime state.
- Provide a small, explicit set of regime labels for the rule-based v1
  engine.

External dependencies:
- numpy: Used only for type annotations of the optional embedding.

Database tables accessed:
- None directly. Regime states are persisted via
  :mod:`prometheus.regime.storage`.

Thread safety: Dataclasses are immutable value objects when used as
such; this module itself is stateless.

Author: Prometheus Team
Created: 2025-11-24
Last Modified: 2025-11-24
Status: Development
Version: v0.4.0
"""

from __future__ import annotations

# ============================================================================
# Imports
# ============================================================================

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any, Dict, Mapping, Optional

import numpy as np
from numpy.typing import NDArray

from prometheus.core.types import MetadataDict

# ============================================================================
# Regime labels
# ============================================================================


class RegimeLabel(str, Enum):
    """Simplified regime labels for Iteration 4.

    These labels implement the rule-based behaviour described in the
    implementation plan:

    - ``CRISIS`` – very high volatility (e.g. VIX > 30).
    - ``RISK_OFF`` – stressed credit (e.g. HY OAS > 600 bps) but not full
      crisis.
    - ``CARRY`` – calm / supportive conditions (low vol, tight spreads).
    - ``NEUTRAL`` – anything in-between.

    Later iterations may expand this enum or map to more granular
    labels such as ``CALM_CARRY`` or ``RISK_OFF_CRISIS`` as per the
    full Regime Engine specification.
    """

    CRISIS = "CRISIS"
    RISK_OFF = "RISK_OFF"
    CARRY = "CARRY"
    NEUTRAL = "NEUTRAL"


# ============================================================================
# Core dataclasses
# ============================================================================


@dataclass(frozen=True)
class RegimeState:
    """Represents the inferred regime for a given region and date.

    Attributes:
        as_of_date: Date for which the regime was inferred.
        region: Region or market identifier (e.g. "GLOBAL", "US", "EU").
        regime_label: Simplified regime label.
        confidence: Confidence score in the range [0.0, 1.0].
        regime_embedding: Optional numeric embedding vector in R^d.
        metadata: Optional structured metadata with diagnostics and
            driver indicators (e.g. VIX, HY OAS levels).
    """

    as_of_date: date
    region: str
    regime_label: RegimeLabel
    confidence: float
    regime_embedding: Optional[NDArray[np.float_]] = None
    metadata: MetadataDict | None = None


@dataclass(frozen=True)
class RegimeIndicators:
    """Simple container for indicators driving the rule-based engine.

    Attributes:
        vix_level: Implied volatility proxy (e.g. VIX level).
        hy_oas_bps: High-yield option-adjusted spread in basis points.
    """

    vix_level: float
    hy_oas_bps: float


IndicatorMapping = Mapping[str, Any]
