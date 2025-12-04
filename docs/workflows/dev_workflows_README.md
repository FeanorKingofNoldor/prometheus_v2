# Dev Workflows – Index

This file lists practical, task-oriented workflows for working with
Prometheus v2 in development. Each workflow document focuses on a specific
slice of the system and is safe to follow in a dev/test environment.

## Available workflows

- `docs/dev_workflows_v0_training_backfills.md`
  - Run a v0 historical training/backfill campaign covering Regime, STAB,
    universes, λ/λ̂, synthetic scenarios, and backtests+Meta for a
    strategy/market/date range.
- `docs/dev_workflows_backtest_and_risk.md`
  - Compare sleeve backtest campaigns with Risk Management enabled vs
    disabled (risk-on vs risk-off).
  - Run `run_backtest_campaign` and `run_campaign_and_meta` with and without
    risk, and inspect `risk_actions` via the `show_risk_actions` CLI.
- `docs/dev_workflows_engine_runs_orchestration.md`
  - Manage daily engine runs using the `engine_runs` state machine and the
    `run_engine_state` CLI.
  - Outlines short/medium/long-term orchestration options (timers, engine
    daemon, external DAG orchestrator).
- `docs/dev_workflows_execution_bridge.md`
  - Run a sleeve-level backtest that flows through the unified execution
    bridge and inspect `orders`, `fills`, and `positions_snapshots` in the
    runtime DB.
- `docs/dev_workflows_execution_risk_and_ibkr.md`
  - Run IBKR PAPER/LIVE execution through the software risk wrapper and
    confirm limits via the `show_execution_risk` CLI before live-capable
    runs.
- `docs/dev_workflows_text_embeddings.md`
  - Backfill text embeddings for news articles using
    `backfill_text_embeddings` and the `text-fin-general-v1` model.
- `docs/dev_workflows_text_profile_embeddings.md`
  - Plan/profile for text-profile-v1 embeddings for issuer/country
    profiles.
- `docs/dev_workflows_text_macro_embeddings.md`
  - Plan/profile for text-macro-v1 embeddings for macro/policy text.
- `docs/dev_workflows_numeric_embeddings.md`
  - Backfill generic numeric window embeddings using
    `backfill_numeric_embeddings`, including flattened and 384-dim
    encoders.
- `docs/dev_workflows_numeric_stab_embeddings.md`
  - Backfill numeric stability embeddings using `num-stab-core-v1`
    (384-dim) via `backfill_numeric_embeddings`.
- `docs/dev_workflows_numeric_profile_embeddings.md`
  - Plan/profile for numeric profile embeddings using
    `num-profile-core-v1`.
- `docs/dev_workflows_numeric_scenario_embeddings.md`
  - Plan/profile for numeric scenario embeddings using
    `num-scenario-core-v1`.
- `docs/dev_workflows_numeric_portfolio_embeddings.md`
  - Plan/profile for numeric portfolio embeddings using
    `num-portfolio-core-v1`.
- `docs/dev_workflows_joint_portfolios.md`
  - Build and inspect joint portfolio embeddings combining numeric
    portfolio features into `joint-portfolio-core-v1`, and search for
    similar portfolios in `PORTFOLIO_CORE_V0` space.
- `docs/dev_workflows_regime_numeric.md`
  - Run the numeric Regime Engine end-to-end using numeric window
    embeddings (e.g. `num-regime-core-v1`) via `run_numeric_regime`.
- `docs/dev_workflows_joint_regime_context.md`
  - Build and inspect joint regime context embeddings combining numeric
    `num-regime-core-v1` and text `text-fin-general-v1` into
    `joint-regime-core-v1`.
- `docs/dev_workflows_joint_regime_macro_context.md`
  - Build and inspect joint regime+macro context embeddings combining
    numeric `num-regime-core-v1` and MACRO text `text-macro-v1` into
    `joint-regime-core-v1`.
- `docs/dev_workflows_joint_episodes.md`
  - Build joint episode embeddings for pre-defined event windows using
    `backfill_joint_episode_context` into `joint-episode-core-v1`.
- `docs/dev_workflows_joint_profiles.md`
  - Build joint profile embeddings combining numeric profile, behaviour,
    and text-profile signals into `joint-profile-core-v1`, and search for
    similar issuers in `PROFILE_CORE_V0` space.
- `docs/dev_workflows_joint_stab_fragility.md`
  - Build joint stability/fragility embeddings combining numeric stability
    and optional joint profile embeddings into `joint-stab-fragility-v1`.
- `docs/dev_workflows_joint_assessment_context.md`
  - Build and inspect joint Assessment context embeddings combining
    profile, regime, stability, and text context into
    `joint-assessment-context-v1`, and search for similar Assessment
    contexts.
- `docs/dev_workflows_joint_meta_config_env.md`
  - Build and inspect meta config+environment embeddings combining
    config, environment, and outcome summaries into
    `joint-meta-config-env-v1`.
- `docs/dev_workflows_portfolio_stab_scenarios.md`
  - Analyse portfolio-level exposure to STAB/fragility scenarios using
    joint STAB embeddings for instruments and scenarios.
- `docs/dev_workflows_regime_prototypes.md`
  - Compute numeric regime prototypes (e.g. NEUTRAL, CRISIS) from
    stored embeddings and use them to initialise `NumericRegimeModel`.

## Conventions

- All workflows assume:
  - Migrations have been applied to both runtime and historical DBs.
  - You are running commands from the project root.
- New workflows should follow the naming pattern
  `docs/dev_workflows_<topic>.md` and be added to this index.
