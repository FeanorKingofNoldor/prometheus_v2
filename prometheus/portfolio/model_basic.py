"""Prometheus v2 – Basic long-only portfolio model.

This module implements a simple long-only portfolio construction model
for equity books using UniverseEngine outputs. It is not a full
mean-variance optimiser; instead it:

- Normalises universe ranking scores into weights.
- Applies per-name max-weight caps from :class:`PortfolioConfig`.
- Computes simple sector and fragility exposure diagnostics.

The goal is to provide a deterministic, inspectable baseline that can be
replaced with a more sophisticated optimisation model later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List

import math

from prometheus.core.database import get_db_manager
from prometheus.core.logging import get_logger
from prometheus.universe.engine import UniverseMember, UniverseStorage
from prometheus.fragility.storage import FragilityStorage
from prometheus.fragility.types import FragilityClass
from prometheus.portfolio.scenario_risk import compute_portfolio_scenario_pnl

from .config import PortfolioConfig
from .types import RiskReport, TargetPortfolio


logger = get_logger(__name__)


@dataclass
class BasicLongOnlyPortfolioModel:
    """Basic long-only portfolio model built from universe members.

    This model assumes a single equity universe per region and constructs
    weights by normalising :class:`UniverseMember.score` values, subject
    to a per-instrument max-weight cap.
    """

    universe_storage: UniverseStorage
    config: PortfolioConfig
    universe_id: str

    # Internal cache of the last set of universe members used for
    # optimisation. PortfolioEngine relies on this to persist weights via
    # PortfolioStorage without re-querying the universe.
    _last_members: List[UniverseMember] = field(default_factory=list, init=False)

    def _load_members(self, as_of_date: date) -> List[UniverseMember]:
        members = self.universe_storage.get_universe(
            as_of_date=as_of_date,
            universe_id=self.universe_id,
            entity_type="INSTRUMENT",
            included_only=True,
        )
        self._last_members = members
        return members

    def build_target_portfolio(self, portfolio_id: str, as_of_date: date) -> TargetPortfolio:  # type: ignore[override]
        members = self._load_members(as_of_date)
        if not members:
            logger.info(
                "BasicLongOnlyPortfolioModel: no universe members for %s on %s",
                portfolio_id,
                as_of_date,
            )
            return TargetPortfolio(
                portfolio_id=portfolio_id,
                as_of_date=as_of_date,
                weights={},
                expected_return=0.0,
                expected_volatility=0.0,
                risk_metrics={},
                factor_exposures={},
                constraints_status={},
                metadata={"risk_model_id": self.config.risk_model_id},
            )

        # Base weights from non-negative scores.
        raw_scores = [max(0.0, m.score) for m in members]
        total_score = sum(raw_scores)
        if total_score <= 0.0:
            n = len(members)
            base_weights = [1.0 / n for _ in members]
        else:
            base_weights = [s / total_score for s in raw_scores]

        # Apply per-name max-weight cap and renormalise if needed. We
        # ensure that the final weights both sum to 1.0 and do not exceed
        # ``w_max``.
        w_max = max(0.0, self.config.per_instrument_max_weight)
        if w_max <= 0.0 or w_max >= 1.0:
            final_weights = base_weights
            any_clipped = False
        else:
            remaining_idx = list(range(len(base_weights)))
            remaining_mass = 1.0
            remaining_base_sum = sum(base_weights)
            final_weights = [0.0 for _ in base_weights]
            any_clipped = False

            # Iteratively assign weight to names that would breach the cap
            # under the current remaining mass, then redistribute the
            # remainder among the rest.
            while remaining_idx and remaining_mass > 0.0 and remaining_base_sum > 0.0:
                updated = False
                for i in list(remaining_idx):
                    # Provisional weight if we distributed remaining_mass
                    # proportionally to base_weights over remaining_idx.
                    w_i = base_weights[i] / remaining_base_sum * remaining_mass
                    if w_i > w_max:
                        final_weights[i] = w_max
                        remaining_mass -= w_max
                        remaining_base_sum -= base_weights[i]
                        remaining_idx.remove(i)
                        any_clipped = True
                        updated = True
                if not updated:
                    # No more names breach the cap under proportional
                    # allocation; assign the remaining mass proportionally
                    # and stop.
                    for i in remaining_idx:
                        final_weights[i] = base_weights[i] / remaining_base_sum * remaining_mass
                    remaining_mass = 0.0
                    break

            # Safety: if due to numerical issues we ended up with no
            # assigned weights, fall back to equal weighting.
            total_final = sum(final_weights)
            if total_final <= 0.0:
                n = len(members)
                final_weights = [1.0 / n for _ in members]
            else:
                final_weights = [w / total_final for w in final_weights]

        weights: Dict[str, float] = {
            m.entity_id: float(w) for m, w in zip(members, final_weights)
        }

        # Diagnostics: sector and fragility exposures.
        sector_exposures: Dict[str, float] = {}
        fragile_weight = 0.0
        total_weight = 0.0
        for m, w in zip(members, final_weights):
            sector = str(m.reasons.get("sector", "UNKNOWN"))
            sector_exposures[sector] = sector_exposures.get(sector, 0.0) + float(w)

            soft_class = str(m.reasons.get("soft_target_class", ""))
            weak_profile = bool(m.reasons.get("weak_profile", False))
            is_fragile = soft_class in {"FRAGILE", "TARGETABLE", "BREAKER"} or weak_profile
            if is_fragile:
                fragile_weight += float(w)
            total_weight += float(w)

        gross_exposure = sum(abs(w) for w in final_weights)
        net_exposure = sum(final_weights)

        frag_limit = self.config.fragility_exposure_limit
        constraints_status = {
            "per_instrument_max_weight_binding": any_clipped,
            "fragility_exposure_within_limit": fragile_weight <= frag_limit,
        }

        risk_metrics = {
            "gross_exposure": gross_exposure,
            "net_exposure": net_exposure,
            "fragility_exposure": fragile_weight,
            "num_names": float(len(members)),
        }

        # Compute simple factor-based risk metrics using historical factor
        # exposures and returns. If factor data is unavailable, this
        # gracefully falls back to zero volatility and no factor
        # exposures.
        factor_exposures: Dict[str, float] = {}
        expected_volatility: float = 0.0
        risk_window_days: int = 0

        try:
            factor_exposures, expected_volatility, risk_window_days = self._compute_factor_risk(
                as_of_date=as_of_date,
                members=members,
                weights_vector=final_weights,
            )
        except Exception:  # pragma: no cover - defensive
            # Factor-risk computation is best-effort; failures should not
            # break portfolio construction.
            logger.exception(
                "BasicLongOnlyPortfolioModel: error computing factor-based risk; "
                "continuing with placeholder risk metrics",
            )
            factor_exposures = {}
            expected_volatility = 0.0
            risk_window_days = 0

        if risk_window_days > 0:
            risk_metrics["risk_window_days"] = float(risk_window_days)
        risk_metrics["expected_volatility"] = float(expected_volatility)

        # For expected return we continue to treat the universe scores as a
        # proxy, independent of the risk model used.
        expected_return = float(sum(w * s for w, s in zip(final_weights, raw_scores)))

        # If we could not compute factor exposures, fall back to
        # sector-based exposures so callers still see a breakdown.
        effective_exposures = factor_exposures or sector_exposures

        return TargetPortfolio(
            portfolio_id=portfolio_id,
            as_of_date=as_of_date,
            weights=weights,
            expected_return=expected_return,
            expected_volatility=expected_volatility,
            risk_metrics=risk_metrics,
            factor_exposures=effective_exposures,
            constraints_status=constraints_status,
            metadata={
                "risk_model_id": self.config.risk_model_id,
            },
        )

    def build_risk_report(
        self,
        portfolio_id: str,
        as_of_date: date,
        target: TargetPortfolio | None = None,
    ) -> RiskReport | None:  # type: ignore[override]
        """Return a basic risk report derived from the target portfolio.

        For this iteration the risk report mirrors the risk_metrics and
        factor_exposures contained in the :class:`TargetPortfolio`.
        """

        if target is None:
            target = self.build_target_portfolio(portfolio_id, as_of_date)

        exposures: Dict[str, float] = {}
        exposures.update(target.factor_exposures)

        # Augment scalar risk metrics with fragility-based aggregates
        # derived from the latest ``fragility_measures`` per instrument.
        risk_metrics = dict(target.risk_metrics)
        frag_metrics, frag_weight_by_class = self._compute_fragility_metrics(
            as_of_date=as_of_date,
            weights=target.weights,
        )
        risk_metrics.update(frag_metrics)

        metadata: Dict[str, object] = {"risk_model_id": self.config.risk_model_id}
        if frag_weight_by_class:
            metadata["fragility_weight_by_class"] = frag_weight_by_class

        # Optionally compute scenario-based P&L for configured scenario
        # sets. This is deliberately conservative: if anything fails, the
        # rest of the risk report remains intact.
        scenario_pnl: Dict[str, float] = {}
        db_manager = getattr(self.universe_storage, "db_manager", None)
        if db_manager is not None and self.config.scenario_risk_scenario_set_ids:
            for scenario_set_id in self.config.scenario_risk_scenario_set_ids:
                try:
                    result = compute_portfolio_scenario_pnl(
                        db_manager=db_manager,
                        scenario_set_id=scenario_set_id,
                        as_of_date=as_of_date,
                        weights=target.weights,
                    )
                except Exception:  # pragma: no cover - defensive
                    logger.exception(
                        "BasicLongOnlyPortfolioModel.build_risk_report: scenario risk computation "
                        "failed for portfolio_id=%s scenario_set_id=%s as_of=%s",
                        portfolio_id,
                        scenario_set_id,
                        as_of_date,
                    )
                    continue

                scenario_pnl.update(result.scenario_pnl)
                for key, value in result.summary_metrics.items():
                    metric_key = f"{scenario_set_id}:{key}"
                    risk_metrics[metric_key] = float(value)

        return RiskReport(
            portfolio_id=portfolio_id,
            as_of_date=as_of_date,
            exposures=exposures,
            risk_metrics=risk_metrics,
            scenario_pnl=scenario_pnl,
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Internal helpers – factor-based risk and fragility
    # ------------------------------------------------------------------

    def _compute_fragility_metrics(
        self,
        as_of_date: date,
        weights: Dict[str, float],
    ) -> tuple[Dict[str, float], Dict[str, float]]:
        """Compute portfolio-level fragility aggregates.

        Returns a tuple ``(metrics, weight_by_class)`` where ``metrics``
        contains scalar values that can be stored in
        ``portfolio_risk_reports.risk_metrics`` and ``weight_by_class`` is
        a mapping from :class:`FragilityClass` value to aggregate absolute
        weight used for metadata/monitoring.
        """

        if not weights:
            return {}, {}

        # Use the same DatabaseManager backing the universe storage to
        # avoid creating a separate connection manager here.
        db_manager = getattr(self.universe_storage, "db_manager", None)
        if db_manager is None:
            return {}, {}

        storage = FragilityStorage(db_manager=db_manager)
        instrument_ids = [inst_id for inst_id, w in weights.items() if float(w) != 0.0]
        measures = storage.get_latest_measures_for_entities("INSTRUMENT", instrument_ids)
        if not measures:
            return {}, {}

        total_abs_weight = 0.0
        frag_weight_total = 0.0
        frag_weight_by_class: Dict[str, float] = {}
        score_weighted_abs = 0.0
        score_max = 0.0
        num_with_measure = 0

        for inst_id, w in weights.items():
            measure = measures.get(inst_id)
            if measure is None:
                continue
            abs_w = abs(float(w))
            if abs_w <= 0.0:
                continue

            total_abs_weight += abs_w
            num_with_measure += 1

            score = float(measure.fragility_score)
            score_weighted_abs += score * abs_w
            if score > score_max:
                score_max = score

            if measure.class_label is not FragilityClass.NONE:
                frag_weight_total += abs_w

            cls_key = measure.class_label.value
            frag_weight_by_class[cls_key] = frag_weight_by_class.get(cls_key, 0.0) + abs_w

        if total_abs_weight <= 0.0:
            return {}, frag_weight_by_class

        metrics: Dict[str, float] = {}
        metrics["fragility_weight_total"] = frag_weight_total
        metrics["fragility_weight_fraction"] = frag_weight_total / total_abs_weight
        metrics["fragility_score_weighted_mean"] = score_weighted_abs / total_abs_weight
        metrics["fragility_score_max"] = score_max
        metrics["fragility_num_names_with_measure"] = float(num_with_measure)

        return metrics, frag_weight_by_class

    def _compute_factor_risk(
        self,
        as_of_date: date,
        members: List[UniverseMember],
        weights_vector: List[float],
    ) -> tuple[Dict[str, float], float, int]:
        """Compute simple factor-based exposures and portfolio volatility.

        The implementation uses ``instrument_factors_daily`` for
        per-instrument factor exposures and ``factors_daily`` for factor
        returns, both in the historical database. Correlations between
        factors are approximated as zero, yielding::

            sigma_portfolio = sqrt(sum_f (E_f * sigma_f) ** 2)

        where ``E_f`` is the portfolio exposure to factor ``f`` and
        ``sigma_f`` is the realised volatility of that factor over a
        window determined by any correlation panel that covers
        ``as_of_date`` (or a 63-day fallback window).

        The function is deliberately defensive: if any step fails or
        there is insufficient data, it returns empty exposures and
        zero volatility.
        """

        if not members or not weights_vector:
            return {}, 0.0, 0

        # Map instrument_id -> weight for instruments with non-zero weight.
        weights_by_instrument: Dict[str, float] = {}
        for m, w in zip(members, weights_vector):
            w_f = float(w)
            if abs(w_f) > 0.0:
                weights_by_instrument[m.entity_id] = w_f

        if not weights_by_instrument:
            return {}, 0.0, 0

        try:
            db_manager = get_db_manager()
        except Exception:  # pragma: no cover - defensive
            logger.warning(
                "BasicLongOnlyPortfolioModel._compute_factor_risk: failed to initialise DatabaseManager; "
                "skipping factor risk computation",
            )
            return {}, 0.0, 0

        # Query factor exposures and returns from the historical DB. Any
        # errors here should cause a graceful fallback.
        try:
            with db_manager.get_historical_connection() as conn:  # type: ignore[attr-defined]
                cursor = conn.cursor()
                try:
                    # 1) Load per-instrument factor exposures for the date.
                    sql_exposures = """
                        SELECT instrument_id, factor_id, exposure
                        FROM instrument_factors_daily
                        WHERE trade_date = %s
                          AND instrument_id = ANY(%s)
                    """
                    cursor.execute(sql_exposures, (as_of_date, list(weights_by_instrument.keys())))
                    rows = cursor.fetchall()

                    if not rows:
                        return {}, 0.0, 0

                    # Aggregate portfolio factor exposures E_f.
                    factor_exposures: Dict[str, float] = {}
                    factor_ids: set[str] = set()
                    for instrument_id, factor_id, exposure in rows:
                        w = weights_by_instrument.get(instrument_id)
                        if w is None or w == 0.0:
                            continue
                        f_id = str(factor_id)
                        factor_ids.add(f_id)
                        factor_exposures[f_id] = factor_exposures.get(f_id, 0.0) + float(w) * float(exposure)

                    if not factor_exposures:
                        return {}, 0.0, 0

                    # 2) Determine risk window from correlation_panels, if
                    # available, otherwise fall back to a 63-day calendar
                    # window ending at as_of_date.
                    sql_panel = """
                        SELECT panel_id, start_date, end_date
                        FROM correlation_panels
                        WHERE start_date <= %s
                          AND end_date >= %s
                        ORDER BY (end_date - start_date) ASC
                        LIMIT 1
                    """
                    cursor.execute(sql_panel, (as_of_date, as_of_date))
                    panel_row = cursor.fetchone()

                    if panel_row:
                        _panel_id, start_date, end_date = panel_row
                        # Ensure the window is not empty and is bounded by
                        # as_of_date on the upper side.
                        if end_date > as_of_date:
                            end_date = as_of_date
                        if start_date >= end_date:
                            start_date = as_of_date - timedelta(days=63)
                    else:
                        start_date = as_of_date - timedelta(days=63)
                        end_date = as_of_date

                    # 3) Load factor returns over the chosen window.
                    sql_factors = """
                        SELECT factor_id, trade_date, value
                        FROM factors_daily
                        WHERE trade_date BETWEEN %s AND %s
                          AND factor_id = ANY(%s)
                    """
                    cursor.execute(sql_factors, (start_date, end_date, list(factor_ids)))
                    factor_rows = cursor.fetchall()
                finally:
                    cursor.close()
        except Exception:  # pragma: no cover - defensive
            logger.exception(
                "BasicLongOnlyPortfolioModel._compute_factor_risk: error loading factor data; "
                "skipping factor risk computation",
            )
            return {}, 0.0, 0

        if not factor_rows:
            return {}, 0.0, 0

        # Group factor returns by factor_id and compute realised
        # volatility sigma_f for each.
        returns_by_factor: Dict[str, list[float]] = {}
        for factor_id, _trade_date, value in factor_rows:
            f_id = str(factor_id)
            returns_by_factor.setdefault(f_id, []).append(float(value))

        sigma_by_factor: Dict[str, float] = {}
        for f_id, values in returns_by_factor.items():
            n = len(values)
            if n < 2:
                continue
            mean_val = sum(values) / n
            var = sum((v - mean_val) ** 2 for v in values) / (n - 1)
            sigma = math.sqrt(var) if var > 0.0 else 0.0
            sigma_by_factor[f_id] = sigma

        if not sigma_by_factor:
            return {}, 0.0, 0

        # Portfolio variance under diagonal factor covariance
        # approximation.
        variance = 0.0
        for f_id, exposure in factor_exposures.items():
            sigma = sigma_by_factor.get(f_id)
            if sigma is None or sigma <= 0.0:
                continue
            contribution = exposure * sigma
            variance += contribution * contribution

        if variance <= 0.0:
            return {}, 0.0, 0

        window_days = (end_date - start_date).days + 1
        volatility = math.sqrt(variance)

        return factor_exposures, volatility, max(window_days, 0)
