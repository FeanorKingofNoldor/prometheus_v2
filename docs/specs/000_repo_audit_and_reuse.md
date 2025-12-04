# 000 – Repo Audit and Reuse Plan (Prometheus v2)

## 1. Purpose

This document inventories the current Prometheus repo and decides what to:
- **Reuse** (infrastructure only, adapted to v2 specs).
- **Treat as reference-only** (concepts and patterns, but no direct reuse).
- **Scrap/replace** (superseded by Prometheus v2 architecture).

The goal is to avoid dragging v1 assumptions into v2, while not throwing away solid infrastructure.

---

## 2. Inventory – Existing Planning Docs

Directory: `docs/new_project_plan/`

Found planning documents:

- `REGIME_STABILITY_COMPLETION_SUMMARY.md`
- `REGIME_STABILITY_INTEGRATION_GUIDE.md`
- `REVISED_PLANS_SUMMARY.md`
- `STABILITY_REWRITE_PROGRESS.md`
- `algorithms_landscape.md`
- `assessment_engine_v2_plan.md`
- `backtesting_engine_plan.md`
- `black_swan_emergency_engine_plan.md`
- `config_and_strategy_management_plan.md`
- `data_ingestion_plan.md`
- `documentation_standards.md`
- `execution_plan.md`
- `execution_service_plan.md`
- `macro_regime_service_plan.md`
- `makro plan.md`
- `meta_orchestrator_plan.md`
- `monitoring_and_observability_plan.md`
- `profile_service_plan.md`
- `risk_management_service_plan.md`
- `universe_selection_service_plan.md`

### 2.1 Classification of planning docs

- **Keep as reference (conceptual only):**
  - All of the above.
- **Superseded by v2 master plans:**
  - `assessment_engine_v2_plan.md` (replaced by `130_assessment_engine.md`).
  - `black_swan_emergency_engine_plan.md` (replaced by `120_black_swan_engine.md`).
  - `macro_regime_service_plan.md` and `makro plan.md` (replaced by `100_regime_engine.md`).
  - `meta_orchestrator_plan.md` (replaced by `160_meta_orchestrator.md`).
  - `universe_selection_service_plan.md` (replaced by `140_universe_engine.md`).
  - `risk_management_service_plan.md` (replaced by `150_portfolio_and_risk_engine.md`).
- **Still directly useful for v2 standards/process:**
  - `documentation_standards.md` (docstring and doc rules).
  - `monitoring_and_observability_plan.md` (input to monitoring section in 200_defensive threat model and engine specs).
  - `config_and_strategy_management_plan.md` (input to config schemas & Meta-Orchestrator).
  - `data_ingestion_plan.md` and `execution_plan.md`/`execution_service_plan.md` (input to new data and execution layers).

**Rule:**
- v2 specs (in `docs/specs/0xx` and `1xx`) are the **source of truth**. Old plans can be consulted for ideas but must not override v2 decisions.

---

## 3. Inventory – Code Packages

Top-level Python packages under `prometheus/` (from file scan):

- `prometheus/regime/`
- `prometheus/stability/`
- `prometheus/assessment/`
- `prometheus/backtesting/`
- `prometheus/black_swan/`
- `prometheus/config_mgmt/`
- `prometheus/core/`
- `prometheus/data_ingestion/`
- `prometheus/execution/`
- `prometheus/llm_core/`
- `prometheus/macro/`
- `prometheus/meta/`
- `prometheus/monitoring/`
- `prometheus/profiles/`
- `prometheus/risk/`
- `prometheus/scripts/`
- `prometheus/universe/`

Below we classify them for Prometheus v2.

### 3.1 Core infrastructure packages

**`prometheus/core/`**
- Files: `config.py`, `database.py`, `db_health.py`, `logging.py`, `types.py`, `__init__.py`.
- **Classification:**
  - **Candidate for reuse**, with review and adaptation to v2 foundations.
- **Notes:**
  - Likely contains generic config, DB, logging, and type helpers that are still useful.
  - Must be aligned with `010_foundations.md` (IDs, config, logging patterns) and `020_data_model.md` (DB schemas).

**`prometheus/monitoring/`**
- Files: `alerts.py`, `dashboards.py`, `logging_setup.py`, `metrics.py`, `web/app.py`, `__init__.py`.
- **Classification:**
  - **Candidate for reuse**, especially patterns for logging, metrics, and alerting.
- **Notes:**
  - Implementation should be re-reviewed; interfaces may change per v2 specs.

**`prometheus/config_mgmt/`**
- Files: `api.py`, `models.py`, `storage.py`, `versioning.py`, `__init__.py`.
- **Classification:**
  - **Reference-only / partial reuse**.
- **Notes:**
  - Concepts and patterns for config versioning are valuable.
  - Actual models, storage layout must be reconciled with v2 config schemas and `020_data_model.md`.

**`prometheus/data_ingestion/`**
- Contains: `api.py`, `sources/*`, `normalizers/*`, `validation/*`, `writers/historical_db_writer.py`, etc.
- **Classification:**
  - **Reference-only / partial reuse**.
- **Notes:**
  - Ingestion clients, validation rules, and writers may be reusable after aligning with v2 canonical schemas.
  - Orchestration code may need rewrites.

**`prometheus/scripts/`**
- Files: `db_migrate.py`, `run_assessment_cycle.py`, `run_backtest.py`, `__init__.py`.
- **Classification:**
  - **Reference-only**.
- **Notes:**
  - CLI entrypoints will be redesigned to match the new engine APIs and orchestration flows.

### 3.2 Engine & logic packages (to be superseded)

