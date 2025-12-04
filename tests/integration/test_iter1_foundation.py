"""
Prometheus v2: Iteration 1 Foundation Integration Test

This integration test validates the complete workflow for Iteration 1:
- Configuration loading
- Logging setup
- Database connection acquisition
- CRUD operations on core entity tables
"""

from __future__ import annotations

from datetime import date

import pytest

from prometheus.core.config import get_config
from prometheus.core.database import DatabaseManager
from prometheus.core.ids import generate_uuid
from prometheus.core.logging import get_logger, setup_logging


@pytest.mark.integration
class TestIteration1Foundation:
    """Integration tests for Iteration 1 foundation components."""

    def test_full_foundation_workflow(self) -> None:
        """End-to-end test of config, logging, and database CRUD.

        This test assumes that both the runtime and historical databases
        are reachable using the credentials specified in the environment
        (typically via ``.env``).
        """

        # Step 1: Load configuration
        config = get_config()

        assert config.historical_db_host
        assert config.runtime_db_host

        # Step 2: Configure logging
        setup_logging(config)
        logger = get_logger("tests.integration.iter1")
        logger.info("Starting Iteration 1 foundation integration test")

        # Step 3: Initialise database manager
        db_manager = DatabaseManager(config)

        # Step 4: Perform basic CRUD against runtime_db
        with db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()

            # Insert a market
            market_id = f"TEST_MARKET_{generate_uuid()[:8]}"
            cursor.execute(
                """
                INSERT INTO markets (market_id, name, region, timezone)
                VALUES (%s, %s, %s, %s)
                """,
                (market_id, "Test Market", "US", "America/New_York"),
            )

            # Insert an issuer
            issuer_id = f"TEST_ISSUER_{generate_uuid()[:8]}"
            cursor.execute(
                """
                INSERT INTO issuers (issuer_id, issuer_type, name)
                VALUES (%s, %s, %s)
                """,
                (issuer_id, "CORPORATION", "Test Corp"),
            )

            # Insert an instrument
            instrument_id = f"TEST_INST_{generate_uuid()[:8]}"
            cursor.execute(
                """
                INSERT INTO instruments (
                    instrument_id,
                    issuer_id,
                    market_id,
                    asset_class,
                    symbol,
                    currency
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (instrument_id, issuer_id, market_id, "EQUITY", "TEST", "USD"),
            )

            # Insert a portfolio
            portfolio_id = f"TEST_PORT_{generate_uuid()[:8]}"
            cursor.execute(
                """
                INSERT INTO portfolios (portfolio_id, name, base_currency)
                VALUES (%s, %s, %s)
                """,
                (portfolio_id, "Test Portfolio", "USD"),
            )

            # Insert a strategy
            strategy_id = f"TEST_STRAT_{generate_uuid()[:8]}"
            cursor.execute(
                """
                INSERT INTO strategies (strategy_id, name)
                VALUES (%s, %s)
                """,
                (strategy_id, "Test Strategy"),
            )

            conn.commit()

            # Step 5: Query back and validate
            cursor.execute("SELECT name FROM markets WHERE market_id = %s", (market_id,))
            market_row = cursor.fetchone()
            assert market_row is not None
            assert market_row[0] == "Test Market"

            cursor.execute("SELECT name FROM issuers WHERE issuer_id = %s", (issuer_id,))
            issuer_row = cursor.fetchone()
            assert issuer_row is not None
            assert issuer_row[0] == "Test Corp"

            cursor.execute(
                "SELECT symbol FROM instruments WHERE instrument_id = %s",
                (instrument_id,),
            )
            instrument_row = cursor.fetchone()
            assert instrument_row is not None
            assert instrument_row[0] == "TEST"

            cursor.execute(
                "SELECT name FROM portfolios WHERE portfolio_id = %s",
                (portfolio_id,),
            )
            portfolio_row = cursor.fetchone()
            assert portfolio_row is not None
            assert portfolio_row[0] == "Test Portfolio"

            cursor.execute(
                "SELECT name FROM strategies WHERE strategy_id = %s",
                (strategy_id,),
            )
            strategy_row = cursor.fetchone()
            assert strategy_row is not None
            assert strategy_row[0] == "Test Strategy"

            # Step 6: Roll back inserts to leave database clean
            conn.rollback()

            cursor.close()

        logger.info("Iteration 1 foundation integration test completed successfully")
