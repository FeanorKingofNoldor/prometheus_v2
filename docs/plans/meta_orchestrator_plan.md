# Meta Orchestrator (Kronos v2) – Detailed Plan

## 1. Purpose & Scope

Analyze the behavior of the entire system over time and propose changes to configurations, thresholds, and strategy weights. It does **not** place trades directly; it influences the system via config updates and proposals.


## 2. High-Level Architecture

Modules under `meta/`:

- `data_aggregator/` – pulls trades, decisions, profiles, regimes, and performance.
- `analysis/` – computes diagnostics and patterns.
- `proposal_generator/` – creates adaptation proposals.
- `storage/` – writes proposals and tracks which were applied.
- `api/` – surfaces proposals and allows human/auto application.


## 3. Data Contracts

### 3.1 Inputs

- Runtime DB:
  - `trades`
  - `positions`
  - `pipeline_decisions`
- Research/Backtest DB:
  - `backtest_runs`
  - `backtest_trades`
- Profile Service:
  - `company_profile_versions`, `sector_profile_versions` (via DB or API).
- Regime & Universe:
  - `regime_history`, `universe_snapshots`, `universe_members`.
- Config DB:
  - Strategy and risk configs, prompt templates, etc., with version IDs.

### 3.2 Outputs – Tables

- `meta_controller_config_proposals`:
  - `proposal_id` (PK)
  - `created_at`
  - `target_type` (STRATEGY_CONFIG, RISK_CONFIG, PROMPT_TEMPLATE, UNIVERSE_RULES, etc.)
  - `target_id` (e.g. `strategy_id` or config key)
  - `current_config_snapshot_json`
  - `proposed_config_json`
  - `rationale_text`
  - `evidence_json` (metrics, stats backing the proposal)
  - `status` (PENDING, APPROVED, REJECTED, APPLIED)
  - `applied_at`, `applied_by` (AUTO/HUMAN)


## 4. Analysis Flow

1. Periodically (e.g. daily/weekly) or on-demand, collect data:
   - Recent trades and decisions.
   - Associated `profile_version_id`, `regime_id`, `universe_id`, `strategy_id`, `prompt_template_id`, `agent_graph_version`.
2. Compute diagnostics:
   - Performance by regime, sector, profile attributes, and strategies.
   - Over/under-performance relative to backtests.
   - Frequency and impact of Risk overrides.
   - Stability and quality of Assessment decisions.
3. Identify issues or opportunities:
   - Strategies that underperform in certain regimes.
   - Profile patterns associated with poor outcomes.
   - Prompts/agent graphs that correlate with errors.
4. Generate proposals:
   - Adjust thresholds, filters, risk budgets, or prompt parameters.
   - Add/remove universe rules.
   - Suggest new experiments.
5. Store proposals in `meta_controller_config_proposals`.


## 5. Interactions with Other Players

- **Configuration & Strategy Management**:
  - Receives proposals and either applies them automatically or after human review.
- **Assessment Engine v2, Risk, Universe**:
  - Config updates change behavior of these components; they should reference config version IDs in decisions.
- **Profile Service**:
  - May suggest changes to profile generation (e.g. new fields) if certain attributes are predictive.
- **Black Swan Engine**:
  - Analyze how emergency SOPs performed and refine future SOP templates.


## 6. Failure Modes & Safeguards

- If data is insufficient or inconsistent for robust conclusions:
  - Mark proposals with low confidence or avoid auto-application.
- Proposals should always include a way to revert (store previous config snapshot).


## 7. Current Implementation Status (Meta core)

- Implemented modules under `prometheus/meta/`:
  - `engine.py` – `MetaOrchestrator` over `backtest_runs`, including
    lambda/state-aware sleeve evaluation helpers
    (`select_top_sleeves_lambda_uplift` and
    `select_top_sleeves_lambda_robust`) that consume the
    lambda/regime/STAB diagnostics written into
    `backtest_runs.metrics_json`.
  - `data_aggregator.py` – placeholder functions for collecting trades,
    decisions, and backtest summaries (currently return empty lists).
  - `analysis.py` – placeholder `compute_diagnostics` function returning a
    simple status mapping.
  - `proposal_generator.py` – placeholder `generate_proposals` function that
    currently returns an empty list.
  - `storage.py` – helpers for inserting into and querying
    `meta_controller_config_proposals`.
  - `api.py` – wires together aggregation, diagnostics, proposal generation,
    and storage via `run_meta_analysis()` and exposes
    `get_pending_proposals_api()`.
  - `llm/` – scaffolding for LLM-based rationale generation (not wired into the
    main flow yet).
- Tests:
  - `tests/unit/test_meta_imports.py` – smoke tests for the meta API.
  - `tests/unit/test_meta_storage.py` – in-memory SQLite tests ensuring
    `insert_proposals` and `get_pending_proposals` work against a minimal
    schema.
- Dev workflows:
  - `dev_workflows/PHASE10_META.md` documents how to invoke meta analysis and
    inspect proposals.


## 8. Deferred Enhancements / TODOs (later passes)

The following items are intentionally **not** part of the current meta core and
should be implemented in later passes:

- Real diagnostics
  - Implement concrete diagnostics over trades, decisions, and backtests,
    including regime/strategy performance, risk overrides, and prompt/graph
    effectiveness.
- LLM-based rationales
  - Use `prometheus.llm_core` (and/or `meta.llm.llm_client`) to generate
    human-readable `rationale_text` fields for proposals.
- Proposal scoring and auto-application
  - Attach confidence scores to proposals and define policies for
    auto-application vs human review.
- Integration with Config & Strategy Management
  - Provide APIs for applying/reverting proposals and updating config
    version IDs, with proper logging in `config_change_log`.
- Black Swan and emergency SOP evaluation
  - Add specific diagnostics and proposals around `black_swan_*` tables and
    emergency SOP effectiveness.
- **Information-theoretic and robustness diagnostics (v2/v3)**
  - Compute regime- and universe-conditional performance summaries using
    entropy/dispersion-style metrics (e.g. is a config only working in
    low-entropy, low-dispersion regimes?).
  - Use mutual information-style measures to identify which config
    knobs (thresholds, filters, risk caps) actually move performance,
    and which are redundant.
  - Incorporate scenario-engine outputs and extreme-value metrics into
    Meta diagnostics so proposals can be justified not only by realized
    PnL but also by robustness under synthetic stress paths.

The following items are intentionally **not** part of the current meta core and
should be implemented in later passes:

- Real diagnostics
  - Implement concrete diagnostics over trades, decisions, and backtests,
    including regime/strategy performance, risk overrides, and prompt/graph
    effectiveness.
- LLM-based rationales
  - Use `prometheus.llm_core` (and/or `meta.llm.llm_client`) to generate
    human-readable `rationale_text` fields for proposals.
- Proposal scoring and auto-application
  - Attach confidence scores to proposals and define policies for
    auto-application vs human review.
- Integration with Config & Strategy Management
  - Provide APIs for applying/reverting proposals and updating config
    version IDs, with proper logging in `config_change_log`.
- Black Swan and emergency SOP evaluation
  - Add specific diagnostics and proposals around `black_swan_*` tables and
    emergency SOP effectiveness.

## Future: Config and environment embedding space

In a later phase, the Meta-Orchestrator will represent "config + environment
+ outcome" tuples as points in a shared embedding space, enabling
nearest-neighbor retrieval of successful configs under similar conditions, as
outlined in the "Meta-Orchestrator – Config and Environment Similarity" use
case in `docs/new_project_plan/joint_embedding_shared_spaces_plan.md`.