These map to v1 engine designs and will largely be replaced by v2 engine specs.

**`prometheus/regime/`**
- Files: `api.py`, `engine.py`, `classification/*`, `indicators/*`, `storage.py`.
- **Classification:**
  - **Reference-only.** Superseded by `100_regime_engine.md`.
- **Notes:**
  - Existing indicators, classification code, and storage patterns may inspire new implementations but should not be assumed correct for v2.

**`prometheus/stability/`**
- Files: `api.py`, `engine.py`, `classification.py`, `entities.py`, `scoring.py`, `storage.py`.
- **Classification:**
  - **Reference-only.** Superseded by `110_stability_engine.md`.

**`prometheus/black_swan/`**
- Files: `api.py`, `sop_engine.py`, `state_manager.py`, `storage.py`.
- **Classification:**
  - **Reference-only.** Superseded by `120_black_swan_engine.md`.

**`prometheus/assessment/`**
- Files: `api.py`, `engine-like components`, `agents/*`, `llm/*`, `context_builder.py`, `orchestrator.py`, `storage.py`.
- **Classification:**
  - **Reference-only.** Superseded by `130_assessment_engine.md`.
- **Notes:**
  - Decompose concepts: numeric vs LLM agents, context building. Use patterns where clean, but re-spec behavior.

**`prometheus/universe/`**
- Files: `api.py`, `builder/*`, `analyzer/*`, `storage.py`.
- **Classification:**
  - **Reference-only.** Superseded by `140_universe_engine.md`.

**`prometheus/risk/`**
- Files: `api.py`, `engine.py`, `constraints.py`, `exposure_calculator.py`, `storage.py`.
- **Classification:**
  - **Reference-only.** Superseded by `150_portfolio_and_risk_engine.md`.

**`prometheus/backtesting/`**
- Files: `api.py`, `engine.py`, `market_simulator.py`, `portfolio.py`, `time_machine.py`, `storage.py`.
- **Classification:**
  - **Reference-only.**
- **Notes:**
  - V2 backtesting is core infra; we may reuse some simulator/portfolio ideas after reconciling with v2 Portfolio & Risk and Synthetic Scenario specs.

**`prometheus/execution/`**
- Files: `api.py`, `broker_adapters/*`, `order_planner.py`, `router.py`, `simulated_execution.py`, `storage.py`.
- **Classification:**
  - **Reference-only / partial reuse.**
- **Notes:**
  - Broker adapters and some routing patterns may be ported; high-level interface must match new execution plan docs (likely under a new spec file later).

**`prometheus/macro/`**
- Files: `api.py`, `engine.py`, `indicators/*`, `models/regime_model.py`, `storage.py`.
- **Classification:**
  - **Reference-only.** Fold into `regime` + `stability` v2 specs as needed.

**`prometheus/profiles/`**
- Files: `api.py`, `builders/*`, `llm/*`, `models.py`, `storage.py`, `updaters/*`.
- **Classification:**
  - **Reference-only / partial reuse.** Superseded conceptually by `035_profiles.md`.
- **Notes:**
  - Existing builders/updaters may be heavily refactored to match new ProfileSnapshot schema and embedding design.

**`prometheus/meta/`**
- Files: `analysis.py`, `api.py`, `data_aggregator.py`, `llm/*`, `proposal_generator.py`, `storage.py`.
- **Classification:**
  - **Reference-only.** Superseded by `160_meta_orchestrator.md`.

**`prometheus/llm_core/`**
- Files: `agent_base.py`, `client.py`, `graph.py`, `__init__.py`.
- **Classification:**
  - **Reference-only / partial reuse.**
- **Notes:**
  - LLM client/wrapper patterns can inform v2 LLM integration, but must respect new rules (LLMs as explainers/proposers only).

---

## 4. High-Level Reuse Rules for v2

1. **Engines & alpha logic:**
   - All v1 engines (regime, stability, black_swan, assessment, universe, risk, macro, meta) are **superseded** by new specs.
   - Their code is **reference-only**; we can borrow ideas but must not reuse blindly.

2. **Infrastructure (core, monitoring, parts of data_ingestion, config_mgmt, execution, backtesting, profiles):**
   - Can be reused **selectively** after careful review.
   - Must be made consistent with:
     - `010_foundations.md` (IDs, config, logging, typing).
     - `020_data_model.md` (schemas).
     - `030_encoders_and_embeddings.md` and `035_profiles.md` (embedding APIs).

3. **LLM integration:**
   - v1 LLM code (`assessment/llm`, `meta/llm`, `llm_core`, `profiles/llm`) is reference-only.
   - v2 will define strict interfaces and roles for LLMs; reuse only low-level client abstractions if they fit.

4. **Docs:**
   - Old planning docs live under `docs/new_project_plan/` as historical context.
   - New specs live under `docs/specs/` and take precedence.

---

## 5. Practical Guidelines Going Forward

- When starting a v2 spec or implementation for an engine:
  - You **may read** the corresponding v1 package and old plan docs for intuition.
  - You **must design** the v2 interface and behavior from the new spec documents, not from v1 code.
  - Any code you think about copying must be:
    - Reviewed line-by-line against v2 assumptions.
    - Re-tested in isolation before being trusted.

- Before deleting v1 modules:
  - Ensure any useful utilities (e.g., DB health checks, logging helpers) have clear homes in v2 `core/` or other infra packages.
  - Archive the repo state (tag or branch) as `prometheus_v1_legacy` for future reference.

This audit/reuse plan should be revisited after `010_foundations.md`, `020_data_model.md`, and `030/035` are drafted, to confirm that the initial classifications still hold.