# Assessment Engine v2 – Detailed Plan

## 1. Purpose & Scope

Given candidate universes, company/sector profiles, regime, technicals, and portfolio state, the Assessment Engine v2 decides **which names to trade, in what direction, with what conviction**, and provides auditable rationales.


## 2. High-Level Architecture

Modules under `assessment/`:

- `context_builder/` – assemble full `DecisionContext` per ticker.
- `agents/` – LLM-based and rule-based agents that perform reasoning.
- `orchestrator/` – combines agent outputs into final decisions.
- `storage/` – logs decision objects into `pipeline_decisions` table.
- `api/` – entrypoints for daily/intraday decision cycles.


## 3. Data Contracts

### 3.1 Inputs (per decision cycle)

- From Universe Selection:
  - `universe_id`, list of candidate tickers and selection metadata.
- From Profile Service:
  - `get_company_profile(ticker, as_of_date)` for each candidate.
  - `get_sector_profile(sector_id, as_of_date)` as needed.
- From Macro Regime Service:
  - `{regime_id, regime_name, sub_stage, scores}`.
- From Historical/Runtime DB:
  - `stock_metrics` (technical indicators, volatility, factor exposures per ticker).
- From Runtime DB:
  - Portfolio state: positions, PnL, exposures.
- From Config:
  - Strategy definitions and parameters.
  - Prompt templates and LLM model choices.

### 3.2 Outputs

- In-memory decision objects:
  - For each ticker:
    - `ticker`
    - `decision_type` (LONG_ENTRY, LONG_HOLD, LONG_EXIT, SHORT_ENTRY, SHORT_HOLD, SHORT_EXIT, SKIP)
    - `conviction_score`
    - `target_weight_hint` or `notional_hint`
    - `stop_loss_hint`, `take_profit_hint` (optional)
    - `profile_version_id`, `sector_profile_version_id`
    - `regime_id`, `universe_id`, `strategy_id`
    - `prompt_template_id`, `agent_graph_version`
    - `decision_rationale_short`
- DB table `pipeline_decisions` (runtime DB):
  - Stores above fields plus timestamps and any additional metadata.


## 4. DecisionContext Structure

Internal structured object per ticker:

- `CompanyContext`:
  - Profile snapshot (structured fields, narrative, strengths, weaknesses, risk flags).
  - Cycle behavior summary.
- `SectorContext`:
  - Sector profile snapshot.
- `MarketContext`:
  - Regime state.
  - Technical indicators, volatility, correlations.
- `PortfolioContext`:
  - Current holdings in this ticker (if any).
  - Overall exposures and risk state.
- `StrategyContext`:
  - Strategy config: style, horizon, risk budget, filters.


## 5. Agent Design

- Agents operate only on the `DecisionContext`, not on raw external data.
- Example agents:
  - `FundamentalAgent` – interprets profile fundamentals, strengths/weaknesses.
  - `TechnicalAgent` – interprets technicals and volatility context.
  - `RiskAwareAgent` – checks risk flags, concentration, and suggests caution when needed.
  - `SynthesisAgent` – combines signals into a final direction and conviction.

Each agent produces:
- A **local recommendation** and scores.
- A short explanation snippet.

The orchestrator merges these into a single decision per ticker.


## 6. Interactions with Other Players

- **Universe Selection**:
  - Provides candidate set and selection metadata.
- **Profile Service**:
  - Provides company/sector profiles at decision time.
- **Macro Regime Service**:
  - Provides regime state for context.
- **Risk Management**:
  - Receives decisions and applies hard constraints, may override or scale down.
- **Meta Orchestrator**:
  - Reads `pipeline_decisions` with associated profile versions and evaluates quality of decisions.
- **Black Swan Engine**:
  - `DecisionContext` includes `black_swan_state` and event info; prompts adjust to emphasize capital preservation under emergencies.


## 7. Failure Modes & Safeguards

- If profile or technical data is incomplete:
  - DecisionContext includes `data_quality_flag`, agents may downgrade conviction or return SKIP.
- If LLM call fails for a ticker:
  - Fallback to simpler rule-based decision or SKIP.
- All decisions are timestamped and versioned with config and prompt IDs.


## 8. Current Implementation Status (Phase 7 core)

