"""Prometheus v2 – Regime state-change forecaster.

This module provides a thin, data-driven forecaster for *regime
state-change risk* based on the empirical transition matrix stored in the
runtime database.

The initial v1 implementation focuses on region-level regime changes and
exposes a small, explicit interface that other components (Universe,
Meta/Kronos, lambda experiments) can query to obtain probabilities of
regime changes over a given horizon.

Design notes
-----------

- We model regimes as a time-homogeneous Markov chain over
  :class:`prometheus.regime.types.RegimeLabel`.
- Transition probabilities are read from
  :meth:`prometheus.regime.storage.RegimeStorage.get_transition_matrix`.
- This module is intended to be wired into state-aware components such
  as :class:`prometheus.universe.engine.BasicUniverseModel` via the
  ``regime_forecaster`` hook, and into Meta/Kronos evaluation, once
  regime history is populated for the relevant regions.
- Given the *current* regime label for a region and a horizon ``H``
  (measured in discrete steps), we compute ``P^H`` where ``P`` is the
  one-step transition matrix and return:

  - The full probability distribution over labels at horizon ``H``.
  - The probability of *any* regime change.
  - The probability of moving into stressed regimes (CRISIS or RISK_OFF).
  - A simple ``risk_score`` derived from those probabilities.

Later iterations may:

- Condition transition matrices on time or additional covariates.
- Add an explicit STAB-driven instability forecaster.
- Provide rolling / expanding-window estimates for backtests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping

import numpy as np

from prometheus.core.logging import get_logger
from prometheus.regime.storage import RegimeStorage
from prometheus.regime.types import RegimeLabel, RegimeState


logger = get_logger(__name__)


@dataclass(frozen=True)
class RegimeChangeRisk:
    """Summary of regime state-change risk for a region.

    Attributes:
        as_of_date: Date of the latest observed regime state for the
            region (i.e. the conditioning point for the forecast).
        region: Region identifier (e.g. "GLOBAL", "US").
        current_regime: Current regime label at ``as_of_date``.
        horizon_steps: Forecast horizon in discrete Markov steps
            (typically interpreted as trading days).
        p_change_any: Probability that the regime will *not* remain in
            ``current_regime`` after ``horizon_steps``.
        p_to_crisis_or_risk_off: Probability of being in CRISIS or
            RISK_OFF after ``horizon_steps``.
        p_to_carry: Probability of being in CARRY after
            ``horizon_steps``.
        distribution: Full probability distribution over regime labels
            at the horizon.
        risk_score: Convenience scalar risk score in [0, 1], currently
            equal to ``p_to_crisis_or_risk_off`` and suitable for use as
            a multiplicative risk modifier.
    """

    as_of_date: "date"
    region: str
    current_regime: RegimeLabel
    horizon_steps: int
    p_change_any: float
    p_to_crisis_or_risk_off: float
    p_to_carry: float
    distribution: Dict[RegimeLabel, float]
    risk_score: float


@dataclass
class RegimeStateChangeForecaster:
    """Markov-chain based forecaster for regime state-change risk.

    This forecaster is intentionally simple and relies entirely on
    :class:`RegimeStorage` for persistence and empirical transition
    probabilities. It makes the following modelling assumptions:

    - Transition probabilities are time-homogeneous for a region.
    - The latest stored regime for the region is the current state.
    - Missing transition rows fall back to an identity row ("no change").

    The API is deliberately small so that we can later swap in a more
    sophisticated forecaster (e.g. time-varying transitions or
    feature-conditioned models) without touching downstream code.
    """

    storage: RegimeStorage

    def forecast(self, region: str = "GLOBAL", horizon_steps: int = 1) -> RegimeChangeRisk | None:
        """Forecast regime change risk for ``region`` over ``horizon_steps``.

        Returns ``None`` if there is no stored regime state for the
        region. In that case, callers should fall back to neutral
        assumptions.
        """

        if horizon_steps <= 0:
            raise ValueError("horizon_steps must be a positive integer")

        current: RegimeState | None = self.storage.get_latest_regime(region)
        if current is None:
            logger.warning("RegimeStateChangeForecaster: no regime state found for region=%s", region)
            return None

        matrix_dict = self.storage.get_transition_matrix(region)
        P, index_by_label = _build_transition_matrix(matrix_dict)

        # Multi-step transition matrix via matrix power.
        try:
            P_h = np.linalg.matrix_power(P, horizon_steps)
        except ValueError as exc:  # pragma: no cover - defensive
            raise RuntimeError("Failed to compute matrix power for regime transitions") from exc

        labels = list(index_by_label.keys())
        current_idx = index_by_label[current.regime_label]
        row = P_h[current_idx, :]

        # Build distribution over labels at the horizon.
        distribution: Dict[RegimeLabel, float] = {
            label: float(row[index_by_label[label]]) for label in labels
        }

        p_stay = distribution.get(current.regime_label, 0.0)
        p_change_any = float(max(0.0, min(1.0, 1.0 - p_stay)))

        p_crisis = distribution.get(RegimeLabel.CRISIS, 0.0)
        p_risk_off = distribution.get(RegimeLabel.RISK_OFF, 0.0)
        p_carry = distribution.get(RegimeLabel.CARRY, 0.0)

        p_to_crisis_or_risk_off = float(max(0.0, min(1.0, p_crisis + p_risk_off)))

        risk_score = p_to_crisis_or_risk_off

        return RegimeChangeRisk(
            as_of_date=current.as_of_date,
            region=current.region,
            current_regime=current.regime_label,
            horizon_steps=horizon_steps,
            p_change_any=p_change_any,
            p_to_crisis_or_risk_off=p_to_crisis_or_risk_off,
            p_to_carry=float(max(0.0, min(1.0, p_carry))),
            distribution=distribution,
            risk_score=risk_score,
        )


def _build_transition_matrix(
    matrix_dict: Mapping[str, Mapping[str, float]],
) -> tuple[np.ndarray, Dict[RegimeLabel, int]]:
    """Convert a nested mapping into a row-stochastic transition matrix.

    The returned matrix ``P`` has shape ``(n_labels, n_labels)`` where
    labels are ordered according to ``list(RegimeLabel)``. Any labels
    missing from ``matrix_dict`` receive an identity row (no-change).
    """

    labels = list(RegimeLabel)
    n = len(labels)
    index_by_label: Dict[RegimeLabel, int] = {label: i for i, label in enumerate(labels)}

    P = np.zeros((n, n), dtype=float)

    # Fill rows from the nested dict.
    for from_label_str, to_mapping in matrix_dict.items():
        try:
            from_label = RegimeLabel(from_label_str)
        except ValueError:
            logger.warning("Unknown from_regime_label in transition matrix: %s", from_label_str)
            continue

        i = index_by_label[from_label]
        for to_label_str, prob in to_mapping.items():
            try:
                to_label = RegimeLabel(to_label_str)
            except ValueError:
                logger.warning("Unknown to_regime_label in transition matrix: %s", to_label_str)
                continue
            j = index_by_label[to_label]
            P[i, j] = float(prob)

    # Ensure rows are valid probability vectors. For any row that sums to
    # zero (no data), fall back to an identity row.
    row_sums = P.sum(axis=1, keepdims=True)
    zero_mask = row_sums.squeeze() <= 0.0

    if np.any(zero_mask):
        P[zero_mask, :] = 0.0
        for idx in np.where(zero_mask)[0]:
            P[idx, idx] = 1.0
        row_sums = P.sum(axis=1, keepdims=True)

    P /= row_sums

    return P, index_by_label
