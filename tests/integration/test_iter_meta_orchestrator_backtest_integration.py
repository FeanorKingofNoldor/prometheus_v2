"""Integration tests for MetaOrchestrator over backtest runs.

This module validates that MetaOrchestrator can:

* Read backtest_runs rows and reconstruct SleeveConfig objects from
  config_json.
* Expose per-sleeve evaluations for a given strategy.
* Select the top-k sleeves based on metrics_json.
"""

from __future__ import annotations

from typing import List
from datetime import date

import pytest

from prometheus.core.database import get_db_manager
from prometheus.core.ids import generate_uuid
from prometheus.meta import MetaOrchestrator, MetaStorage
from prometheus.pipeline.tasks import run_meta_for_strategy


@pytest.mark.integration
class TestMetaOrchestratorBacktestIntegration:
    """Integration tests for MetaOrchestrator + backtest_runs."""

    def test_evaluate_and_select_top_sleeves(self) -> None:
        db_manager = get_db_manager()

        # If the engine_decisions table has not been created (e.g. runtime
        # migrations not yet applied), skip this integration test rather
        # than failing with an UndefinedTable error.
        with db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT to_regclass('engine_decisions')")
                (tbl_name,) = cursor.fetchone()
                if tbl_name is None:
                    pytest.skip("engine_decisions table not present; apply migration 0018 before running this test")
            finally:
                cursor.close()

        run_ids: List[str] = []
        strategy_id = "META_TEST_STRAT"

        # Seed a few synthetic backtest_runs rows with different metrics.
        with db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                def insert_run(sleeve_id: str, sharpe: float, cumret: float, maxdd: float) -> str:
                    run_id = generate_uuid()
                    config_json = {
                        "sleeve_id": sleeve_id,
                        "strategy_id": strategy_id,
                        "market_id": "US_EQ",
                        "universe_id": "META_TEST_UNIVERSE",
                        "portfolio_id": "META_TEST_PORTFOLIO",
                        "assessment_strategy_id": "META_TEST_ASSESS",
                        "assessment_horizon_days": 21,
                        "start_date": "2024-01-01",
                        "end_date": "2024-03-31",
                    }
                    metrics_json = {
                        "annualised_sharpe": sharpe,
                        "cumulative_return": cumret,
                        "max_drawdown": maxdd,
                    }
                    from psycopg2.extras import Json

                    cursor.execute(
                        """
                        INSERT INTO backtest_runs (
                            run_id,
                            strategy_id,
                            config_json,
                            start_date,
                            end_date,
                            universe_id,
                            metrics_json,
                            created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                        """,
                        (
                            run_id,
                            strategy_id,
                            Json(config_json),
                            "2024-01-01",
                            "2024-03-31",
                            "META_TEST_UNIVERSE",
                            Json(metrics_json),
                        ),
                    )
                    return run_id

                # Sleeve A: best Sharpe and return.
                run_ids.append(insert_run("SLEEVE_A", sharpe=1.5, cumret=0.25, maxdd=-0.10))
                # Sleeve B: lower Sharpe.
                run_ids.append(insert_run("SLEEVE_B", sharpe=0.8, cumret=0.20, maxdd=-0.08))
                # Different strategy; should be ignored.
                from psycopg2.extras import Json

                cursor.execute(
                    """
                    INSERT INTO backtest_runs (
                        run_id,
                        strategy_id,
                        config_json,
                        start_date,
                        end_date,
                        universe_id,
                        metrics_json,
                        created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                    """,
                    (
                        generate_uuid(),
                        "OTHER_STRAT",
                        Json(
                            {
                                "sleeve_id": "OTHER_SLEEVE",
                                "strategy_id": "OTHER_STRAT",
                                "market_id": "US_EQ",
                                "universe_id": "META_TEST_UNIVERSE",
                                "portfolio_id": "META_TEST_PORTFOLIO",
                                "assessment_strategy_id": "META_TEST_ASSESS",
                                "assessment_horizon_days": 21,
                            }
                        ),
                        "2024-01-01",
                        "2024-03-31",
                        "META_TEST_UNIVERSE",
                        Json({"annualised_sharpe": 10.0, "cumulative_return": 1.0, "max_drawdown": -0.5}),
                    ),
                )

                conn.commit()
            finally:
                cursor.close()

        # Evaluate sleeves via MetaOrchestrator.
        storage = MetaStorage(db_manager=db_manager)
        orchestrator = MetaOrchestrator(storage=storage)

        evaluations = orchestrator.evaluate_sleeves(strategy_id)
        sleeve_ids = {ev.sleeve_config.sleeve_id for ev in evaluations}
        assert sleeve_ids == {"SLEEVE_A", "SLEEVE_B"}

        top = orchestrator.select_top_sleeves(strategy_id, k=1)
        assert len(top) == 1
        assert top[0].sleeve_config.sleeve_id == "SLEEVE_A"

        # Request more sleeves than exist; should simply return all.
        top_all = orchestrator.select_top_sleeves(strategy_id, k=10)
        assert {ev.sleeve_config.sleeve_id for ev in top_all} == {"SLEEVE_A", "SLEEVE_B"}

        # Also verify that run_meta_for_strategy records a decision into
        # engine_decisions.
        decision_id = run_meta_for_strategy(
            db_manager=db_manager,
            strategy_id=strategy_id,
            as_of_date=date(2024, 3, 31),
            top_k=1,
        )
        assert decision_id is not None

        with db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    SELECT strategy_id, engine_name, input_refs, output_refs
                    FROM engine_decisions
                    WHERE decision_id = %s
                    """,
                    (decision_id,),
                )
                row = cursor.fetchone()
                assert row is not None
                strat_db, engine_name_db, input_refs_db, output_refs_db = row
                assert strat_db == strategy_id
                assert engine_name_db == "META_ORCHESTRATOR"
                assert "candidate_runs" in (input_refs_db or {})
                assert "selected_sleeves" in (output_refs_db or {})
            finally:
                cursor.close()

        # Clean up seeded backtest_runs and engine_decisions.
        with db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "DELETE FROM backtest_runs WHERE run_id = ANY(%s)",
                    (run_ids,),
                )
                cursor.execute(
                    "DELETE FROM backtest_runs WHERE strategy_id = %s",
                    ("OTHER_STRAT",),
                )
                cursor.execute(
                    "DELETE FROM engine_decisions WHERE strategy_id = %s",
                    (strategy_id,),
                )
                conn.commit()
            finally:
                cursor.close()
