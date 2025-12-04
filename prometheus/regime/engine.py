"""Prometheus v2 – Regime Engine infrastructure.

This module provides orchestration and persistence infrastructure for the
Regime Engine without hard-coding any specific regime logic. The actual
classification logic is supplied via the :class:`RegimeModel` protocol.

Responsibilities:
- Define :class:`RegimeModel`, which maps (as_of_date, region) to a
  :class:`RegimeState`.
- Provide :class:`RegimeEngine` that:
  - delegates classification to a RegimeModel implementation,
  - persists results via :class:`RegimeStorage`,
  - records regime transitions when labels change over time.

Concrete RegimeModel implementations are expected to use the encoder
layer (numeric, text, joint) and historical data as specified in the
Regime Engine spec; this module does not implement any such logic
itself.
"""

from __future__ import annotations

# ============================================================================
# Imports
# ============================================================================

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from prometheus.core.logging import get_logger
from prometheus.regime.storage import RegimeStorage
from prometheus.regime.types import RegimeState

logger = get_logger(__name__)


# ============================================================================
# Model protocol
# ============================================================================


class RegimeModel(Protocol):
    """Protocol for regime models used by :class:`RegimeEngine`.

    Implementations should encapsulate all regime classification logic,
    typically using numeric/text/joint embeddings and historical data as
    inputs. Concrete implementations may use rule-based logic, machine
    learning models, or hybrid approaches.
    
    Example:
        >>> class MyRegimeModel:
        ...     def classify(self, as_of_date, region):
        ...         # Custom regime logic here
        ...         return RegimeState(...)
    """

    def classify(self, as_of_date: date, region: str) -> RegimeState:  # pragma: no cover - interface
        """Infer the regime state for the given date and region.
        
        This method should analyze market conditions as of the specified
        date and return a complete RegimeState with label, confidence,
        and optional embedding.
        
        Args:
            as_of_date: Date for regime classification (no look-ahead)
            region: Region code (e.g., "US", "EU", "GLOBAL")
        
        Returns:
            RegimeState containing regime label, confidence score,
            and optional regime embedding vector
        
        Raises:
            NotImplementedError: If protocol method not implemented
            ValueError: If inputs are invalid or data insufficient
        """


# ============================================================================
# Engine
# ============================================================================


@dataclass
class RegimeEngine:
    """Orchestrator and persistence façade for the Regime Engine.

    This class is deliberately thin: it delegates regime classification
    to the supplied :class:`RegimeModel` and handles persistence and
    transition logging via :class:`RegimeStorage`. It provides the main
    entry point for regime inference and historical analysis.
    
    Attributes:
        model: RegimeModel implementation for classification logic
        storage: RegimeStorage instance for database persistence
    
    Example:
        >>> from prometheus.regime.model_numeric import NumericRegimeModel
        >>> model = NumericRegimeModel(...)
        >>> storage = RegimeStorage(db_manager)
        >>> engine = RegimeEngine(model=model, storage=storage)
        >>> regime = engine.get_regime(date(2024, 1, 15), "US")
    """

    model: RegimeModel
    storage: RegimeStorage

    # ========================================================================
    # Public API Methods
    # ========================================================================

    def get_regime(self, as_of_date: date, region: str = "GLOBAL") -> RegimeState:
        """Infer, persist, and return the regime for ``region`` on ``as_of_date``.

        This is the main entry point for regime classification. The method
        delegates classification to the model, persists the result, and
        records any regime transitions.
        
        Workflow:
        1. Delegate classification to :attr:`model`
        2. Fetch previous regime for transition detection
        3. Save the new regime state via :attr:`storage`
        4. Record transition if label changed
        5. Log regime information
        
        Args:
            as_of_date: Date for regime inference (no look-ahead bias)
            region: Region code, defaults to "GLOBAL"
        
        Returns:
            RegimeState object with label, confidence, and metadata
        
        Raises:
            ValueError: If model classification fails due to invalid inputs
            psycopg2.Error: If database operations fail
        
        Example:
            >>> regime = engine.get_regime(date(2024, 1, 15), "US")
            >>> print(f"{regime.regime_label.value}: {regime.confidence:.2f}")
            CARRY: 0.87
        """

        state = self.model.classify(as_of_date, region)

        previous = self.storage.get_latest_regime(region)
        self.storage.save_regime(state)
        if previous is not None and previous.regime_label != state.regime_label:
            self.storage.record_transition(previous, state)

        logger.info(
            "RegimeEngine.get_regime: date=%s region=%s label=%s confidence=%.3f",
            state.as_of_date,
            state.region,
            state.regime_label.value,
            state.confidence,
        )

        return state

    def get_latest_regime(self, region: str = "GLOBAL") -> RegimeState | None:
        """Return the most recent stored regime for ``region``, if any.
        
        Queries the database for the most recent regime classification
        without running the model. Useful for checking current state
        before deciding whether to reclassify.
        
        Args:
            region: Region code, defaults to "GLOBAL"
        
        Returns:
            RegimeState if any regime exists for the region, None otherwise
        
        Raises:
            psycopg2.Error: If database query fails
        
        Example:
            >>> latest = engine.get_latest_regime("US")
            >>> if latest:
            ...     print(f"Last regime: {latest.regime_label.value}")
        """

        return self.storage.get_latest_regime(region)

    def get_history(self, region: str, start_date: date, end_date: date) -> list[RegimeState]:
        """Return stored regime history for ``region`` within a date range.
        
        Retrieves historical regime classifications for analysis,
        backtesting, or visualization. Results are ordered chronologically.
        
        Args:
            region: Region code (e.g., "US", "EU", "GLOBAL")
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
        
        Returns:
            List of RegimeState objects ordered by date ascending
        
        Raises:
            psycopg2.Error: If database query fails
        
        Example:
            >>> history = engine.get_history(
            ...     region="US",
            ...     start_date=date(2024, 1, 1),
            ...     end_date=date(2024, 3, 31),
            ... )
            >>> for state in history:
            ...     print(state.as_of_date, state.regime_label.value)
        """

        return self.storage.get_history(region, start_date, end_date)

    def get_transition_matrix(self, region: str = "GLOBAL") -> dict[str, dict[str, float]]:
        """Return empirical regime transition probabilities for ``region``.

        Calculates and returns the regime transition probability matrix
        based on historical transitions. This is useful for understanding
        regime dynamics and modeling regime changes.
        
        The matrix format is: P(to_label | from_label) expressed as
        nested dict: from_label → to_label → probability.
        
        Args:
            region: Region code, defaults to "GLOBAL"
        
        Returns:
            Nested dict mapping from_label -> to_label -> probability.
            Empty dict if no transitions recorded for region.
        
        Raises:
            psycopg2.Error: If database query fails
        
        Example:
            >>> matrix = engine.get_transition_matrix("US")
            >>> carry_to_crisis = matrix.get("CARRY", {}).get("CRISIS", 0.0)
            >>> print(f"P(CRISIS | CARRY) = {carry_to_crisis:.2%}")
        """

        return self.storage.get_transition_matrix(region)
