"""Prometheus v2 – Run execution plan for a portfolio via IBKR broker.

This script bridges the daily portfolio targets produced by the
Portfolio & Risk Engine (``target_portfolios`` table) to the unified
execution bridge and a concrete broker implementation (Paper/Live
IBKR).

Initial focus is on PAPER mode for safe testing. LIVE mode wiring is
present but should be used with extreme care and typically in readonly
mode until fully validated.

Usage examples
--------------

Run a PAPER execution for the latest targets of a portfolio, allocating
100k of notional:

    python -m prometheus.scripts.run_execution_for_portfolio \
        --portfolio-id US_CORE_LONG_EQ \
        --mode PAPER \
        --notional 100000

Run for a specific date:

    python -m prometheus.scripts.run_execution_for_portfolio \
        --portfolio-id US_CORE_LONG_EQ \
        --mode PAPER \
        --notional 100000 \
        --as-of 2025-12-02

LIVE mode (readonly by default, no orders submitted):

    python -m prometheus.scripts.run_execution_for_portfolio \
        --portfolio-id US_CORE_LONG_EQ \
        --mode LIVE \
        --readonly \
        --notional 100000
"""

from __future__ import annotations

import argparse
from datetime import date
from typing import Dict, List, Optional, Sequence, Tuple

from prometheus.core.database import DatabaseManager, get_db_manager
from prometheus.core.logging import get_logger
from prometheus.execution.api import apply_execution_plan
from prometheus.execution.broker_factory import create_live_broker, create_paper_broker
from prometheus.execution.ibkr_config import IbkrGatewayType


logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers: parsing and DB access
# ---------------------------------------------------------------------------


def _parse_date(value: str) -> date:
    """Parse a YYYY-MM-DD date string for CLI arguments."""

    try:
        year, month, day = map(int, value.split("-"))
        return date(year, month, day)
    except Exception as exc:  # pragma: no cover - CLI validation
        raise argparse.ArgumentTypeError(f"Invalid date {value!r}, expected YYYY-MM-DD") from exc


def _find_latest_as_of(db_manager: DatabaseManager, portfolio_id: str) -> Optional[date]:
    """Return the most recent as_of_date for which targets exist.

    If no rows are present for the portfolio, returns None.
    """

    sql = """
        SELECT as_of_date
        FROM target_portfolios
        WHERE portfolio_id = %s
        ORDER BY as_of_date DESC
        LIMIT 1
    """

    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (portfolio_id,))
            row = cursor.fetchone()
        finally:
            cursor.close()

    if not row:
        return None

    as_of_date: date = row[0]
    return as_of_date


def _load_target_weights(
    db_manager: DatabaseManager,
    portfolio_id: str,
    as_of: date,
) -> Dict[str, float]:
    """Load target weights for a portfolio/date from target_portfolios.

    Returns a mapping ``instrument_id -> weight``. If no row is found,
    returns an empty dict.
    """

    sql = """
        SELECT target_positions
        FROM target_portfolios
        WHERE portfolio_id = %s
          AND as_of_date = %s
        ORDER BY created_at DESC
        LIMIT 1
    """

    with db_manager.get_runtime_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(sql, (portfolio_id, as_of))
            row = cursor.fetchone()
        finally:
            cursor.close()

    if not row:
        return {}

    positions = row[0]
    if not isinstance(positions, dict):
        logger.warning(
            "run_execution_for_portfolio: target_positions payload is not a dict for portfolio_id=%s as_of=%s",
            portfolio_id,
            as_of,
        )
        return {}

    raw_weights = positions.get("weights") or {}
    try:
        weights: Dict[str, float] = {str(k): float(v) for k, v in raw_weights.items()}
    except Exception as exc:  # pragma: no cover - defensive
        logger.error(
            "run_execution_for_portfolio: failed to parse weights for portfolio_id=%s as_of=%s: %s",
            portfolio_id,
            as_of,
            exc,
        )
        return {}

    return weights


def _load_latest_closes(
    db_manager: DatabaseManager,
    instrument_ids: List[str],
    as_of: date,
) -> Dict[str, float]:
    """Load latest close price on/before ``as_of`` for each instrument.

    Returns mapping ``instrument_id -> close``. Instruments without a
    price are omitted from the result.
    """

    if not instrument_ids:
        return {}

    sql = """
        SELECT instrument_id, trade_date, close
        FROM prices_daily
        WHERE instrument_id = ANY(%s)
          AND trade_date <= %s
        ORDER BY instrument_id ASC, trade_date DESC
    """

    prices: Dict[str, float] = {}

    try:
        with db_manager.get_historical_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (instrument_ids, as_of))
                rows = cursor.fetchall()
            finally:
                cursor.close()
    except Exception as exc:  # pragma: no cover - defensive
        logger.error(
            "run_execution_for_portfolio: failed to load prices from prices_daily: %s",
            exc,
            exc_info=True,
        )
        return {}

    for inst_id_db, trade_date, close in rows:
        inst = str(inst_id_db)
        # First row per instrument_id is the most recent because of ORDER BY.
        if inst not in prices:
            try:
                prices[inst] = float(close)
            except Exception:
                continue

    missing = sorted(set(instrument_ids) - set(prices.keys()))
    if missing:
        logger.warning(
            "run_execution_for_portfolio: missing prices for %d instruments on/before %s (e.g. %s)",
            len(missing),
            as_of,
            ", ".join(missing[:5]),
        )

    return prices


