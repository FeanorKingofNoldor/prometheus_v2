"""Integration test for the Assessment Engine.

This test exercises BasicAssessmentModel and AssessmentEngine end-to-end
using the real DatabaseManager, DataWriter, and InstrumentScoreStorage.
It verifies that scores are computed for a simple price history and
persisted into ``instrument_scores``.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import List

import pytest

from prometheus.core.database import get_db_manager
from prometheus.core.ids import generate_uuid
from prometheus.core.logging import get_logger
from prometheus.core.time import TradingCalendar
from prometheus.data.types import PriceBar
from prometheus.data.writer import DataWriter
from prometheus.data.reader import DataReader
from prometheus.stability import (
    StabilityEngine,
    StabilityStorage,
    BasicPriceStabilityModel,
)
from prometheus.assessment import AssessmentEngine
from prometheus.assessment.model_basic import BasicAssessmentModel
from prometheus.assessment.storage import InstrumentScoreStorage


logger = get_logger(__name__)


@pytest.mark.integration
class TestIterAssessmentEngine:
    def test_assessment_engine_scores_and_persists(self) -> None:
        db_manager = get_db_manager()

        # 1) Insert a small monotonic price history for one instrument.
        writer = DataWriter(db_manager=db_manager)
        instrument_id = f"ASSESS_{generate_uuid()[:8]}"

        calendar = TradingCalendar()
        start = date(2024, 1, 1)
        trading_days = calendar.trading_days_between(start, start + timedelta(days=90))
        trading_days = trading_days[:63]

        bars: List[PriceBar] = []
        price = 100.0
        for d in trading_days:
            close = price
            bars.append(
                PriceBar(
                    instrument_id=instrument_id,
                    trade_date=d,
                    open=close,
                    high=close,
                    low=close,
                    close=close,
                    adjusted_close=close,
                    volume=1_000_000.0,
                    currency="USD",
                    metadata={"source": "iter_assessment"},
                )
            )
            price += 0.5

        writer.write_prices(bars)

        # 2) Run STAB once to produce a SoftTargetState used by Assessment.
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

        # 3) Run AssessmentEngine over this single-instrument universe.
        assessment_storage = InstrumentScoreStorage(db_manager=db_manager)
        assessment_model = BasicAssessmentModel(
            data_reader=reader,
            calendar=calendar,
            stability_storage=stab_storage,
        )
        engine = AssessmentEngine(
            model=assessment_model,
            storage=assessment_storage,
            model_id="assessment-basic-v1",
        )

        strategy_id = "TEST_ASSESS_STRAT"
        market_id = "US_EQ"

        scores = engine.score_universe(
            strategy_id=strategy_id,
            market_id=market_id,
            instrument_ids=[instrument_id],
            as_of_date=as_of,
            horizon_days=21,
        )

        assert instrument_id in scores
        s = scores[instrument_id]
        assert s.instrument_id == instrument_id
        assert s.as_of_date == as_of
        assert s.horizon_days == 21
        assert s.signal_label in {"BUY", "STRONG_BUY", "HOLD", "SELL", "STRONG_SELL"}
        assert "momentum" in s.alpha_components
        assert "fragility_penalty" in s.alpha_components

        # 4) Verify a row was written into instrument_scores.
        try:
            with db_manager.get_runtime_connection() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(
                        """
                        SELECT strategy_id, market_id, instrument_id, as_of_date, horizon_days,
                               expected_return, score, confidence, signal_label
                        FROM instrument_scores
                        WHERE strategy_id = %s
                          AND market_id = %s
                          AND instrument_id = %s
                          AND as_of_date = %s
                          AND horizon_days = %s
                        """,
                        (strategy_id, market_id, instrument_id, as_of, 21),
                    )
                    row = cursor.fetchone()
                finally:
                    cursor.close()

            assert row is not None
            (
                strat_db,
                mkt_db,
                inst_db,
                as_of_db,
                horizon_db,
                exp_ret_db,
                score_db,
                conf_db,
                label_db,
            ) = row
            assert strat_db == strategy_id
            assert mkt_db == market_id
            assert inst_db == instrument_id
            assert as_of_db == as_of
            assert horizon_db == 21
            # Basic sanity on numeric fields.
            assert isinstance(exp_ret_db, float)
            assert isinstance(score_db, float)
            assert isinstance(conf_db, float)
            assert isinstance(label_db, str)
        finally:
            # Cleanup test artefacts from both runtime and historical DBs.
            with db_manager.get_runtime_connection() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(
                        "DELETE FROM instrument_scores WHERE instrument_id = %s",
                        (instrument_id,),
                    )
                    cursor.execute(
                        "DELETE FROM soft_target_classes WHERE entity_type = %s AND entity_id = %s",
                        ("INSTRUMENT", instrument_id),
                    )
                    cursor.execute(
                        "DELETE FROM stability_vectors WHERE entity_type = %s AND entity_id = %s",
                        ("INSTRUMENT", instrument_id),
                    )
                    conn.commit()
                finally:
                    cursor.close()

            with db_manager.get_historical_connection() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(
                        "DELETE FROM prices_daily WHERE instrument_id = %s",
                        (instrument_id,),
                    )
                    conn.commit()
                finally:
                    cursor.close()
