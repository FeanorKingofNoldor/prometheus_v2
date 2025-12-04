"""Prometheus v2 – Basic price-based StabilityModel for STAB engine.

This module implements a first real numeric StabilityModel based solely
on daily close prices from ``prices_daily``. It computes simple
volatility, drawdown, and trend measures over a rolling window and
converts them into a Soft Target Index and classification.

The goal is to provide a fully real, deterministic baseline model using
existing data; additional factors (CDS, macro, profiles, joint
embeddings) can be added in later iterations.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol

import numpy as np

from prometheus.core.logging import get_logger
from prometheus.core.time import TradingCalendar
from prometheus.data.reader import DataReader
from prometheus.profiles.types import ProfileSnapshot
from prometheus.stability.types import SoftTargetClass, SoftTargetState, StabilityVector

logger = get_logger(__name__)


class ProfileServiceLike(Protocol):
    """Minimal protocol for profile services used by STAB.

    This allows :class:`BasicPriceStabilityModel` to depend only on the
    ``get_snapshot`` behaviour, while remaining agnostic to the concrete
    ProfileService implementation.
    """

    def get_snapshot(
        self, issuer_id: str, as_of_date: date
    ) -> ProfileSnapshot:  # pragma: no cover - interface
        ...


@dataclass
class BasicPriceStabilityModel:
    """Price-based implementation of :class:`StabilityModel`.

    This model currently supports only ``entity_type="INSTRUMENT"`` and
    uses a fixed lookback window of trading days to compute:

    - Realised volatility of log returns.
    - Maximum drawdown over the window.
    - Simple price trend over the window.

    These metrics are mapped into component scores in [0, 100] and
    combined into an overall Soft Target Index, which is then mapped to
    a :class:`SoftTargetClass`.
    """

    data_reader: DataReader
    calendar: TradingCalendar
    window_days: int = 63

    # Minimum required days for window. If between min_required_days and
    # window_days, we use available data with a warning. If below
    # min_required_days, we raise ValueError. Default allows ~87% tolerance.
    min_required_days: int = 55

    # Reference scales and weights for component scoring. These are
    # conservative defaults and may be calibrated using historical
    # backtests in later iterations.
    vol_ref: float = 0.02  # 2% daily volatility ~ mid-scale
    dd_ref: float = 0.20   # 20% drawdown ~ mid-scale
    trend_ref: float = 0.20  # -20% trend over window ~ mid-scale

    vol_weight: float = 0.4
    dd_weight: float = 0.4
    trend_weight: float = 0.2

    # Optional profile integration for weak_profile flag. When
    # ``profile_service`` and ``instrument_to_issuer`` are provided, the
    # model will query issuer profiles and set ``weak_profile`` based on
    # a weighted combination of volatility-, drawdown-, and
    # leverage-based risk flags.
    profile_service: ProfileServiceLike | None = None
    instrument_to_issuer: Callable[[str], str | None] | None = None
    weak_profile_threshold: float = 0.7

    # Weights used to aggregate profile risk flags into a single
    # ``weak_profile`` driver in [0, 1]. These are interpreted as
    # relative weights; they are renormalised internally so their sum is
    # 1.0 when computing the combined flag.
    weak_profile_weight_vol: float = 0.4
    weak_profile_weight_dd: float = 0.4
    weak_profile_weight_lev: float = 0.2

    def _compute_features(
        self, entity_id: str, as_of_date: date
    ) -> tuple[np.ndarray, np.ndarray, float]:
        """Return (log_returns, closes, max_drawdown) for the window.

        Raises ValueError if there is insufficient price history.
        """

        if self.window_days <= 0:
            raise ValueError("window_days must be positive")

        # Find trading days in a broad range then take the last N.
        search_start = as_of_date - timedelta(days=self.window_days * 3)
        trading_days = self.calendar.trading_days_between(search_start, as_of_date)

        # Check minimum threshold
        if len(trading_days) < self.min_required_days:
            raise ValueError(
                f"Not enough trading history to compute stability: {len(trading_days)} days "
                f"available but require at least {self.min_required_days} for {entity_id} "
                f"ending at {as_of_date}"
            )

        # Log warning if between min and target
        if len(trading_days) < self.window_days:
            logger.warning(
                "Using %d trading days instead of target %d for %s ending at %s",
                len(trading_days),
                self.window_days,
                entity_id,
                as_of_date,
            )
            actual_window_days = len(trading_days)
        else:
            actual_window_days = self.window_days

        window_days = trading_days[-actual_window_days:]
        start_date = window_days[0]

        df = self.data_reader.read_prices([entity_id], start_date, as_of_date)
        if df.empty or len(df) < self.min_required_days:
            raise ValueError(
                f"Insufficient price rows ({len(df)}) for {entity_id} between "
                f"{start_date} and {as_of_date}. Need at least {self.min_required_days}."
            )

        df_sorted = df.sort_values(["trade_date"]).reset_index(drop=True)
        df_window = df_sorted.tail(actual_window_days)
        closes = df_window["close"].astype(float).to_numpy()

        if closes.shape[0] != actual_window_days:
            raise ValueError(
                "Price history length does not match expected window size: "
                f"{closes.shape[0]} != {actual_window_days}"
            )

        # Log returns; first element = 0.0.
        log_rets = np.zeros_like(closes, dtype=float)
        log_rets[1:] = np.log(closes[1:] / closes[:-1])

        # Max drawdown over the window.
        running_max = np.maximum.accumulate(closes)
        drawdowns = closes / running_max - 1.0
        max_dd = float(drawdowns.min())  # negative value

        return log_rets, closes, max_dd

    def _score_components(
        self, log_rets: np.ndarray, closes: np.ndarray, max_dd: float
    ) -> dict[str, float]:
        """Compute component scores in [0, 100] from raw features."""

        # Realised volatility of daily log returns.
        sigma = float(np.std(log_rets[1:], ddof=1)) if log_rets.shape[0] > 1 else 0.0

        # Simple price trend over the window.
        if closes[0] > 0.0:
            trend = float((closes[-1] - closes[0]) / closes[0])
        else:
            trend = 0.0

        def clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
            return max(lo, min(hi, value))

        # Volatility score: 0 for zero vol, ~50 around vol_ref, up to 100.
        vol_score = 0.0
        if self.vol_ref > 0.0:
            vol_score = clamp((sigma / self.vol_ref) * 50.0)

        # Drawdown score: use magnitude of max_dd (which is negative).
        dd_score = 0.0
        dd_mag = abs(max_dd)
        if self.dd_ref > 0.0:
            dd_score = clamp((dd_mag / self.dd_ref) * 50.0)

        # Trend score: penalise negative trends; positive trend gets 0.
        trend_score = 0.0
        if trend < 0.0 and self.trend_ref > 0.0:
            trend_score = clamp((abs(trend) / self.trend_ref) * 50.0)

        components = {
            "vol_score": vol_score,
            "dd_score": dd_score,
            "trend_score": trend_score,
            "sigma": sigma,
            "max_drawdown": max_dd,
            "trend": trend,
        }
        return components

    def _combine_overall(self, components: dict[str, float]) -> float:
        """Combine component scores into an overall Soft Target Index."""

        vol_score = components.get("vol_score", 0.0)
        dd_score = components.get("dd_score", 0.0)
        trend_score = components.get("trend_score", 0.0)

        total_weight = self.vol_weight + self.dd_weight + self.trend_weight
        if total_weight <= 0.0:
            # Fallback to simple average if weights are misconfigured.
            return (vol_score + dd_score + trend_score) / 3.0

        overall = (
            self.vol_weight * vol_score
            + self.dd_weight * dd_score
            + self.trend_weight * trend_score
        ) / total_weight
        return float(max(0.0, min(100.0, overall)))

    def _infer_weak_profile(self, as_of_date: date, entity_type: str, entity_id: str) -> bool:
        """Infer ``weak_profile`` from issuer profile risk flags, if available.

        For now this uses a simple threshold on a weighted combination of
        volatility-, drawdown-, and leverage-based profile risk flags
        (``vol_flag``, ``dd_flag``, and ``leverage_flag``) computed over a
        recent window. The weights are configurable via
        ``weak_profile_weight_*`` fields and are renormalised internally
        so their sum is 1.0 when aggregating the flags.
        """

        if self.profile_service is None or self.instrument_to_issuer is None:
            return False

        if entity_type != "INSTRUMENT":
            # Profile integration for non-instrument entities will be
            # added when those entity types are supported.
            return False

        issuer_id = self.instrument_to_issuer(entity_id)
        if issuer_id is None:
            logger.warning(
                "BasicPriceStabilityModel._infer_weak_profile: no issuer mapping for instrument %s",
                entity_id,
            )
            return False

        try:
            snapshot = self.profile_service.get_snapshot(issuer_id, as_of_date)
        except Exception:  # pragma: no cover - defensive
            # Profile failures should not break STAB scoring; fall back to
            # weak_profile=False and log the issue for inspection.
            logger.exception(
                "BasicPriceStabilityModel._infer_weak_profile: failed to load profile "
                "for issuer_id=%s as_of=%s",
                issuer_id,
                as_of_date,
            )
            return False

        flags = snapshot.risk_flags or {}
        vol_flag = float(flags.get("vol_flag", 0.0))
        dd_flag = float(flags.get("dd_flag", 0.0))
        lev_flag = float(flags.get("leverage_flag", 0.0))

        w_vol = self.weak_profile_weight_vol
        w_dd = self.weak_profile_weight_dd
        w_lev = self.weak_profile_weight_lev
        weight_sum = w_vol + w_dd + w_lev

        if weight_sum <= 0.0:
            # Misconfigured weights; fall back to no weak_profile signal.
            return False

        combined = (
            w_vol * vol_flag
            + w_dd * dd_flag
            + w_lev * lev_flag
        ) / weight_sum

        return combined >= self.weak_profile_threshold

    def _classify(self, overall_score: float) -> SoftTargetClass:
        """Map overall Soft Target Index into a SoftTargetClass."""

        if overall_score < 30.0:
            return SoftTargetClass.STABLE
        if overall_score < 45.0:
            return SoftTargetClass.WATCH
        if overall_score < 60.0:
            return SoftTargetClass.FRAGILE
        if overall_score < 75.0:
            return SoftTargetClass.TARGETABLE
        return SoftTargetClass.BREAKER

    def score(
        self, as_of_date: date, entity_type: str, entity_id: str
    ) -> tuple[StabilityVector, SoftTargetState]:
        """Score an entity and return (StabilityVector, SoftTargetState).

        Currently only supports ``entity_type="INSTRUMENT"``. Other
        entity types will be added in later iterations when the
        corresponding data sources are available.
        """

        if entity_type != "INSTRUMENT":
            raise NotImplementedError(
                f"BasicPriceStabilityModel only supports entity_type='INSTRUMENT', "
                f"got {entity_type!r}"
            )

        log_rets, closes, max_dd = self._compute_features(entity_id, as_of_date)
        components = self._score_components(log_rets, closes, max_dd)
        overall_score = self._combine_overall(components)
        soft_class = self._classify(overall_score)

        metadata = {
            "window_days": self.window_days,
        }

        vector = StabilityVector(
            as_of_date=as_of_date,
            entity_type=entity_type,
            entity_id=entity_id,
            components={k: float(v) for k, v in components.items()},
            overall_score=float(overall_score),
            metadata=metadata,
        )

        # Map components into SoftTargetState breakdown fields. We align
        # instability with vol_score, high_fragility with dd_score, and
        # complacent_pricing with trend_score. The weak_profile flag is
        # derived from issuer profile risk flags when profile integration
        # is configured.
        instability = float(components["vol_score"])
        high_fragility = float(components["dd_score"])
        complacent_pricing = float(components["trend_score"])

        weak_profile = self._infer_weak_profile(as_of_date, entity_type, entity_id)

        state = SoftTargetState(
            as_of_date=as_of_date,
            entity_type=entity_type,
            entity_id=entity_id,
            soft_target_class=soft_class,
            soft_target_score=float(overall_score),
            weak_profile=weak_profile,
            instability=instability,
            high_fragility=high_fragility,
            complacent_pricing=complacent_pricing,
            metadata=metadata,
        )

        logger.info(
            "BasicPriceStabilityModel.score: date=%s entity_type=%s entity_id=%s "
            "class=%s score=%.2f",
            as_of_date,
            entity_type,
            entity_id,
            soft_class.value,
            overall_score,
        )

        return vector, state
