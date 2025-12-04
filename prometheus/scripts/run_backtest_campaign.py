"""Prometheus v2 – Backtest campaign CLI.

This script runs a simple backtest campaign over one or more sleeves for
the same strategy and market, using :func:`run_backtest_campaign`.

Example
-------

    python -m prometheus.scripts.run_backtest_campaign \
        --market-id US_EQ \
        --start 2024-01-01 \
        --end 2024-03-31 \
        --sleeve US_CORE_20D:US_CORE_LONG_EQ:US_EQ:US_CORE_UNIVERSE:US_CORE_PORT:US_CORE_ASSESS:21
"""

from __future__ import annotations

import argparse
from datetime import date
from typing import List, Optional, Sequence

from prometheus.core.config import get_config
from prometheus.core.database import DatabaseManager
from prometheus.core.logging import get_logger
from prometheus.core.time import TradingCalendar
from prometheus.backtest import SleeveConfig, run_backtest_campaign


logger = get_logger(__name__)


def _parse_date(value: str) -> date:
    try:
        year, month, day = map(int, value.split("-"))
        return date(year, month, day)
    except Exception as exc:  # pragma: no cover - CLI validation
        raise argparse.ArgumentTypeError(f"Invalid date {value!r}, expected YYYY-MM-DD") from exc


def _parse_sleeve_arg(raw: str) -> SleeveConfig:
    """Parse a compact sleeve definition into :class:`SleeveConfig`.

    The format is::

        sleeve_id:strategy_id:market_id:universe_id:portfolio_id:assessment_strategy_id:assessment_horizon_days
    """

    parts = raw.split(":")
    if len(parts) != 7:
        raise argparse.ArgumentTypeError(
            "--sleeve must have 7 colon-separated fields: "
            "sleeve_id:strategy_id:market_id:universe_id:portfolio_id:assessment_strategy_id:assessment_horizon_days",
        )

    sleeve_id, strategy_id, market_id, universe_id, portfolio_id, assess_id, horizon_str = parts
    try:
        horizon_days = int(horizon_str)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid assessment_horizon_days {horizon_str!r} in --sleeve argument",
        ) from exc

    return SleeveConfig(
        sleeve_id=sleeve_id,
        strategy_id=strategy_id,
        market_id=market_id,
        universe_id=universe_id,
        portfolio_id=portfolio_id,
        assessment_strategy_id=assess_id,
        assessment_horizon_days=horizon_days,
    )


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Run a multi-sleeve backtest campaign")

    parser.add_argument("--market-id", type=str, required=True, help="Market identifier (e.g. US_EQ)")
    parser.add_argument("--start", type=_parse_date, required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=_parse_date, required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--sleeve",
        dest="sleeves",
        action="append",
        required=True,
        help=(
            "Sleeve definition in the form "
            "sleeve_id:strategy_id:market_id:universe_id:portfolio_id:assessment_strategy_id:assessment_horizon_days. "
            "May be specified multiple times."
        ),
    )
    parser.add_argument(
        "--initial-cash",
        type=float,
        default=1_000_000.0,
        help="Initial cash per sleeve (default: 1,000,000)",
    )
    parser.add_argument(
        "--disable-risk",
        action="store_true",
        help=(
            "Disable Risk Management adjustments inside the sleeve pipeline "
            "(use raw portfolio weights for a risk-off baseline)"
        ),
    )
    parser.add_argument(
        "--assessment-backend",
        type=str,
        choices=["basic", "context"],
        default="basic",
        help=(
            "Assessment backend used inside the sleeve pipeline: 'basic' "
            "(price/STAB-based) or 'context' (joint Assessment context "
            "embeddings). Applies to all sleeves in this campaign."
        ),
    )
    parser.add_argument(
        "--assessment-use-joint-context",
        action="store_true",
        help=(
            "If set and --assessment-backend=basic, enable joint Assessment "
            "context diagnostics (ASSESSMENT_CTX_V0) inside the basic model."
        ),
    )
    parser.add_argument(
        "--assessment-context-model-id",
        type=str,
        default="joint-assessment-context-v1",
        help=(
            "Joint Assessment context model_id in joint_embeddings "
            "(default: joint-assessment-context-v1)."
        ),
    )
    parser.add_argument(
        "--assessment-model-id",
        type=str,
        default=None,
        help=(
            "Assessment model identifier used for persistence/tracing in "
            "instrument_scores (default: assessment-basic-v1 for basic "
            "backend, assessment-context-v1 for context backend)."
        ),
    )

    args = parser.parse_args(argv)

    if args.end < args.start:
        parser.error("--end must be >= --start")

    sleeve_configs: List[SleeveConfig] = []
    for raw in args.sleeves:
        cfg = _parse_sleeve_arg(raw)
        # Apply campaign-wide Assessment configuration to each sleeve.
        cfg.assessment_backend = args.assessment_backend
        cfg.assessment_use_joint_context = args.assessment_use_joint_context
        cfg.assessment_context_model_id = args.assessment_context_model_id
        if args.assessment_model_id is not None:
            cfg.assessment_model_id = args.assessment_model_id
        sleeve_configs.append(cfg)

    config = get_config()
    db_manager = DatabaseManager(config)
    calendar = TradingCalendar()

    summaries = run_backtest_campaign(
        db_manager=db_manager,
        calendar=calendar,
        market_id=args.market_id,
        start_date=args.start,
        end_date=args.end,
        sleeve_configs=sleeve_configs,
        initial_cash=args.initial_cash,
        apply_risk=not args.disable_risk,
    )

    if not summaries:
        print("No sleeves were run (empty sleeve list)")
        return

    print("run_id,sleeve_id,strategy_id,cumulative_return,annualised_sharpe,max_drawdown")
    for s in summaries:
        m = s.metrics or {}
        cumret = float(m.get("cumulative_return", 0.0))
        sharpe = float(m.get("annualised_sharpe", 0.0))
        maxdd = float(m.get("max_drawdown", 0.0))
        print(
            f"{s.run_id},{s.sleeve_id},{s.strategy_id},{cumret:.6f},{sharpe:.4f},{maxdd:.6f}",
        )


if __name__ == "__main__":  # pragma: no cover - manual CLI entry
    main()
