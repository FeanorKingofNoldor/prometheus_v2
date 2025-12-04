"""Prometheus v2: Tests for BasicAssessmentModel.

These tests exercise the basic numeric/STAB-based AssessmentModel
implementation using in-memory price data and stubbed stability
storage.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List

import numpy as np
import pandas as pd

from prometheus.core.time import TradingCalendar
from prometheus.data.reader import DataReader
from prometheus.stability.storage import StabilityStorage
from prometheus.stability.types import SoftTargetClass, SoftTargetState
from prometheus.assessment.model_basic import BasicAssessmentModel


@dataclass
class _StubDataReader(DataReader):  # type: ignore[misc]
    """Stub for DataReader.read_prices using an in-memory DataFrame."""

    df: pd.DataFrame

    def __init__(self, df: pd.DataFrame) -> None:  # type: ignore[no-untyped-def]
        # Bypass DatabaseManager initialisation in DataReader.
        self.df = df

    def read_prices(self, instrument_ids, start_date, end_date):  # type: ignore[override, no-untyped-def]
        return self.df


class _StubStabilityStorage(StabilityStorage):  # type: ignore[misc]
    """Very small stub for StabilityStorage.latest_state.

    Avoids any DB access; returns a preconfigured SoftTargetState.
    """

    def __init__(self, state: SoftTargetState | None) -> None:  # type: ignore[no-untyped-def]
        self._state = state

    def get_latest_state(self, entity_type: str, entity_id: str):  # type: ignore[override, no-untyped-def]
        return self._state


class TestBasicAssessmentModel:
    """Tests for BasicAssessmentModel behaviour."""

    def _build_price_df(self, closes: List[float]) -> pd.DataFrame:
        instrument_id = "TEST_ASSESS_INSTRUMENT"
        start = date(2024, 1, 1)
        dates: List[date] = [start + timedelta(days=i) for i in range(len(closes))]

        rows = []
        for d, c in zip(dates, closes):
            rows.append(
                (
                    instrument_id,
                    d,
                    c,
                    c + 1.0,
                    c - 1.0,
                    c,
                    c,
                    1_000_000.0,
                    "USD",
                    {},
                )
            )

        df = pd.DataFrame(
            rows,
            columns=[
                "instrument_id",
                "trade_date",
                "open",
                "high",
                "low",
                "close",
                "adjusted_close",
                "volume",
                "currency",
                "metadata",
            ],
        )
        return df

    def test_positive_momentum_without_stab_yields_buy_like_signal(self) -> None:
        """With positive momentum and no STAB penalty, we expect a bullish label."""

        # Simple monotonic uptrend.
        closes = [100.0 + 0.5 * i for i in range(63)]
        df = self._build_price_df(closes)
        reader = _StubDataReader(df)
        calendar = TradingCalendar()

        model = BasicAssessmentModel(
            data_reader=reader,
            calendar=calendar,
            stability_storage=None,
            min_window_days=21,
            momentum_ref=0.05,
        )

        instrument_id = "TEST_ASSESS_INSTRUMENT"
        strategy_id = "TEST_STRAT"
        market_id = "US_EQ"
        as_of = date(2024, 3, 4)
        horizon = 21

        scores = model.score_instruments(
            strategy_id=strategy_id,
            market_id=market_id,
            instrument_ids=[instrument_id],
            as_of_date=as_of,
            horizon_days=horizon,
        )

        assert instrument_id in scores
        s = scores[instrument_id]
        # Expect positive expected_return and a BUY/STRONG_BUY style label.
        assert s.expected_return > 0.0
        assert s.signal_label in {"BUY", "STRONG_BUY"}
        assert s.confidence >= 0.0

    def test_high_fragility_penalty_pushes_score_down(self) -> None:
        """High STAB soft_target_score and weak_profile should penalise scores."""

        closes = [100.0 + 0.5 * i for i in range(63)]
        df = self._build_price_df(closes)
        reader = _StubDataReader(df)
        calendar = TradingCalendar()

        instrument_id = "TEST_ASSESS_INSTRUMENT"
        strategy_id = "TEST_STRAT"
        market_id = "US_EQ"
        as_of = date(2024, 3, 4)
        horizon = 21

        # First, model without STAB to establish baseline score.
        model_no_stab = BasicAssessmentModel(
            data_reader=reader,
            calendar=calendar,
            stability_storage=None,
            min_window_days=21,
            momentum_ref=0.05,
            fragility_penalty_weight=1.0,
            weak_profile_penalty_multiplier=0.5,
        )
        base_score = model_no_stab.score_instruments(
            strategy_id=strategy_id,
            market_id=market_id,
            instrument_ids=[instrument_id],
            as_of_date=as_of,
            horizon_days=horizon,
        )[instrument_id]

        # Now, introduce a very fragile STAB state.
        stab_state = SoftTargetState(
            as_of_date=as_of,
            entity_type="INSTRUMENT",
            entity_id=instrument_id,
            soft_target_class=SoftTargetClass.BREAKER,
            soft_target_score=80.0,
            weak_profile=True,
            instability=80.0,
            high_fragility=80.0,
            complacent_pricing=10.0,
            metadata=None,
        )
        stab_storage = _StubStabilityStorage(state=stab_state)

        model_with_stab = BasicAssessmentModel(
            data_reader=reader,
            calendar=calendar,
            stability_storage=stab_storage,
            min_window_days=21,
            momentum_ref=0.05,
            fragility_penalty_weight=1.0,
            weak_profile_penalty_multiplier=0.5,
        )

        penalised_score = model_with_stab.score_instruments(
            strategy_id=strategy_id,
            market_id=market_id,
            instrument_ids=[instrument_id],
            as_of_date=as_of,
            horizon_days=horizon,
        )[instrument_id]

        # Expected return and normalised score should both be lower when
        # fragility penalties are applied.
        assert penalised_score.expected_return < base_score.expected_return
        assert penalised_score.score <= base_score.score

        # Fragility penalty component should be strictly positive.
        assert penalised_score.alpha_components["fragility_penalty"] > 0.0

        # With a strong enough penalty, label should no longer be strongly
        # bullish; in practice this is usually HOLD/SELL.
        assert penalised_score.signal_label in {"HOLD", "SELL", "STRONG_SELL"}
