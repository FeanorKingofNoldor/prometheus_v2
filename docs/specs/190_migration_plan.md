# 190 – Migration Plan (Prometheus v1 → v2)

## 1. Purpose

This document describes how to migrate from the existing Prometheus v1 code and data to the Prometheus v2 architecture defined in 010–180.

Goals:
- Clean separation between **legacy v1 engines** and **v2 engines**.
- Maximal reuse of trustworthy infra and data where safe.
- Phased, reversible rollout with clear rollback paths.

---

## 2. Current vs Target State (High-Level)

### 2.1 Current state (v1)

- Single repo with:
  - legacy engines (regime, stability, assessment, backtesting, black swan, macro, meta, universe, risk),
  - core infra (logging, config, DB),
  - data ingestion.
- Data model less structured than 020; partial coupling between layers.
- Testing and validation practices uneven across modules.

### 2.2 Target state (v2)

- Architecture decomposed as in 010 and WARP overview:
  - strict separation between data, encoders, profiles, engines, meta-orchestrator, scenarios, and monitoring.
- Postgres schemas/tables aligned with 020.
- Engines implemented per 100–170; Kronos per 160.
- Testing/validation/gating per 180.

Legacy v1 engines are **reference-only**; new work is done in the v2 structure.

---

## 3. Principles

1. **No in-place mutation of v1 engines**
   - v1 code is preserved (possibly moved/renamed) as reference.
   - v2 engines are implemented in new modules under the planned package layout.

2. **Forward-only data model changes**
   - v2 tables and schemas are added alongside any existing v1 tables.
   - Migrations are additive; destructive changes to v1 DB objects happen only after a stable v2 cutover.

3. **Side-by-side evaluation before cutover**
   - v2 runs in **shadow mode** alongside v1:
     - consumes the same or better data,
     - produces decisions that are logged but not traded,
     - is validated vs v1 and via backtests/scenarios.

4. **Explicit cutover decisions with rollback**
   - Switching live trading from v1 to v2 is an explicit operation.
   - Rollback paths are defined in advance.

---

## 4. Code Migration Plan

### 4.1 Repository organization

- Keep a single repo `prometheus` but introduce clear separation:
  - `prometheus/legacy/` (or equivalent) for v1 engines that we keep for reference.
  - `prometheus/core/`, `prometheus/data_ingestion/`, `prometheus/encoders/`, `prometheus/profiles/`, `prometheus/regime/`, `prometheus/stability/`, `prometheus/fragility/`, `prometheus/assessment/`, `prometheus/universe/`, `prometheus/portfolio/`, `prometheus/meta/`, `prometheus/synthetic/`, `prometheus/monitoring/`, etc. for v2.

- Steps:
  1. Move v1 engine modules into `prometheus/legacy/` (or rename their package) without functional changes.
  2. Update imports in any remaining v1-specific scripts to use the `legacy` namespace.
  3. Keep v1 tests under `tests/legacy/`.

### 4.2 Core infra and utilities

- Evaluate v1 infra modules (logging, config, DB connection management):
  - If consistent with 010, reuse them with minimal refactoring.
  - Otherwise, implement v2-compliant infra and incrementally migrate callers.

- Introduce v2-friendly abstractions where needed:
  - config loading per 010,
  - DB sessions aligned with 020,
  - orchestrator integration per 012/013.

### 4.3 Engine implementation order

Implement and hook v2 engines roughly in this order:

1. **Foundations & data model**
   - Ensure Alembic migrations exist for v2 tables (020).
   - Implement core config/logging/time/calendar utilities (010, 012).

2. **Representation layer**
   - Encoders & embeddings (030).
   - Profile service (035).

3. **Regime & stability/fragility**
   - Regime Engine (100).
   - Stability & Soft-Target Engine (110).
   - Fragility Alpha (135).

4. **Assessment & universe**
   - Assessment Engine (130).
   - Universe Engine (140).

5. **Portfolio & risk**
   - Portfolio optimization and risk reporting (150).

6. **Synthetic scenarios**
   - Scenario Engine and DB tables (170).

7. **Meta-Orchestrator & testing**
   - Kronos v2 (160).
   - Integrate with testing/validation harness (180).

Each step should ship with its own tests (per 180) and not rely on v1 engines.

---

## 5. Data Migration Plan

### 5.1 DB schemas

- Introduce a v2 schema or table namespace according to 020; examples:
  - `markets`, `issuers`, `instruments`, `portfolios`, `strategies`.
  - `prices_daily`, `returns_daily`, `factors_daily`, `instrument_factors_daily`.
  - `macro_time_series`, `news_articles`, `filings`, `earnings_calls`.
  - `profiles`, `text_embeddings`, `numeric_window_embeddings`, `joint_embeddings`.
  - `regimes`, `stability_vectors`, `fragility_measures`, `soft_target_classes`.

- Use Alembic to create new objects **without** altering v1 tables.

### 5.2 Historical data backfill

- Market and macro time series:
  - If v1 already has canonical time-series tables, write ETL jobs that:
    - read v1 tables,
    - transform to v2 schema,
    - populate v2 tables.

