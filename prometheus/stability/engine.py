"""Prometheus v2 – Stability (STAB) Engine infrastructure.

This module defines the orchestration layer for the Stability / Soft
Target Engine (STAB). It mirrors the design of the Regime Engine:

- StabilityModel protocol encapsulates all scoring logic.
- StabilityEngine delegates to a StabilityModel and handles persistence
  via StabilityStorage.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from prometheus.core.logging import get_logger
from prometheus.stability.storage import StabilityStorage
from prometheus.stability.types import StabilityVector, SoftTargetState


logger = get_logger(__name__)

ENGINE_NAME: str = "STAB"


class StabilityModel(Protocol):
    """Protocol for stability models used by :class:`StabilityEngine`.

    Implementations should encapsulate all stability / soft-target
    scoring logic and may use any combination of numeric, text, and
    profile features as inputs. Models typically analyze volatility,
    correlation patterns, and fragility indicators.
    """

    def score(
        self,
        as_of_date: date,
        entity_type: str,
        entity_id: str,
    ) -> tuple[StabilityVector, SoftTargetState]:  # pragma: no cover - interface
        """Score an entity and return (stability_vector, soft_target_state).
        
        Args:
            as_of_date: Date for stability assessment (no look-ahead)
            entity_type: Type of entity (e.g., "issuer", "instrument")
            entity_id: Unique identifier for the entity
        
        Returns:
            Tuple of (StabilityVector, SoftTargetState) with detailed
            scores and classification
        
        Raises:
            NotImplementedError: If protocol method not implemented
            ValueError: If inputs invalid or data insufficient
        """


@dataclass
class StabilityEngine:
    """Orchestrator and persistence façade for the STAB engine.

    This class delegates scoring to a :class:`StabilityModel`
    implementation and persists the resulting stability vectors and
    soft-target classifications via :class:`StabilityStorage`.
    
    Attributes:
        model: StabilityModel implementation for scoring logic
        storage: StabilityStorage for database persistence
        engine_name: Engine identifier (defaults to "STAB")
    
    Example:
        >>> model = MyStabilityModel(...)
        >>> storage = StabilityStorage(db_manager)
        >>> engine = StabilityEngine(model=model, storage=storage)
        >>> state = engine.score_entity(
        ...     as_of_date=date(2024, 1, 15),
        ...     entity_type="issuer",
        ...     entity_id="AAPL",
        ... )
    """

    model: StabilityModel
    storage: StabilityStorage
    engine_name: str = ENGINE_NAME

    # ========================================================================
    # Public API Methods
    # ========================================================================

    def score_entity(
        self,
        as_of_date: date,
        entity_type: str,
        entity_id: str,
    ) -> SoftTargetState:
        """Score an entity and persist results.

        This is the main entry point for stability/fragility scoring.
        Delegates to the model for scoring, then persists both the
        detailed stability vector and the soft-target classification.
        
        Args:
            as_of_date: Date for stability assessment (no look-ahead)
            entity_type: Type of entity (e.g., "issuer", "instrument")
            entity_id: Unique identifier for the entity
        
        Returns:
            SoftTargetState with classification and component flags
        
        Raises:
            ValueError: If model scoring fails
            psycopg2.Error: If database persistence fails
        
        Example:
            >>> state = engine.score_entity(
            ...     as_of_date=date(2024, 1, 15),
            ...     entity_type="issuer",
            ...     entity_id="AAPL",
            ... )
            >>> print(f"{state.soft_target_class.value}: {state.soft_target_score:.2f}")
            GOOD: 0.85
        """

        vector, state = self.model.score(as_of_date, entity_type, entity_id)
        self.storage.save_stability_vector(vector)
        self.storage.save_soft_target(state)

        logger.info(
            "StabilityEngine.score_entity: date=%s type=%s id=%s class=%s score=%.2f",
            as_of_date,
            entity_type,
            entity_id,
            state.soft_target_class.value,
            state.soft_target_score,
        )

        return state

    def get_latest_state(self, entity_type: str, entity_id: str) -> SoftTargetState | None:
        """Return the most recent soft-target state for an entity, if any.
        
        Args:
            entity_type: Type of entity (e.g., "issuer", "instrument")
            entity_id: Unique identifier for the entity
        
        Returns:
            SoftTargetState if exists, None otherwise
        
        Raises:
            psycopg2.Error: If database query fails
        
        Example:
            >>> latest = engine.get_latest_state("issuer", "AAPL")
            >>> if latest:
            ...     print(f"Latest class: {latest.soft_target_class.value}")
        """

        return self.storage.get_latest_state(entity_type, entity_id)

    def get_history(
        self,
        entity_type: str,
        entity_id: str,
        start_date: date,
        end_date: date,
    ) -> list[SoftTargetState]:
        """Return soft-target history for an entity within a date range.
        
        Args:
            entity_type: Type of entity (e.g., "issuer", "instrument")
            entity_id: Unique identifier for the entity
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
        
        Returns:
            List of SoftTargetState objects ordered by date ascending
        
        Raises:
            psycopg2.Error: If database query fails
        
        Example:
            >>> history = engine.get_history(
            ...     entity_type="issuer",
            ...     entity_id="AAPL",
            ...     start_date=date(2024, 1, 1),
            ...     end_date=date(2024, 3, 31),
            ... )
            >>> for state in history:
            ...     print(state.as_of_date, state.soft_target_class.value)
        """

        return self.storage.get_history(entity_type, entity_id, start_date, end_date)
