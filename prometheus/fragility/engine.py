"""Prometheus v2 – Fragility Alpha Engine orchestration.

This module defines a small engine façade around a Fragility Alpha
model and :class:`FragilityStorage`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List

from prometheus.core.logging import get_logger

from .model_basic import FragilityAlphaModel
from .storage import FragilityStorage
from .types import FragilityMeasure, PositionTemplate


logger = get_logger(__name__)


@dataclass
class FragilityAlphaEngine:
    """Orchestrator for Fragility Alpha scoring and persistence."""

    model: FragilityAlphaModel
    storage: FragilityStorage

    def score_and_save(self, as_of_date: date, entity_type: str, entity_id: str) -> FragilityMeasure:
        """Score an entity, persist the measure, and return it."""

        measure = self.model.score_entity(as_of_date, entity_type, entity_id)
        self.storage.save_measure(measure)
        logger.info(
            "FragilityAlphaEngine.score_and_save: date=%s entity_type=%s entity_id=%s score=%.4f class=%s",
            as_of_date,
            entity_type,
            entity_id,
            measure.fragility_score,
            measure.class_label.value,
        )
        return measure

    def score_and_suggest(
        self,
        as_of_date: date,
        entity_type: str,
        entity_id: str,
    ) -> tuple[FragilityMeasure, List[PositionTemplate]]:
        """Score an entity, persist, and return measure plus templates."""

        measure = self.score_and_save(as_of_date, entity_type, entity_id)
        templates = self.model.suggest_positions(measure, as_of_date)
        return measure, templates

    def get_latest_measure(self, entity_type: str, entity_id: str) -> FragilityMeasure | None:
        """Return the latest fragility measure for an entity, if present."""

        return self.storage.get_latest_measure(entity_type, entity_id)

    def get_history(
        self,
        entity_type: str,
        entity_id: str,
        start_date: date,
        end_date: date,
    ) -> List[FragilityMeasure]:
        """Return fragility measure history for an entity between two dates."""

        return self.storage.get_history(entity_type, entity_id, start_date, end_date)