- Implemented modules under `prometheus/assessment/`:
  - `context_builder.py` – builds `DecisionContext` objects using Profile and
    Macro Regime services (company profile snapshot + regime + minimal
    portfolio/strategy placeholders).
  - `agents/` – rule-based `FundamentalAgent`, `TechnicalAgent`,
    `RiskAwareAgent`, and `SynthesisAgent` that operate purely on
    `DecisionContext`.
  - `orchestrator.py` – loads universe tickers, builds contexts, runs agents,
    materialises decision dicts, and writes them to `pipeline_decisions`.
  - `storage.py` – helper to insert decision rows into `pipeline_decisions`.
  - `api.py` – public `run_assessment_cycle(as_of_date, regime_id, universe_id,
    strategy_id)` function.
  - `llm/` – scaffolding for future LLM integration (client, prompts,
    agent-graph config) which is **not** yet wired into the main decision path.
- Tests:
  - `tests/unit/test_assessment_imports.py` – smoke tests for the public API.
  - `tests/unit/test_assessment_storage.py` – in-memory SQLite tests verifying
    `insert_pipeline_decisions` can write rows into a minimal
    `pipeline_decisions` schema.
- Dev workflows:
  - `dev_workflows/PHASE7_ASSESSMENT.md` documents how to run
    `run_assessment_cycle` and inspect resulting `pipeline_decisions` rows.


## 9. Deferred Enhancements / TODOs (later passes)

The following items are intentionally **not** part of the Phase 7 core and
should be implemented in later passes, primarily because they depend on real
LLM providers or richer data/config tables:

- LLM-based assessment agents
  - Implement LLM-backed agents on top of `prometheus.llm_core` that consume
    `DecisionContext` and produce richer rationales and calibrated signals.
  - Wire prompt loading from `prompt_templates` and model parameters from
    `llm_config` instead of hard-coded placeholders.
- Richer DecisionContext and data usage
  - Integrate `stock_metrics` and other technical/factor data into
    `MarketContext`.
  - Incorporate real portfolio state and risk configuration (via
    `positions`, `risk_configs`, and `strategy_configs`) instead of placeholders.
- Deeper Risk integration
  - Tighten coupling between assessment outputs and the Risk engine,
    standardising how constraints and overrides are represented in decisions.
- Calibration, evaluation, and feedback
  - Define a systematic mapping from raw scores to `decision_type` and
    `conviction_score`, including per-strategy calibration curves.
  - Add feedback loops for the Meta Orchestrator to evaluate decision quality
    and suggest config/prompt changes.
- Operationalisation & tooling
  - Monitoring/observability hooks (structured logs and metrics) around
    assessment runs (basic CLI entrypoint already exists under
    `prometheus.scripts.run_assessment_cycle`).
- **Information-theoretic and sparse modelling enhancements (v3+)**
  - Where the Assessment Engine consumes numeric features, use
    mutual-information-style diagnostics and L1/proximal methods (e.g.
    LASSO) to keep auxiliary scoring models sparse and interpretable,
    avoiding proliferation of brittle indicators.
  - Reserve heavier, math-driven scoring models for clearly separated
    research passes; keep the production decision surface simple and
    stable, with Meta assessing whether extra complexity actually
    improves outcomes.

The following items are intentionally **not** part of the Phase 7 core and
should be implemented in later passes, primarily because they depend on real
LLM providers or richer data/config tables:

- LLM-based assessment agents
  - Implement LLM-backed agents on top of `prometheus.llm_core` that consume
    `DecisionContext` and produce richer rationales and calibrated signals.
  - Wire prompt loading from `prompt_templates` and model parameters from
    `llm_config` instead of hard-coded placeholders.
- Richer DecisionContext and data usage
  - Integrate `stock_metrics` and other technical/factor data into
    `MarketContext`.
  - Incorporate real portfolio state and risk configuration (via
    `positions`, `risk_configs`, and `strategy_configs`) instead of placeholders.
- Deeper Risk integration
  - Tighten coupling between assessment outputs and the Risk engine,
    standardising how constraints and overrides are represented in decisions.
- Calibration, evaluation, and feedback
  - Define a systematic mapping from raw scores to `decision_type` and
    `conviction_score`, including per-strategy calibration curves.
  - Add feedback loops for the Meta Orchestrator to evaluate decision quality
    and suggest config/prompt changes.
- Operationalisation & tooling
  - Monitoring/observability hooks (structured logs and metrics) around
    assessment runs (basic CLI entrypoint already exists under
    `prometheus.scripts.run_assessment_cycle`).

## Future: Assessment context embedding space

A later iteration of the Assessment Engine will consume joint context
embeddings (profile + regime + stability + recent text) as compact numeric
features, following the "Assessment Context Space" use case in
`docs/new_project_plan/joint_embedding_shared_spaces_plan.md`. The daily
pipeline remains purely numeric and deterministic; embeddings are just
another structured feature.
