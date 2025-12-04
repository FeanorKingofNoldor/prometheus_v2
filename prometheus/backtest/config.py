"""Prometheus v2 – Backtesting configuration models.

This module defines configuration structures for sleeve-level backtests.
For this iteration only a single :class:`SleeveConfig` model is
implemented; it can be extended later with richer constraint and
analytics options as described in the backtesting design docs.
"""

from __future__ import annotations

from pydantic import BaseModel


class SleeveConfig(BaseModel):
    """Configuration for a single backtest sleeve/book.

    Attributes:
        sleeve_id: Logical identifier for the sleeve/book (e.g.
            ``"US_EQ_CORE_LONG"``).
        strategy_id: Strategy/alpha identifier associated with this
            sleeve; stored into ``backtest_runs.strategy_id``.
        market_id: Market identifier traded by the sleeve (e.g.
            ``"US_EQ"``).
        universe_id: Universe identifier whose members the sleeve trades.
        portfolio_id: Portfolio/book identifier whose targets the sleeve
            executes.
        assessment_strategy_id: Strategy identifier used when reading
            Assessment Engine scores from ``instrument_scores``.
        assessment_horizon_days: Assessment horizon in trading days.
        assessment_backend: Assessment backend used inside the sleeve
            pipeline. ``"basic"`` selects the price/STAB-based
            :class:`BasicAssessmentModel`; ``"context"`` selects the
            joint-space :class:`ContextAssessmentModel`.
        assessment_model_id: Optional assessment model identifier used
            for persistence/tracing. If omitted, a reasonable default is
            chosen based on :attr:`assessment_backend`.
        assessment_use_joint_context: When using the ``"basic"`` backend,
            enable or disable joint Assessment context diagnostics inside
            :class:`BasicAssessmentModel`.
        assessment_context_model_id: Joint Assessment context
            ``model_id`` in ``joint_embeddings`` to use when
            ``assessment_use_joint_context`` is True or when using the
            ``"context"`` backend.
        stability_risk_alpha: Strength of the per-instrument STAB
            state-change risk modifier applied in the sleeve's universe
            model. A value of 0.0 disables STAB risk integration for this
            sleeve.
        stability_risk_horizon_steps: Horizon in soft-target transition
            steps for the STAB risk forecast.
        regime_risk_alpha: Strength of the global regime risk modifier
            applied in the sleeve's universe model. A value of 0.0
            disables regime risk integration.
        scenario_risk_set_id: Optional ``scenario_set_id`` used when
            computing scenario-based portfolio risk for this sleeve's
            portfolios. If ``None``, scenario risk is disabled for the
            sleeve.
        lambda_score_weight: Weight applied to lambda-based opportunity
            scores in the sleeve's universe model when a lambda provider
            is configured. Defaults to 0.0 (no lambda contribution).
    """

    sleeve_id: str
    strategy_id: str
    market_id: str
    universe_id: str
    portfolio_id: str
    assessment_strategy_id: str
    assessment_horizon_days: int = 21

    # Assessment engine configuration for this sleeve.
    assessment_backend: str = "basic"
    assessment_model_id: str | None = None
    assessment_use_joint_context: bool = False
    assessment_context_model_id: str = "joint-assessment-context-v1"

    # STAB state-change risk integration for the sleeve's universe. When
    # ``stability_risk_alpha`` is non-zero, the universe model applies a
    # multiplicative penalty based on STAB state-change risk, mirroring
    # the behaviour in the live pipeline.
    stability_risk_alpha: float = 0.5
    stability_risk_horizon_steps: int = 1
    regime_risk_alpha: float = 0.0

    # Optional scenario and lambda configuration for this sleeve.
    scenario_risk_set_id: str | None = None
    lambda_score_weight: float = 0.0