- Text and profiles:
  - For existing filings/earnings/news, re-encode under v2 encoders and populate v2 profile/embedding tables.

- Engine outputs:
  - Regimes, stability vectors, fragility scores, etc. are not migrated; they are recomputed under v2 engines on historical data as needed.

### 5.3 Runtime data

- For live operation:
  - v1 ingestion pipelines may continue writing to old tables during transition.
  - v2 ingestion pipelines should be introduced to write directly to v2 tables.
  - Where feasible, the same raw data feeds both v1 and v2 schemas.

---

## 6. Config and Strategy Migration

### 6.1 Config mapping

- v1 configs (YAML/JSON) may not directly fit v2’s config schema.
- Create **mapping docs** and scripts to:
  - extract relevant v1 parameters (universe rules, risk limits, alpha toggles),
  - map them into v2 engine configs (`engine_configs` table in 020 and 160),
  - record mapping decisions and assumptions.

### 6.2 Strategy equivalence

- For each major v1 strategy/portfolio:
  - define a v2 **reference strategy config** that aims to approximate v1’s behavior.
  - run backtests on overlapping historical windows:
    - v1 vs v2 decisions and portfolios,
    - P&L and risk metrics.

- Use this to:
  - identify structural differences (v2 may intentionally behave differently),
  - ensure v2 does not introduce unexpected pathological behaviors.

---

## 7. Phased Rollout

### 7.1 Phase 0 – Stabilize v1 and freeze scope

- Freeze major v1 feature development.
- Only critical bugfixes allowed.
- Document key v1 behaviors and configs for reference.

### 7.2 Phase 1 – Infra and data model

- Introduce v2 DB schema (020) via migrations.
- Implement v2 core infra (010) and basic ingestion into v2 tables.
- Validate via integration tests and data QC.

### 7.3 Phase 2 – Offline v2 engines

- Implement v2 engines stepwise (Section 4.3).
- Run **pure offline** backtests using v2 data (no link to live trading).
- Establish golden backtests and baselines (180).

### 7.4 Phase 3 – Shadow mode

- Connect v2 engines to the same live or near-live data as v1 (read-only).
- For each trading day:
  - v1 continues to produce live decisions.
  - v2 produces shadow decisions and portfolios, written to `engine_decisions` and related tables.

- Use Kronos v2 to:
  - compare v1 vs v2 performance and behavior,
  - monitor scenario risk and robustness of v2 configs.

### 7.5 Phase 4 – Partial cutover

- Select low-risk strategies or small capital allocations:
  - route a fraction of orders through v2 portfolios,
  - keep v1 running either as:
    - a benchmark only, or
    - a fallback for the remaining capital.

- Carefully monitor:
  - execution quality,
  - realized P&L and drawdowns,
  - scenario risk under Synthetic Scenario Engine tests.

### 7.6 Phase 5 – Full cutover

- Once v2 demonstrates stable behavior and passes all tests:
  - shift all relevant strategies to v2.
  - keep v1 in **read-only archival** mode:
    - legacy reports,
    - occasional cross-checks.

---

## 8. Rollback Strategy

### 8.1 Operational rollback

If v2 exhibits unacceptable behavior in production:

- Immediately reduce or zero-out v2 capital allocation.
- Optionally revert to:
  - v1 engines (if still wired to live trading), or
  - a conservative fallback portfolio (e.g. hedged benchmark ETFs) until issues are resolved.

Conditions for triggering rollback should be defined:
- drawdown thresholds,
- constraint violation counts,
- anomalies in regime/stability/fragility signals.

### 8.2 Code and config rollback

- Use version control tags for major v2 releases.
- Use `engine_configs` versioning to:
  - mark previous stable configs,
  - roll back to prior config IDs if a new config proves problematic.

---

## 9. Decommissioning v1

Once v2 has been stable for a sufficient period:

- Mark v1 code as deprecated:
  - Move `prometheus/legacy/` to a separate archival branch or keep it clearly separated in main.
  - Remove v1 from CI and active testing; keep a minimal smoke test for archival buildability if desired.

- DB objects:
  - Keep v1 tables in read-only mode for some time.
  - If storage/complexity becomes an issue, export them to cold storage (backups, dumps) before dropping.

- Documentation:
  - Update all README/WARP docs to reference v2 only.
  - Archive v1-specific docs into a `docs/legacy/` area.

---

## 10. Integration with Testing and Kronos

- All migration phases must respect the testing and gating plan (180):
  - new engine implementations ship with tests,
  - configs are promoted via Kronos experiments and numeric gates.

- Kronos plays a central role in:
  - comparing v1 vs v2 behavior (using decision/outcome logs where both exist),
  - managing config experiments that approximate or improve on v1 strategies,
  - ensuring only well-tested configs receive production capital.

---

## 11. Summary

This migration plan:
- preserves v1 as a reference while building v2 in parallel,
- moves data and configs via additive, auditable steps,
- relies on shadow mode, backtests, and scenario tests to validate v2,
- defines explicit cutover and rollback processes.

Executed carefully, it lets Prometheus evolve into the v2 architecture without losing the empirical lessons of v1 or exposing capital to untested behavior.