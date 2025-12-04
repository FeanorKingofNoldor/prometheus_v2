"""Integration test for Synthetic Scenario Engine.

This test uses the real DatabaseManager and DataWriter to exercise the
SyntheticScenarioEngine end-to-end over a small synthetic price
history.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List

import pandas as pd
import pytest

from prometheus.core.database import get_db_manager
from prometheus.core.ids import generate_uuid
from prometheus.core.logging import get_logger
from prometheus.data.writer import DataWriter
from prometheus.data.reader import DataReader
from prometheus.data.types import PriceBar
from prometheus.synthetic import ScenarioRequest, SyntheticScenarioEngine


logger = get_logger(__name__)


@pytest.mark.integration
class TestIterSyntheticScenarioEngine:
    def test_generate_and_persist_historical_scenarios(self) -> None:
        db_manager = get_db_manager()

        # Prepare a tiny price history for two instruments in US_EQ.
        writer = DataWriter(db_manager=db_manager)

        # Use unique instrument identifiers so the test remains idempotent
        # across runs even with primary keys on (instrument_id, trade_date).
        instruments = [f"SYNTH_{generate_uuid()[:8]}", f"SYNTH_{generate_uuid()[:8]}"]
        start = date(2024, 1, 1)
        days = 10
        prices: Dict[str, List[PriceBar]] = {}

        for inst in instruments:
            series: List[PriceBar] = []
            for i in range(days):
                d = start + timedelta(days=i)
                # Simple upward drift; we only care that prices change.
                close = 100.0 + i * 1.0
                bar = PriceBar(
                    instrument_id=inst,
                    trade_date=d,
                    open=close,
                    high=close,
                    low=close,
                    close=close,
                    adjusted_close=close,
                    volume=1_000,
                    currency="USD",
                    metadata={},
                )
                series.append(bar)
            prices[inst] = series

        # Write prices into historical_db.prices_daily.
        for inst, series in prices.items():
            writer.write_prices(series)

        reader = DataReader(db_manager=db_manager)
        engine = SyntheticScenarioEngine(db_manager=db_manager, data_reader=reader)

        request = ScenarioRequest(
            name="INTEGRATION_TEST_SET",
            description="integration test historical scenarios",
            category="HISTORICAL",
            horizon_days=5,
            num_paths=3,
            markets=["US_EQ"],
            base_date_start=start,
            base_date_end=start + timedelta(days=days - 1),
        )

        # Monkeypatch instrument lookup to our synthetic instruments.
        engine._load_instruments_for_markets = lambda markets: instruments  # type: ignore[assignment]

        set_ref = engine.generate_scenario_set(request)

        assert set_ref.horizon_days == 5
        assert set_ref.num_paths == 3

        # Verify that paths were written.
        with db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM scenario_paths
                    WHERE scenario_set_id = %s
                    """,
                    (set_ref.scenario_set_id,),
                )
                (count_paths,) = cursor.fetchone()
            finally:
                cursor.close()

        assert count_paths > 0

        metadata = engine.get_scenario_set_metadata(set_ref.scenario_set_id)
        assert metadata["horizon_days"] == 5
        assert metadata["num_paths"] == 3
