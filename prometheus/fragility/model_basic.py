"""Prometheus v2 – Basic Fragility Alpha model.

This module implements a simple, rule-based Fragility Alpha model that
combines soft-target scores from the Stability Engine with optional
scenario-based losses from the Synthetic Scenario Engine to produce a
scalar fragility score and lightweight position templates.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Protocol

import numpy as np

from prometheus.core.database import DatabaseManager
from prometheus.core.logging import get_logger
from prometheus.stability.storage import StabilityStorage
from prometheus.stability.types import SoftTargetState

from .types import FragilityClass, FragilityMeasure, PositionTemplate


logger = get_logger(__name__)


class FragilityAlphaModel(Protocol):
    """Protocol for Fragility Alpha models."""

    def score_entity(self, as_of_date: date, entity_type: str, entity_id: str) -> FragilityMeasure:  # pragma: no cover - interface
        ...

    def suggest_positions(self, measure: FragilityMeasure, as_of_date: date) -> List[PositionTemplate]:  # pragma: no cover - interface
        ...


@dataclass
class BasicFragilityAlphaModel:
    """Rule-based Fragility Alpha model for instruments.

    This implementation currently supports only ``entity_type=
    "INSTRUMENT"`` and uses:

    - Soft-target scores from :class:`StabilityStorage`.
    - Optional scenario-based tail losses from a single
      ``scenario_set_id`` in ``scenario_paths``.
    """

    db_manager: DatabaseManager
    stability_storage: StabilityStorage
    scenario_set_id: str | None = None
    w_soft_target: float = 0.5
    w_scenario: float = 0.5

    def score_entity(self, as_of_date: date, entity_type: str, entity_id: str) -> FragilityMeasure:  # type: ignore[override]
        if entity_type != "INSTRUMENT":
            msg = f"BasicFragilityAlphaModel only supports entity_type='INSTRUMENT', got {entity_type!r}"
            raise NotImplementedError(msg)

        soft_state = self.stability_storage.get_latest_state(entity_type, entity_id)

        if soft_state is None or soft_state.as_of_date > as_of_date:
            # No prior stability information; treat as non-fragile.
            soft_state = SoftTargetState(
                as_of_date=as_of_date,
                entity_type=entity_type,
                entity_id=entity_id,
                soft_target_class=None,  # type: ignore[arg-type]
                soft_target_score=0.0,
                weak_profile=False,
                instability=0.0,
                high_fragility=0.0,
                complacent_pricing=0.0,
                metadata=None,
            )

        # Normalise soft-target score to [0, 1].
        score_soft = float(max(0.0, min(1.0, soft_state.soft_target_score / 100.0)))

        scenario_losses: Dict[str, float] = {}
        loss_metric = 0.0

        if self.scenario_set_id is not None:
            loss_metric = self._compute_scenario_loss(entity_id)
            scenario_losses[self.scenario_set_id] = loss_metric

        # Normalise scenario loss to [0, 1] using a simple reference scale.
        score_scenario = float(max(0.0, min(1.0, loss_metric / 0.5))) if loss_metric > 0.0 else 0.0

        # Combine into a single fragility score.
        total_weight = max(self.w_soft_target + self.w_scenario, 1e-6)
        fragility_score = (
            self.w_soft_target * score_soft + self.w_scenario * score_scenario
        ) / total_weight

        class_label = self._classify(fragility_score)

        components: Dict[str, float] = {
            "soft_target_score": float(soft_state.soft_target_score),
            "instability": float(soft_state.instability),
            "high_fragility": float(soft_state.high_fragility),
            "complacent_pricing": float(soft_state.complacent_pricing),
            "score_soft": score_soft,
            "score_scenario": score_scenario,
        }

        metadata: Dict[str, object] = {
            "class_label": class_label.value,
            "components": components,
        }

        measure = FragilityMeasure(
            entity_type=entity_type,
            entity_id=entity_id,
            as_of_date=as_of_date,
            fragility_score=float(fragility_score),
            class_label=class_label,
            scenario_losses=scenario_losses,
            components=components,
            metadata=metadata,
        )

        return measure

    def suggest_positions(self, measure: FragilityMeasure, as_of_date: date) -> List[PositionTemplate]:  # type: ignore[override]
        """Return simple short-equity templates for fragile entities.

        For v1 we propose a single equity short when the fragility class
        is SHORT_CANDIDATE or CRISIS, with a notional hint scaled by the
        fragility score.
        """

        if measure.class_label not in {FragilityClass.SHORT_CANDIDATE, FragilityClass.CRISIS}:
            return []

        # Cap suggested notional at 5% of capital and bottom out at a
        # small threshold to avoid microscopic suggestions.
        base = max(0.01, min(0.05, measure.fragility_score * 0.05))

        template = PositionTemplate(
            entity_id=measure.entity_id,
            instrument_id=measure.entity_id,
            as_of_date=as_of_date,
            direction="SHORT",
            kind="EQUITY",
            notional_hint=base,
            horizon_days=21,
            rationale={
                "fragility_score": measure.fragility_score,
                "class_label": measure.class_label.value,
            }
        )

        return [template]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_scenario_loss(self, instrument_id: str) -> float:
        """Compute a simple tail-loss metric from scenario_paths.

        The metric is defined as the maximum cumulative loss across all
        scenarios over the full horizon, using returns from
        ``scenario_paths`` for the configured ``scenario_set_id``.
        """

        if self.scenario_set_id is None:
            return 0.0

        sql = """
            SELECT scenario_id, horizon_index, return_value
            FROM scenario_paths
            WHERE scenario_set_id = %s
              AND instrument_id = %s
            ORDER BY scenario_id, horizon_index
        """

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (self.scenario_set_id, instrument_id))
                rows = cursor.fetchall()
            finally:
                cursor.close()

        if not rows:
            return 0.0

        # Group by scenario_id.
        losses_by_scenario: Dict[int, List[float]] = {}
        for scenario_id, horizon_index, ret in rows:
            if horizon_index == 0:
                continue
            losses_by_scenario.setdefault(int(scenario_id), []).append(float(ret))

        if not losses_by_scenario:
            return 0.0

        max_loss = 0.0
        for _, rets in losses_by_scenario.items():
            # Cumulative return over horizon.
            rets_arr = np.asarray(rets, dtype=float)
            cum_return = float(np.prod(1.0 + rets_arr) - 1.0)
            loss = max(0.0, -cum_return)
            if loss > max_loss:
                max_loss = loss

        return max_loss

    @staticmethod
    def _classify(score: float) -> FragilityClass:
        """Map scalar fragility score into a FragilityClass."""

        if score < 0.3:
            return FragilityClass.NONE
        if score < 0.5:
            return FragilityClass.WATCHLIST
        if score < 0.7:
            return FragilityClass.SHORT_CANDIDATE
        return FragilityClass.CRISIS
