"""Integration tests for BasicUniverseModel with real Assessment scores.

This module validates that BasicUniverseModel and UniverseEngine can:

- Use STAB and price history for liquidity and fragility filters.
- Consume Assessment Engine outputs from ``instrument_scores``.
- Reflect Assessment scores in the final universe ranking.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import List, Tuple

import pytest

from prometheus.core.config import get_config
from prometheus.core.database import DatabaseManager
from prometheus.core.ids import generate_uuid
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
from prometheus.universe import (
    UniverseEngine,
    UniverseStorage,
    BasicUniverseModel,
)


def _ensure_market(db_manager: DatabaseManager, market_id: str = "US_EQ") -> None:
    """Ensure a market row exists for the given market_id."""

    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO markets (market_id, name, region, timezone)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (market_id) DO NOTHING
                """,
                (market_id, "US Equities", "US", "America/New_York"),
            )
            conn.commit()
        finally:
            cursor.close()


def _insert_issuer_and_instrument(db_manager: DatabaseManager, symbol: str, name: str) -> Tuple[str, str]:
    issuer_id = f"UNIV_ASSESS_ISS_{generate_uuid()[:8]}"
    instrument_id = f"UNIV_ASSESS_INST_{generate_uuid()[:8]}"
    market_id = "US_EQ"

    _ensure_market(db_manager, market_id)

    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO issuers (issuer_id, issuer_type, name)
                VALUES (%s, %s, %s)
                """,
                (issuer_id, "COMPANY", name),
            )
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
                (instrument_id, issuer_id, market_id, "EQUITY", symbol, "USD"),
            )
            conn.commit()
        finally:
            cursor.close()

    return issuer_id, instrument_id


def _insert_price_history(
    db_manager: DatabaseManager,
    instrument_id: str,
    pattern: str,
) -> List[date]:
    """Insert synthetic price history with a given pattern.

    pattern:
        - "strong_up": strong uptrend.
        - "mild_up": gentler uptrend.
    """

    calendar = TradingCalendar()
    start = date(2024, 1, 1)
    trading_days = calendar.trading_days_between(start, start + timedelta(days=90))
    trading_days = trading_days[:63]

    writer = DataWriter(db_manager=db_manager)
    price = 100.0
    bars: List[PriceBar] = []
    for d in trading_days:
        if pattern == "strong_up":
            price *= 1.01
        elif pattern == "mild_up":
            price *= 1.002
        close = price
        bars.append(
            PriceBar(
                instrument_id=instrument_id,
                trade_date=d,
                open=close,
                high=close * 1.01,
                low=close * 0.99,
                close=close,
                adjusted_close=close,
                volume=500_000.0,
                currency="USD",
                metadata={"source": "iter_universe_with_assessment"},
            )
        )

    writer.write_prices(bars)
    return trading_days


def _cleanup(db_manager: DatabaseManager, issuer_ids: List[str], instrument_ids: List[str]) -> None:
    """Remove test artefacts from universe, stability, assessment, and prices tables."""

    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM universe_members WHERE entity_id = ANY(%s)",
                (instrument_ids,),
            )
            cursor.execute(
                "DELETE FROM instrument_scores WHERE instrument_id = ANY(%s)",
                (instrument_ids,),
            )
            cursor.execute(
                "DELETE FROM soft_target_classes WHERE entity_type = 'INSTRUMENT' AND entity_id = ANY(%s)",
                (instrument_ids,),
            )
            cursor.execute(
                "DELETE FROM stability_vectors WHERE entity_type = 'INSTRUMENT' AND entity_id = ANY(%s)",
                (instrument_ids,),
            )
            cursor.execute("DELETE FROM instruments WHERE instrument_id = ANY(%s)", (instrument_ids,))
            cursor.execute("DELETE FROM issuers WHERE issuer_id = ANY(%s)", (issuer_ids,))
            conn.commit()
        finally:
            cursor.close()

    with db_manager.get_historical_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM prices_daily WHERE instrument_id = ANY(%s)", (instrument_ids,))
            conn.commit()
        finally:
            cursor.close()


@pytest.mark.integration
class TestUniverseWithAssessmentIntegration:
    """Integration tests for UniverseEngine reading Assessment scores."""

    def test_universe_respects_assessment_scores_in_ranking(self) -> None:
        config = get_config()
        db_manager = DatabaseManager(config)

        # Two instruments: both liquid and stable, but with different
        # Assessment scores driven by their price momentum.
        issuer_high, inst_high = _insert_issuer_and_instrument(db_manager, "HGH", "High Score Corp")
        issuer_low, inst_low = _insert_issuer_and_instrument(db_manager, "LOW", "Low Score Corp")

        try:
            # Insert price histories: strong vs mild uptrend.
            days_high = _insert_price_history(db_manager, inst_high, pattern="strong_up")
            days_low = _insert_price_history(db_manager, inst_low, pattern="mild_up")

            as_of = min(days_high[-1], days_low[-1])

            calendar = TradingCalendar()
            reader = DataReader(db_manager=db_manager)

            # STAB: numeric-only BasicPriceStabilityModel.
            stab_storage = StabilityStorage(db_manager=db_manager)
            stab_model = BasicPriceStabilityModel(
                data_reader=reader,
                calendar=calendar,
                window_days=63,
            )
            stab_engine = StabilityEngine(model=stab_model, storage=stab_storage)

            for inst in (inst_high, inst_low):
                try:
                    stab_engine.score_entity(as_of, "INSTRUMENT", inst)
                except ValueError:
                    # If history is insufficient for some reason, the test
                    # setup is wrong.
                    pytest.fail("STAB scoring failed due to insufficient history")

            # Assessment Engine: write scores into instrument_scores.
            assessment_storage = InstrumentScoreStorage(db_manager=db_manager)
            assessment_model = BasicAssessmentModel(
                data_reader=reader,
                calendar=calendar,
                stability_storage=stab_storage,
                min_window_days=21,
                momentum_ref=0.05,
            )
            assessment_engine = AssessmentEngine(
                model=assessment_model,
                storage=assessment_storage,
                model_id="assessment-basic-v1",
            )

            strategy_id = "UNIV_ASSESS_STRAT"
            market_id = "US_EQ"

            scores = assessment_engine.score_universe(
                strategy_id=strategy_id,
                market_id=market_id,
                instrument_ids=[inst_high, inst_low],
                as_of_date=as_of,
                horizon_days=21,
            )

            # Basic sanity: both instruments scored, and high has higher
            # Assessment score than low.
            assert inst_high in scores and inst_low in scores
            high_score = scores[inst_high]
            low_score = scores[inst_low]
            assert high_score.score > low_score.score

            # Universe engine with Assessment integration enabled.
            univ_storage = UniverseStorage(db_manager=db_manager)
            univ_model = BasicUniverseModel(
                db_manager=db_manager,
                calendar=calendar,
                data_reader=reader,
                profile_service=None,  # not used in this test
                stability_storage=stab_storage,
                market_ids=("US_EQ",),
                min_avg_volume=100_000.0,
                max_soft_target_score=90.0,
                exclude_breakers=True,
                exclude_weak_profile_when_fragile=True,
                window_days=63,
                use_assessment_scores=True,
                assessment_strategy_id=strategy_id,
                assessment_horizon_days=21,
                assessment_score_weight=50.0,
            )
            univ_engine = UniverseEngine(model=univ_model, storage=univ_storage)

            universe_id = "CORE_EQ_ASSESS"
            members = univ_engine.build_and_save(as_of, universe_id)

            included = {m.entity_id: m for m in members if m.included}
            assert {inst_high, inst_low} <= set(included.keys())

            member_high = included[inst_high]
            member_low = included[inst_low]

            # Both should carry Assessment scores in their reasons.
            assert "assessment_score" in member_high.reasons
            assert "assessment_score" in member_low.reasons
            assert member_high.reasons["assessment_score"] > member_low.reasons["assessment_score"]

            # Overall universe ranking score must reflect the Assessment
            # difference on top of identical liquidity/STAB inputs.
            assert member_high.score > member_low.score

            # Check that universe_members rows exist for both instruments.
            persisted = univ_storage.get_universe(as_of, universe_id, included_only=False)
            persisted_ids = {m.entity_id for m in persisted}
            assert {inst_high, inst_low} <= persisted_ids
        finally:
            _cleanup(db_manager, [issuer_high, issuer_low], [inst_high, inst_low])
