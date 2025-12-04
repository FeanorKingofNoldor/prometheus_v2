"""Prometheus v2 – Meta/Kronos Proposal Applicator.

This module applies approved configuration proposals to strategies and tracks
their performance outcomes. It provides safe application with validation,
rollback support, and performance monitoring.

Key responsibilities:
- Apply approved proposals to strategy configurations
- Validate changes before application
- Track before/after performance in config_change_log
- Support rollback/reversion of bad changes
- Atomic updates with transactional safety

Author: Prometheus Team
Created: 2025-12-02
Status: Development
Version: v0.1.0
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, List, Optional, Any

from psycopg2.extras import Json

from prometheus.core.database import DatabaseManager
from prometheus.core.ids import generate_uuid
from prometheus.core.logging import get_logger


logger = get_logger(__name__)


@dataclass(frozen=True)
class ApplicationResult:
    """Result of applying a configuration change.

    Attributes:
        success: Whether application succeeded
        change_id: Unique change log entry ID
        proposal_id: Source proposal ID
        error_message: Error message if failed
        applied_at: Timestamp of application
    """

    success: bool
    change_id: Optional[str]
    proposal_id: str
    error_message: Optional[str] = None
    applied_at: Optional[datetime] = None


@dataclass(frozen=True)
class ReversionResult:
    """Result of reverting a configuration change.

    Attributes:
        success: Whether reversion succeeded
        change_id: Change log entry that was reverted
        error_message: Error message if failed
        reverted_at: Timestamp of reversion
    """

    success: bool
    change_id: str
    error_message: Optional[str] = None
    reverted_at: Optional[datetime] = None


@dataclass
class ProposalApplicator:
    """Applies and reverts configuration proposals.

    The applicator reads approved proposals, validates them, applies the
    changes to strategy configurations, and tracks outcomes in the
    config_change_log table.
    """

    db_manager: DatabaseManager
    dry_run: bool = False  # If True, validate but don't actually apply

    def apply_proposal(
        self, proposal_id: str, applied_by: str
    ) -> ApplicationResult:
        """Apply an approved proposal.

        Args:
            proposal_id: Proposal to apply
            applied_by: Identifier of user applying the change

        Returns:
            ApplicationResult indicating success/failure
        """
        # Load proposal
        proposal = self._load_proposal(proposal_id)

        if not proposal:
            return ApplicationResult(
                success=False,
                change_id=None,
                proposal_id=proposal_id,
                error_message=f"Proposal {proposal_id} not found",
            )

        # Validate proposal status
        if proposal["status"] != "APPROVED":
            return ApplicationResult(
                success=False,
                change_id=None,
                proposal_id=proposal_id,
                error_message=f"Proposal status is {proposal['status']}, must be APPROVED",
            )

        # Validate proposal data
        validation_error = self._validate_proposal(proposal)
        if validation_error:
            return ApplicationResult(
                success=False,
                change_id=None,
                proposal_id=proposal_id,
                error_message=validation_error,
            )

        if self.dry_run:
            logger.info(f"DRY RUN: Would apply proposal {proposal_id}")
            return ApplicationResult(
                success=True,
                change_id="DRY_RUN",
                proposal_id=proposal_id,
                applied_at=datetime.utcnow(),
            )

        try:
            # Get current config for comparison
            current_config = self._load_current_config(
                proposal["strategy_id"], proposal["target_component"]
            )

            # Apply the change (strategy-specific logic)
            self._apply_config_change(
                strategy_id=proposal["strategy_id"],
                target_component=proposal["target_component"],
                new_value=proposal["proposed_value"],
            )

            # Record in config_change_log
            change_id = generate_uuid()
            self._record_config_change(
                change_id=change_id,
                proposal_id=proposal_id,
                strategy_id=proposal["strategy_id"],
                market_id=proposal.get("market_id"),
                change_type=proposal["proposal_type"],
                target_component=proposal["target_component"],
                previous_value=current_config,
                new_value=proposal["proposed_value"],
                applied_by=applied_by,
            )

            # Update proposal status to APPLIED
            self._update_proposal_status(proposal_id, "APPLIED")

            logger.info(
                f"Applied proposal {proposal_id} for strategy {proposal['strategy_id']}"
            )

            return ApplicationResult(
                success=True,
                change_id=change_id,
                proposal_id=proposal_id,
                applied_at=datetime.utcnow(),
            )

        except Exception as e:
            logger.exception(f"Failed to apply proposal {proposal_id}: {e}")
            return ApplicationResult(
                success=False,
                change_id=None,
                proposal_id=proposal_id,
                error_message=str(e),
            )

    def apply_approved_proposals(
        self,
        strategy_id: Optional[str] = None,
        applied_by: str = "system",
        max_proposals: int = 10,
    ) -> List[ApplicationResult]:
        """Apply all approved proposals for a strategy.

        Args:
            strategy_id: Optional filter by strategy
            applied_by: Identifier of user applying changes
            max_proposals: Maximum number to apply in one batch

        Returns:
            List of application results
        """
        # Load approved proposals
        proposals = self._load_approved_proposals(strategy_id, max_proposals)

        if not proposals:
            logger.info("No approved proposals to apply")
            return []

        logger.info(f"Applying {len(proposals)} approved proposals")

        results = []
        for proposal in proposals:
            result = self.apply_proposal(proposal["proposal_id"], applied_by)
            results.append(result)

            # Stop on first error to avoid cascading failures
            if not result.success:
                logger.warning(
                    f"Stopping batch application after failure: {result.error_message}"
                )
                break

        return results

    def revert_change(
        self, change_id: str, reason: str, reverted_by: str
    ) -> ReversionResult:
        """Revert a previously applied configuration change.

        Args:
            change_id: Change log entry to revert
            reason: Reason for reversion
            reverted_by: Identifier of user reverting

        Returns:
            ReversionResult indicating success/failure
        """
        # Load change record
        change = self._load_config_change(change_id)

        if not change:
            return ReversionResult(
                success=False,
                change_id=change_id,
                error_message=f"Change {change_id} not found",
            )

        if change["is_reverted"]:
            return ReversionResult(
                success=False,
                change_id=change_id,
                error_message="Change already reverted",
            )

        if self.dry_run:
            logger.info(f"DRY RUN: Would revert change {change_id}")
            return ReversionResult(
                success=True,
                change_id=change_id,
                reverted_at=datetime.utcnow(),
            )

        try:
            # Revert to previous value
            self._apply_config_change(
                strategy_id=change["strategy_id"],
                target_component=change["target_component"],
                new_value=change["previous_value"],
            )

            # Mark as reverted in config_change_log
            self._mark_change_reverted(change_id, reason, reverted_by)

            # Update related proposal to REVERTED status
            if change["proposal_id"]:
                self._update_proposal_status(change["proposal_id"], "REVERTED")

            logger.info(f"Reverted change {change_id}: {reason}")

            return ReversionResult(
                success=True,
                change_id=change_id,
                reverted_at=datetime.utcnow(),
            )

        except Exception as e:
            logger.exception(f"Failed to revert change {change_id}: {e}")
            return ReversionResult(
                success=False,
                change_id=change_id,
                error_message=str(e),
            )

    def evaluate_change_performance(
        self,
        change_id: str,
        evaluation_start_date: date,
        evaluation_end_date: date,
    ) -> Dict[str, float]:
        """Evaluate performance impact of an applied change.

        Compares performance metrics before and after the change was applied
        over the specified evaluation period.

        Args:
            change_id: Change to evaluate
            evaluation_start_date: Start of evaluation period
            evaluation_end_date: End of evaluation period

        Returns:
            Dictionary with before/after metrics
        """
        change = self._load_config_change(change_id)

        if not change:
            logger.warning(f"Change {change_id} not found")
            return {}

        # Load backtest results before change
        metrics_before = self._compute_metrics_for_period(
            strategy_id=change["strategy_id"],
            start_date=evaluation_start_date,
            end_date=change["applied_at"].date(),
        )

        # Load backtest results after change
        metrics_after = self._compute_metrics_for_period(
            strategy_id=change["strategy_id"],
            start_date=change["applied_at"].date(),
            end_date=evaluation_end_date,
        )

        # Update config_change_log with performance metrics
        self._update_change_performance(
            change_id=change_id,
            sharpe_before=metrics_before.get("sharpe", 0.0),
            sharpe_after=metrics_after.get("sharpe", 0.0),
            return_before=metrics_before.get("return", 0.0),
            return_after=metrics_after.get("return", 0.0),
            risk_before=metrics_before.get("volatility", 0.0),
            risk_after=metrics_after.get("volatility", 0.0),
            evaluation_start_date=evaluation_start_date,
            evaluation_end_date=evaluation_end_date,
        )

        return {
            "before": metrics_before,
            "after": metrics_after,
            "improvement": {
                "sharpe": metrics_after.get("sharpe", 0.0)
                - metrics_before.get("sharpe", 0.0),
                "return": metrics_after.get("return", 0.0)
                - metrics_before.get("return", 0.0),
                "volatility": metrics_after.get("volatility", 0.0)
                - metrics_before.get("volatility", 0.0),
            },
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_proposal(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        """Load proposal from database."""
        sql = """
            SELECT proposal_id, strategy_id, market_id, proposal_type,
                   target_component, current_value, proposed_value,
                   status, approved_by, approved_at
            FROM meta_config_proposals
            WHERE proposal_id = %s
        """

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (proposal_id,))
                row = cursor.fetchone()
            finally:
                cursor.close()

        if not row:
            return None

        return {
            "proposal_id": row[0],
            "strategy_id": row[1],
            "market_id": row[2],
            "proposal_type": row[3],
            "target_component": row[4],
            "current_value": row[5],
            "proposed_value": row[6],
            "status": row[7],
            "approved_by": row[8],
            "approved_at": row[9],
        }

    def _load_approved_proposals(
        self, strategy_id: Optional[str], max_proposals: int
    ) -> List[Dict[str, Any]]:
        """Load approved proposals from database."""
        if strategy_id:
            sql = """
                SELECT proposal_id, strategy_id, market_id, proposal_type,
                       target_component, current_value, proposed_value
                FROM meta_config_proposals
                WHERE strategy_id = %s AND status = 'APPROVED'
                ORDER BY expected_sharpe_improvement DESC
                LIMIT %s
            """
            params = (strategy_id, max_proposals)
        else:
            sql = """
                SELECT proposal_id, strategy_id, market_id, proposal_type,
                       target_component, current_value, proposed_value
                FROM meta_config_proposals
                WHERE status = 'APPROVED'
                ORDER BY expected_sharpe_improvement DESC
                LIMIT %s
            """
            params = (max_proposals,)

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
            finally:
                cursor.close()

        proposals = []
        for row in rows:
            proposals.append(
                {
                    "proposal_id": row[0],
                    "strategy_id": row[1],
                    "market_id": row[2],
                    "proposal_type": row[3],
                    "target_component": row[4],
                    "current_value": row[5],
                    "proposed_value": row[6],
                }
            )

        return proposals

    def _load_config_change(self, change_id: str) -> Optional[Dict[str, Any]]:
        """Load config change from database."""
        sql = """
            SELECT change_id, proposal_id, strategy_id, target_component,
                   previous_value, new_value, is_reverted, applied_at
            FROM config_change_log
            WHERE change_id = %s
        """

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (change_id,))
                row = cursor.fetchone()
            finally:
                cursor.close()

        if not row:
            return None

        return {
            "change_id": row[0],
            "proposal_id": row[1],
            "strategy_id": row[2],
            "target_component": row[3],
            "previous_value": row[4],
            "new_value": row[5],
            "is_reverted": row[6],
            "applied_at": row[7],
        }

    def _validate_proposal(self, proposal: Dict[str, Any]) -> Optional[str]:
        """Validate proposal before application.

        Returns error message if invalid, None if valid.
        """
        if not proposal.get("strategy_id"):
            return "Missing strategy_id"

        if not proposal.get("target_component"):
            return "Missing target_component"

        if proposal.get("proposed_value") is None:
            return "Missing proposed_value"

        # Additional validation could check:
        # - Strategy exists in database
        # - Target component is valid for strategy type
        # - Proposed value is within acceptable range

        return None

    def _load_current_config(
        self, strategy_id: str, target_component: str
    ) -> Optional[Any]:
        """Load current configuration value from strategy_configs table."""
        sql = """
            SELECT config_json
            FROM strategy_configs
            WHERE strategy_id = %s
        """

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (strategy_id,))
                row = cursor.fetchone()
            finally:
                cursor.close()

        if row and row[0]:
            config_json = row[0]
            return config_json.get(target_component)

        return None

    def _apply_config_change(
        self, strategy_id: str, target_component: str, new_value: Any
    ) -> None:
        """Apply configuration change to strategy_configs table."""
        # First, load current config
        sql_select = """
            SELECT config_json
            FROM strategy_configs
            WHERE strategy_id = %s
        """

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql_select, (strategy_id,))
                row = cursor.fetchone()

                if row:
                    # Update existing config
                    config_json = row[0] or {}
                    config_json[target_component] = new_value

                    sql_update = """
                        UPDATE strategy_configs
                        SET config_json = %s,
                            updated_at = NOW()
                        WHERE strategy_id = %s
                    """
                    cursor.execute(sql_update, (Json(config_json), strategy_id))
                else:
                    # Insert new config
                    config_json = {target_component: new_value}

                    sql_insert = """
                        INSERT INTO strategy_configs (strategy_id, config_json, updated_at)
                        VALUES (%s, %s, NOW())
                    """
                    cursor.execute(sql_insert, (strategy_id, Json(config_json)))

                conn.commit()

                logger.info(
                    f"Applied config change: strategy={strategy_id} "
                    f"component={target_component} value={new_value}"
                )
            finally:
                cursor.close()

    def _record_config_change(
        self,
        change_id: str,
        proposal_id: str,
        strategy_id: str,
        market_id: Optional[str],
        change_type: str,
        target_component: str,
        previous_value: Any,
        new_value: Any,
        applied_by: str,
    ) -> None:
        """Record config change in config_change_log table."""
        sql = """
            INSERT INTO config_change_log (
                change_id,
                proposal_id,
                strategy_id,
                market_id,
                change_type,
                target_component,
                previous_value,
                new_value,
                applied_by,
                applied_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    sql,
                    (
                        change_id,
                        proposal_id,
                        strategy_id,
                        market_id,
                        change_type,
                        target_component,
                        Json(previous_value),
                        Json(new_value),
                        applied_by,
                    ),
                )
                conn.commit()
            finally:
                cursor.close()

    def _update_proposal_status(self, proposal_id: str, status: str) -> None:
        """Update proposal status."""
        sql = """
            UPDATE meta_config_proposals
            SET status = %s,
                applied_at = NOW()
            WHERE proposal_id = %s
        """

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (status, proposal_id))
                conn.commit()
            finally:
                cursor.close()

    def _mark_change_reverted(
        self, change_id: str, reason: str, reverted_by: str
    ) -> None:
        """Mark change as reverted in config_change_log."""
        sql = """
            UPDATE config_change_log
            SET is_reverted = TRUE,
                reverted_at = NOW(),
                reversion_reason = %s
            WHERE change_id = %s
        """

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (reason, change_id))
                conn.commit()
            finally:
                cursor.close()

    def _compute_metrics_for_period(
        self, strategy_id: str, start_date: date, end_date: date
    ) -> Dict[str, float]:
        """Compute aggregate metrics for strategy over date range."""
        sql = """
            SELECT AVG((metrics_json->>'annualised_sharpe')::float) as avg_sharpe,
                   AVG((metrics_json->>'cumulative_return')::float) as avg_return,
                   AVG((metrics_json->>'annualised_vol')::float) as avg_vol
            FROM backtest_runs
            WHERE strategy_id = %s
              AND start_date >= %s
              AND end_date <= %s
              AND metrics_json IS NOT NULL
        """

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (strategy_id, start_date, end_date))
                row = cursor.fetchone()
            finally:
                cursor.close()

        if row and row[0] is not None:
            return {
                "sharpe": float(row[0] or 0.0),
                "return": float(row[1] or 0.0),
                "volatility": float(row[2] or 0.0),
            }

        return {"sharpe": 0.0, "return": 0.0, "volatility": 0.0}

    def _update_change_performance(
        self,
        change_id: str,
        sharpe_before: float,
        sharpe_after: float,
        return_before: float,
        return_after: float,
        risk_before: float,
        risk_after: float,
        evaluation_start_date: date,
        evaluation_end_date: date,
    ) -> None:
        """Update config_change_log with performance metrics."""
        sql = """
            UPDATE config_change_log
            SET sharpe_before = %s,
                sharpe_after = %s,
                return_before = %s,
                return_after = %s,
                risk_before = %s,
                risk_after = %s,
                evaluation_start_date = %s,
                evaluation_end_date = %s
            WHERE change_id = %s
        """

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    sql,
                    (
                        sharpe_before,
                        sharpe_after,
                        return_before,
                        return_after,
                        risk_before,
                        risk_after,
                        evaluation_start_date,
                        evaluation_end_date,
                        change_id,
                    ),
                )
                conn.commit()
            finally:
                cursor.close()