def _compute_target_quantities(
    weights: Dict[str, float],
    prices: Dict[str, float],
    notional: float,
) -> Dict[str, float]:
    """Convert weights + prices into absolute share quantities.

    For each instrument:

    - target_value = weight * notional
    - quantity = floor(target_value / price)

    Instruments with missing prices or non-positive quantities are
    skipped. Quantities are returned as floats but are always
    integer-valued.
    """

    from math import floor

    targets: Dict[str, float] = {}

    for inst_id, weight in weights.items():
        if weight <= 0.0:
            continue
        price = prices.get(inst_id)
        if price is None or price <= 0.0:
            continue

        target_value = notional * float(weight)
        qty = floor(target_value / float(price))
        if qty <= 0:
            continue

        targets[inst_id] = float(qty)

    if not targets:
        logger.warning(
            "run_execution_for_portfolio: no non-zero target quantities after sizing; check weights/prices/notional",
        )

    return targets


# ---------------------------------------------------------------------------
# Broker creation
# ---------------------------------------------------------------------------


def _create_broker(mode: str, readonly: bool) -> object:
    """Create a Live or Paper broker based on mode.

    PAPER mode always uses IB Gateway by default. LIVE mode is created in
    readonly mode unless explicitly disabled. This function returns a
    ``LiveBroker`` or ``PaperBroker`` instance.
    """

    mode_up = mode.upper()

    if mode_up == "PAPER":
        logger.info("Creating PaperBroker (IBKR paper trading)")
        return create_paper_broker(
            gateway_type=IbkrGatewayType.GATEWAY,
            client_id=1,
            readonly=False,
            auto_connect=True,
        )
    elif mode_up == "LIVE":
        logger.info("Creating LiveBroker (IBKR live account), readonly=%s", readonly)
        return create_live_broker(
            gateway_type=IbkrGatewayType.GATEWAY,
            client_id=1,
            readonly=readonly,
            auto_connect=True,
        )
    else:
        raise ValueError(f"Unsupported mode {mode!r}; expected PAPER or LIVE")


def _disconnect_broker(broker: object) -> None:
    """Best-effort disconnect for brokers that wrap an IbkrClient."""

    client = getattr(broker, "client", None)
    if client is not None:
        try:
            client.disconnect()
        except Exception:  # pragma: no cover - defensive
            logger.exception("run_execution_for_portfolio: error while disconnecting broker client")


# ---------------------------------------------------------------------------
# Main CLI
# ---------------------------------------------------------------------------


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Entry point for the run_execution_for_portfolio CLI."""

    parser = argparse.ArgumentParser(
        description=(
            "Apply an execution plan for a portfolio using IBKR PAPER/LIVE broker "
            "based on target_portfolios weights."
        ),
    )

    parser.add_argument(
        "--portfolio-id",
        type=str,
        required=True,
        help="Portfolio identifier (e.g. US_CORE_LONG_EQ)",
    )
    parser.add_argument(
        "--as-of",
        dest="as_of",
        type=_parse_date,
        required=False,
        help=(
            "As-of date for the snapshot (YYYY-MM-DD). If omitted, uses the latest "
            "available date in target_portfolios."
        ),
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["PAPER", "LIVE"],
        default="PAPER",
        help="Execution mode: PAPER (default) or LIVE",
    )
    parser.add_argument(
        "--notional",
        type=float,
        required=True,
        help="Total notional to allocate according to target weights (account currency)",
    )
    parser.add_argument(
        "--readonly",
        action="store_true",
        help=(
            "For LIVE mode: create broker in readonly mode (no order submission). "
            "Has no effect in PAPER mode and defaults to True when mode=LIVE."
        ),
    )

    args = parser.parse_args(argv)

    db_manager = get_db_manager()

    as_of: Optional[date] = args.as_of
    if as_of is None:
        as_of = _find_latest_as_of(db_manager, args.portfolio_id)
        if as_of is None:
            logger.error(
                "run_execution_for_portfolio: no target_portfolios rows found for portfolio %r",
                args.portfolio_id,
            )
            return

    logger.info(
        "run_execution_for_portfolio: portfolio_id=%s mode=%s as_of=%s notional=%.2f",
        args.portfolio_id,
        args.mode,
        as_of,
        args.notional,
    )

    # Load target weights for this portfolio/date.
    weights = _load_target_weights(db_manager, args.portfolio_id, as_of)
    if not weights:
        logger.error(
            "run_execution_for_portfolio: no weights found for portfolio_id=%s as_of=%s",
            args.portfolio_id,
            as_of,
        )
        return

    # Load latest close prices.
    instrument_ids = sorted(weights.keys())
    prices = _load_latest_closes(db_manager, instrument_ids, as_of)
    if not prices:
        logger.warning(
            "run_execution_for_portfolio: no prices available; using synthetic price=100.0 for all instruments",
        )
        prices = {inst_id: 100.0 for inst_id in instrument_ids}

    # Convert to absolute share quantities.
    target_positions = _compute_target_quantities(weights, prices, args.notional)
    if not target_positions:
        logger.error("run_execution_for_portfolio: target_positions is empty after sizing; aborting")
        return

    # Create broker and apply execution plan.
    broker = _create_broker(args.mode, readonly=args.readonly or args.mode.upper() == "LIVE")

    try:
        summary = apply_execution_plan(
            db_manager=db_manager,
            broker=broker,
            portfolio_id=args.portfolio_id,
            target_positions=target_positions,
            mode=args.mode.upper(),
            as_of_date=as_of,
            decision_id=None,
            record_positions=True,
        )

        logger.info(
            "run_execution_for_portfolio: completed execution – orders=%d fills=%d",
            summary.num_orders,
            summary.num_fills,
        )
    finally:
        _disconnect_broker(broker)


if __name__ == "__main__":  # pragma: no cover - manual CLI entry
    main()
