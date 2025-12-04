"""Integration test for Fragility Alpha Engine.

This test wires together the Stability Engine, Synthetic Scenario
Engine, and Fragility Alpha Engine to compute a fragility measure for a
single instrument and persist it in ``fragility_measures``.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import List

import pytest

from prometheus.core.database import get_db_manager
from prometheus.core.ids import generate_uuid
from prometheus.core.logging import get_logger
from prometheus.core.time import TradingCalendar
from prometheus.data.reader import DataReader
from prometheus.data.writer import DataWriter
from prometheus.data.types import PriceBar
from prometheus.stability import (
    BasicPriceStabilityModel,
    StabilityEngine,
    StabilityStorage,
)
from prometheus.synthetic import ScenarioRequest, SyntheticScenarioEngine
from prometheus.fragility import (
    BasicFragilityAlphaModel,
    FragilityAlphaEngine,
    FragilityClass,
    FragilityStorage,
)


logger = get_logger(__name__)


@pytest.mark.integration
class TestIterFragilityAlphaEngine:
    def test_fragility_alpha_end_to_end(self) -> None:
        db_manager = get_db_manager()

        # 1) Write a sufficient price history for one instrument using
        # trading days, so the STAB model has a full window. Use a unique
        # instrument_id to keep the test idempotent across runs.
        writer = DataWriter(db_manager=db_manager)
        instrument_id = f"FRAG_{generate_uuid()[:8]}"

        calendar = TradingCalendar()
        start = date(2024, 1, 1)
        trading_days = calendar.trading_days_between(start, start + timedelta(days=90))
        trading_days = trading_days[:63]

        bars: List[PriceBar] = []
        price = 100.0
        for d in trading_days:
            close = price
            bar = PriceBar(
                instrument_id=instrument_id,
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
            bars.append(bar)
            price += 0.5

        writer.write_prices(bars)

        # 2) Run Stability Engine once to produce a SoftTargetState.
        reader = DataReader(db_manager=db_manager)
        stab_storage = StabilityStorage(db_manager=db_manager)
        stab_model = BasicPriceStabilityModel(
            data_reader=reader,
            calendar=calendar,
            window_days=63,
        )
        stab_engine = StabilityEngine(model=stab_model, storage=stab_storage)

        as_of = trading_days[-1]
        stab_engine.score_entity(as_of, "INSTRUMENT", instrument_id)

        # 3) Generate a small historical scenario set for this instrument.
        synthetic_engine = SyntheticScenarioEngine(db_manager=db_manager, data_reader=reader)
        request = ScenarioRequest(
            name="FRAG_TEST_SCENARIOS",
            description="fragility alpha integration test",
            category="HISTORICAL",
            horizon_days=5,
            num_paths=3,
            markets=["US_EQ"],
            base_date_start=start,
            base_date_end=as_of,
        )

        # Monkeypatch instrument lookup to point at our synthetic instrument.
        synthetic_engine._load_instruments_for_markets = lambda markets: [instrument_id]  # type: ignore[assignment]
        scenario_set = synthetic_engine.generate_scenario_set(request)

        # 4) Run Fragility Alpha Engine.
        frag_storage = FragilityStorage(db_manager=db_manager)
        frag_model = BasicFragilityAlphaModel(
            db_manager=db_manager,
            stability_storage=stab_storage,
            scenario_set_id=scenario_set.scenario_set_id,
        )
        frag_engine = FragilityAlphaEngine(model=frag_model, storage=frag_storage)

        measure, templates = frag_engine.score_and_suggest(as_of, "INSTRUMENT", instrument_id)

        assert measure.entity_id == instrument_id
        assert 0.0 <= measure.fragility_score <= 1.0
        assert measure.class_label in {
            FragilityClass.NONE,
            FragilityClass.WATCHLIST,
            FragilityClass.SHORT_CANDIDATE,
            FragilityClass.CRISIS,
        }

        # Ensure the measure was persisted.
        with db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM fragility_measures
                    WHERE entity_type = %s AND entity_id = %s AND as_of_date = %s
                    """,
                    ("INSTRUMENT", instrument_id, as_of),
                )
                (count_rows,) = cursor.fetchone()
            finally:
                cursor.close()

        assert count_rows == 1

        # There may or may not be a short template depending on the
        # realised fragility score, but the call must succeed.
        assert isinstance(templates, list)
