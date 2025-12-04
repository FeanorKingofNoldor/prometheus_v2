"""Prometheus v2 – Synthetic Scenario Engine.

This module implements a minimal Synthetic Scenario Engine capable of
constructing historical-window scenario sets from realised prices.

The design closely follows spec 170 but focuses on a single scenario
family (Type A – historical windows) for this iteration.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd

from prometheus.core.database import DatabaseManager
from prometheus.core.logging import get_logger
from prometheus.data.reader import DataReader

from .storage import ScenarioPathRow, ScenarioStorage
from .types import ScenarioRequest, ScenarioSetRef


logger = get_logger(__name__)


@dataclass
class SyntheticScenarioEngine:
    """Generate and manage synthetic scenario sets.

    For this iteration, we support several simple numeric scenario
    families:

    - ``HISTORICAL``: contiguous historical windows (Type A).
    - ``BOOTSTRAP``: day-level bootstrap of returns, ignoring temporal
      ordering but preserving cross-sectional structure.
    - ``STRESSED``: stress scenarios built from the worst historical
      days (e.g. large negative cross-sectional returns), optionally
      scaled via ``request.generator_spec``.

    All variants operate on simple daily returns from ``prices_daily``
    for instruments in the requested markets.
    """

    db_manager: DatabaseManager
    data_reader: DataReader

    def __post_init__(self) -> None:
        self._storage = ScenarioStorage(db_manager=self.db_manager)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_scenario_set(self, request: ScenarioRequest) -> ScenarioSetRef:
        """Generate and persist a scenario set described by ``request``.

        Supported categories (case-insensitive):

        - ``HISTORICAL``: contiguous historical windows.
        - ``BOOTSTRAP``: day-level bootstrap of return rows.
        - ``STRESSED``: stress scenarios built from worst historical days,
          optionally scaled via ``request.generator_spec``.
        """

        if request.horizon_days <= 0:
            msg = "horizon_days must be positive"
            raise ValueError(msg)
        if request.num_paths <= 0:
            msg = "num_paths must be positive"
            raise ValueError(msg)
        if not request.markets:
            msg = "markets must not be empty"
            raise ValueError(msg)

        category = request.category.upper()
        if category not in {"HISTORICAL", "BOOTSTRAP", "STRESSED"}:
            msg = f"Unsupported scenario category: {request.category!r}"
            raise NotImplementedError(msg)

        # Create scenario_set row first so we have an identifier for
        # subsequent path rows.
        set_ref = self._storage.create_scenario_set(request=request, created_by="system")

        instrument_ids = self._load_instruments_for_markets(request.markets)
        if not instrument_ids:
            logger.warning(
                "SyntheticScenarioEngine.generate_scenario_set: no instruments for markets %s",
                request.markets,
            )
            return set_ref

        rows: List[ScenarioPathRow] = []
        H = request.horizon_days
        num_paths = request.num_paths

        rng = np.random.default_rng()

        if category == "HISTORICAL":
            windows, instrument_ids = self._build_historical_windows(
                instrument_ids=instrument_ids,
                horizon_days=request.horizon_days,
                base_start=request.base_date_start,
                base_end=request.base_date_end,
            )

            if not windows:
                logger.warning(
                    "SyntheticScenarioEngine.generate_scenario_set: no viable windows for request %s",
                    request.name,
                )
                return set_ref

            # Sample with replacement over contiguous windows.
            window_indices = rng.integers(low=0, high=len(windows), size=num_paths)

            for scenario_id, window_idx in enumerate(window_indices):
                window_returns = windows[window_idx]
                # Ensure window is (H, N) in time-major order.
                if window_returns.shape[0] < H:
                    continue

                for h in range(H):
                    row_returns = window_returns[h]
                    for inst_idx, inst_id in enumerate(instrument_ids):
                        r = float(row_returns[inst_idx])
                        rows.append(
                            ScenarioPathRow(
                                scenario_id=scenario_id,
                                horizon_index=h + 1,  # use 1..H; 0 reserved for baseline
                                instrument_id=inst_id,
                                factor_id="__INSTRUMENT__",
                                macro_id="__NONE__",
                                return_value=r,
                            )
                        )

                # Insert baseline horizon_index=0 rows with zero return.
                for inst_id in instrument_ids:
                    rows.append(
                        ScenarioPathRow(
                            scenario_id=scenario_id,
                            horizon_index=0,
                            instrument_id=inst_id,
                            factor_id="__INSTRUMENT__",
                            macro_id="__NONE__",
                            return_value=0.0,
                        )
                    )

        else:
            # For BOOTSTRAP/STRESSED, work directly with the full returns
            # panel and construct paths by sampling rows.
            returns, instrument_ids = self._build_returns_panel(
                instrument_ids=instrument_ids,
                base_start=request.base_date_start,
                base_end=request.base_date_end,
            )
            if returns.size == 0:
                logger.warning(
                    "SyntheticScenarioEngine.generate_scenario_set: empty returns panel for request %s",
                    request.name,
                )
                return set_ref

            num_days, _ = returns.shape

            # Optional stress configuration for STRESSED category.
            stress_q = 0.1
            stress_scale = 1.5
            if request.generator_spec is not None:
                stress_q = float(request.generator_spec.get("stress_quantile", stress_q))
                stress_scale = float(request.generator_spec.get("stress_scale", stress_scale))

            if category == "STRESSED":
                # Score days by cross-sectional mean return and focus on the
                # lowest quantile (worst days).
                day_scores = returns.mean(axis=1)
                q = max(min(stress_q, 0.5), 0.0)
                threshold = np.quantile(day_scores, q) if 0.0 < q < 1.0 else np.min(day_scores)
                candidate_indices = np.where(day_scores <= threshold)[0]
                if candidate_indices.size == 0:
                    candidate_indices = np.arange(num_days)
            else:  # BOOTSTRAP
                candidate_indices = np.arange(num_days)

            for scenario_id in range(num_paths):
                # Sample H days with replacement from candidate_indices.
                day_indices = rng.integers(low=0, high=candidate_indices.size, size=H)
                for h, idx in enumerate(day_indices, start=1):
                    row_returns = returns[candidate_indices[idx], :]
                    if category == "STRESSED":
                        row_returns = row_returns * stress_scale
                    for inst_idx, inst_id in enumerate(instrument_ids):
                        r = float(row_returns[inst_idx])
                        rows.append(
                            ScenarioPathRow(
                                scenario_id=scenario_id,
                                horizon_index=h,
                                instrument_id=inst_id,
                                factor_id="__INSTRUMENT__",
                                macro_id="__NONE__",
                                return_value=r,
                            )
                        )

                for inst_id in instrument_ids:
                    rows.append(
                        ScenarioPathRow(
                            scenario_id=scenario_id,
                            horizon_index=0,
                            instrument_id=inst_id,
                            factor_id="__INSTRUMENT__",
                            macro_id="__NONE__",
                            return_value=0.0,
                        )
                    )

        self._storage.save_scenario_paths(set_ref.scenario_set_id, rows)

        logger.info(
            "SyntheticScenarioEngine.generate_scenario_set: id=%s category=%s H=%d paths=%d instruments=%d",
            set_ref.scenario_set_id,
            request.category,
            request.horizon_days,
            request.num_paths,
            len(instrument_ids),
        )

        return set_ref

    def list_scenario_sets(self, category: str | None = None) -> List[ScenarioSetRef]:
        """Return scenario sets, optionally filtered by category."""

        return self._storage.list_scenario_sets(category=category)

    def get_scenario_set_metadata(self, scenario_set_id: str) -> Dict[str, object]:
        """Return raw metadata for a scenario set."""

        return self._storage.get_scenario_set_metadata(scenario_set_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_instruments_for_markets(self, markets: List[str]) -> List[str]:
        """Return instrument_ids for the given markets from runtime DB."""

        sql = """
            SELECT instrument_id
            FROM instruments
            WHERE market_id = ANY(%s)
              AND status = 'ACTIVE'
            ORDER BY instrument_id
        """

        with self.db_manager.get_runtime_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (list(markets),))
                rows = cursor.fetchall()
            finally:
                cursor.close()

        return [inst_id for (inst_id,) in rows]

    def _build_historical_windows(
        self,
        instrument_ids: List[str],
        horizon_days: int,
        base_start: date | None,
        base_end: date | None,
    ) -> tuple[List[np.ndarray], List[str]]:
        """Construct contiguous windows of simple returns.

        Returns
        -------
        windows:
            List of numpy arrays with shape (H, N) where H is the horizon
            length and N is the number of instruments.
        instrument_ids:
            The ordered list of instrument_ids corresponding to the columns
            in each window. This may be a strict subset of the input
            ``instrument_ids`` when some requested instruments have no
            price history in the requested window.
        """

        returns, aligned_instrument_ids = self._build_returns_panel(
            instrument_ids=instrument_ids,
            base_start=base_start,
            base_end=base_end,
        )
        if returns.size == 0:
            return [], []

        num_days, num_instruments = returns.shape
        if num_instruments == 0 or num_days < horizon_days:
            return [], []

        windows: List[np.ndarray] = []
        # Build all possible contiguous windows of length horizon_days.
        for start_idx in range(0, num_days - horizon_days + 1):
            window = returns[start_idx : start_idx + horizon_days, :]
            # Shape (H, N)
            windows.append(window)

        return windows, aligned_instrument_ids

    def _build_returns_panel(
        self,
        instrument_ids: List[str],
        base_start: date | None,
        base_end: date | None,
    ) -> tuple[np.ndarray, List[str]]:
        """Return a panel of simple daily returns for instruments.

        Returns
        -------
        returns:
            2D numpy array with shape (T, N) where T is the number of
            trading days with non-null returns and N is the number of
            instruments with price history.
        instrument_ids:
            The ordered list of instrument_ids corresponding to the columns
            in ``returns``.
        """

        if base_end is None:
            msg = "base_date_end must be provided for scenario generation"
            raise ValueError(msg)
        if base_start is None:
            base_start = base_end

        df = self.data_reader.read_prices(
            instrument_ids=instrument_ids,
            start_date=base_start,
            end_date=base_end,
        )
        if df.empty:
            return np.zeros((0, 0), dtype=float), []

        prices = (
            df[["instrument_id", "trade_date", "close"]]
            .pivot(index="trade_date", columns="instrument_id", values="close")
            .sort_index()
        )
        if prices.empty:
            return np.zeros((0, 0), dtype=float), []

        aligned_instrument_ids = [str(col) for col in prices.columns]

        returns = prices.pct_change().dropna(how="all")
        if returns.empty:
            return np.zeros((0, 0), dtype=float), []

        values = returns.to_numpy(dtype=float)
        return values, aligned_instrument_ids
