# 180 – Testing, Validation, and Gating Specification

## 1. Purpose

This document defines how Prometheus v2 is **tested, validated, and gated** at multiple levels:
- Code: unit and integration tests.
- Data: schema and quality validation.
- Engines: offline validation, backtests, and scenario-based checks.
- Configs: Kronos-driven experiments and promotion gates.

The goal is a system where **no change to models, configs, or code** reaches production trading without:
- automated tests passing,
- backtests and scenario tests meeting minimum standards,
- an explicit, auditable approval step.

---

## 2. Scope

Covers the entire stack described in 010, 020, 030, 035, 100–170, 160, and 200:
- Core infra: config, logging, DB, calendars, orchestration.
- Data ingestion: market, macro, text, profiles.
- Representation layer: encoders, embeddings, profiles.
- Engines: Regime, Stability & Soft-Target, Fragility Alpha, Assessment, Universe, Portfolio & Risk.
- Synthetic Scenario Engine.
- Meta-Orchestrator (Kronos) and its experiments.
- APIs and Monitoring/UI surfaces.

Does **not** cover broker connectivity or live exchange simulators in detail; those will have their own integration tests.

---

## 3. Test Taxonomy

### 3.1 Code-level tests

- **Unit tests**
  - Small, fast tests with no DB or external services.
  - E.g., feature calculations, calendar functions, encoders with dummy data, utility functions.
  - Must run within seconds and be suitable for per-commit CI.

- **Integration tests**
  - Use a test Postgres instance and small fixture datasets.
  - Exercise cross-module behavior:
    - ingestion → DB → engine call → DB write.
    - orchestration stubs calling multiple engines.
  - Marked clearly (e.g. `pytest -m integration`).

- **Property-based tests**
  - For critical numerical components (e.g., portfolio optimization, factor model algebra):
    - invariants (homogeneity, monotonicity, bounds) expressed as Hypothesis properties.

### 3.2 Data validation

- **Schema validation**
  - Every table defined in 020 has:
    - column type checks,
    - non-nullability where required,
    - foreign-key consistency (e.g., instruments, markets, issuers).

- **Data quality checks**
  - For time-series tables (prices, returns, factors, macro):
    - missing data thresholds,
    - extreme outlier detection (returns > X sigma, etc.),
    - monotonic constraints where applicable (e.g. cumulative indices).
  - For profiles and embeddings:
    - structural completeness of ProfileSnapshot,
    - embedding norms within expected ranges.

- **Ingestion DAG QC** (012/013)
  - DAGs terminate on **QC tasks** that:
    - compute summary statistics per day/market,
    - compare to rolling baselines,
    - emit alerts when deviations exceed thresholds.

### 3.3 Engine validation

For each engine, we define validation tests beyond pure unit tests.

- **Regime Engine (100)**
  - Stability of cluster assignments over small perturbations of input.
  - Sanity checks:
    - regime frequencies vs historical expectations,
    - transitions not dominated by impossible jumps.

- **Stability & Soft-Target Engine (110)**
  - Value ranges for StabilityVector and SoftTargetClass.
  - Monotonic connections:
    - entities with worse metrics (e.g. leverage, volatility) should not appear more stable than obviously better peers.

- **Fragility Alpha (135)**
  - Consistency between SoftTargetScore and produced alpha ideas:
    - fragile entities should more often appear on the short/hedge side under relevant scenarios.
  - Scenario tests with the Synthetic Scenario Engine:
    - under specific adversarial scenarios, Fragility Alpha should flag the intended vulnerable entities.

- **Assessment Engine (130)**
  - Cross-sectional sanity:
    - rank correlation with simple baseline scores on clean universes,
    - no persistent sign-flip errors when obvious signals exist (e.g. very strong positive signal mapping to a strong negative score).
  - Calibration tests for probabilistic outputs (where applicable).

- **Universe Engine (140)**
  - Hard constraints are always satisfied:
    - liquidity, asset-class filters, blacklist/whitelist rules.
  - No banned instruments; required core holdings appear in CORE or SATELLITE when conditions met.

- **Portfolio & Risk Engine (150)**
  - Feasibility and constraint adherence:
    - sum of weights, leverage caps, position/sector limits.
  - Consistency against simple baselines:
    - on small toy universes, solutions close to analytical or brute-force optima.
  - Scenario risk:
    - uses ScenarioSets to ensure no bizarre behavior (e.g. infinite leverage under mild shocks).

- **Synthetic Scenario Engine (170)**
  - Statistical properties of generated scenarios:
    - mean/variance/correlation vs calibration data,
    - bounds on returns (no impossible 1000x moves unless explicitly configured).
  - Reproducibility under fixed seeds.

- **Meta-Orchestrator (160)**
  - Deterministic performance reports given fixed decision/outcome inputs.
  - Experiment lifecycle invariants (status transitions, logging completeness).

### 3.4 End-to-end workflows

- Small E2E tests that run a truncated version of:
  - data ingestion for a few instruments and days,
  - profiles/encoders,
  - regimes + stability + fragility + assessment + universe + portfolio,
  - synthetic scenarios + scenario risk,
  - Kronos performance summary.

These should use fixed fixture data and run within a few minutes.

---

## 4. Test Harness & Environments

### 4.1 Environments

- **Local dev**
  - Unit tests and small integration tests.

- **CI environment**
  - Runs fast tests on every push/PR.
  - Nightly / scheduled jobs for heavier backtests and scenario runs.

- **Research/backtest environment**
  - Shares codebase but may have larger datasets and more relaxed time limits.
  - Where Kronos’ Meta Backtest Scheduler can explore experiments.

### 4.2 DB test harness

- Use a dedicated test database/schema.
- For integration tests:
  - apply Alembic migrations for the test schema,
  - load minimal fixture data (e.g. a handful of instruments, a short date range),
  - run tests inside a transaction or isolated schema, then rollback/drop.

### 4.3 Backtest harness

A **Backtest Service** used by engines and by Kronos:

- Inputs:
  - engine configs and IDs,
  - universe definitions or portfolio IDs,
  - historical date ranges,
  - ScenarioSets (optional).

- Outputs:
  - time-series of portfolio states and decisions,
  - aggregated performance metrics (P&L, Sharpe, drawdown, turnover),
  - scenario-based metrics when applicable.

Backtests should be:
- deterministic under fixed seeds,
- reproducible from stored config + generator specs (for scenarios).

---

## 5. Gating and Quality Thresholds

### 5.1 Code change gates

- **Per-commit / PR**
  - All unit tests must pass.
  - Linting and type checks (once defined in 010) must pass.

- **Pre-merge to main**
  - Integration tests must pass.
  - Any modified modules require associated tests or explicit justification.

### 5.2 Engine/config gates (Kronos + experiments)

For an experiment to be **eligible for promotion**:

- Backtest criteria:
  - metrics must not significantly degrade vs baseline configs beyond policy thresholds (e.g. Sharpe drop, max drawdown increase, turn-over explosion).
  - must pass scenario-based risk checks for a defined scenario battery:
    - baseline bootstraps,
    - fragility adversarial scenarios,
    - regulatory/named scenarios.

- Robustness criteria:
  - no catastrophic failures on subset markets or regimes,
  - no persistent violations of hard constraints.

These criteria are implemented as numeric policies; Kronos evaluates them and presents a **summary verdict** alongside raw metrics.

### 5.3 Data and ingestion gates

- Ingestion DAGs must:
  - complete schema validation and QC tasks,
  - not exceed missing-data and outlier thresholds.

- If thresholds are breached:
  - affected markets or universes are marked as **degraded**,
  - engines either:
    - fall back to conservative defaults, or
    - are prevented from running for that context (with alerts).

---

## 6. Baselines and Golden Backtests

### 6.1 Golden backtest suite

Define a **small, canonical backtest suite**:
- A handful of representative strategies and portfolios,
- Covering multiple markets (e.g. US_EQ, EU_EQ, FX_GLOB),
- Using fixed historical windows and ScenarioSets.

For each run we store:
- summary metrics (Sharpe, drawdown, turnover, hit-rates),
- key distributional stats,
- config and scenario versions.

Any substantial change to engines, factor models, or portfolio optimization must be compared to this suite:
- If deviations exceed tolerance bands, the change is blocked or flagged for manual review.

### 6.2 Monitoring regressions over time

- Kronos tracks performance and risk metrics per config over rolling windows.
- Monitoring/UI (200) shows trend lines; sudden degradations can be traced to specific config or code changes.

### 6.3 Negative Config Suite ("clusterfuck" tests)

In addition to golden backtests, we maintain a **Negative Config Suite** of deliberately bad or nonsensical configs to act as **negative controls** for the full gating pipeline:

- Each negative config is stored in `engine_configs` and/or experiment metadata with a label such as `expected_outcome = "NEGATIVE_CONTROL"`.
- Examples:
  - Assessment configs that randomize or invert obvious signals.
  - Universe configs that ignore liquidity or blacklist constraints.
  - Portfolio configs that request unreasonable leverage or broken risk aversion.
- For each negative config we define expectations, e.g.:
  - Sharpe and other performance metrics must be significantly **worse** than baseline.
  - Scenario-based risk must show clearly unacceptable behavior.
  - Gating policies must **reject** these configs (they must never be eligible for promotion).

Kronos and the Backtest Service periodically run this Negative Config Suite (e.g. nightly/weekly) through the same backtest + scenario battery used for candidate configs. If any negative config would pass the current numeric gates, this is treated as a **test failure** for the gating logic itself and triggers investigation.

---

## 7. Observability and Debuggability

- **Structured logging** for engines and backtests with:
  - config IDs, decision IDs, context IDs,
  - seeds, data ranges, ScenarioSet IDs.

- **Debug runs**
  - Ability to re-run a given backtest or scenario analysis with the same IDs.
  - Exportable artifacts (e.g. CSV/Parquet summaries, plots via notebooks).

- **UI hooks**
  - From Monitoring/UI, jump from a degraded metric directly to:
    - the underlying experiment,
    - its backtest runs,
    - its scenario risk reports.

---

## 8. Relationship to Threat Models and Crisis-Pattern Features

The testing and validation strategy is aligned with the threat models (defensive and offensive perspectives):
- Scenario batteries explicitly include adversarial/fragility tests.
- Experiments and configs are rejected if they:
  - materially increase vulnerability to identified attack patterns,
  - reduce robustness in critical crisis regimes.

For features derived from crisis/extraction research (see 045):
- Treat them as **one feature family** (e.g. `crisis_extraction_features`).
- Kronos should routinely run **ablation tests**:
  - Compare configs with and without this feature family.
  - Flag any configs whose apparent performance relies almost entirely on these features.
- Evidence levels should be tracked:
  - Weak (anecdotal/small-sample), Moderate (several crises), Strong (many regimes/countries).
  - Use weak features primarily as risk flags and explanatory context.

This enforces the epistemic stance that narrative-derived features are **hypotheses to be tested**, not truths to be hard-coded.

---

## 9. Summary

The testing and validation strategy is aligned with the threat models (defensive and offensive perspectives):
- Scenario batteries explicitly include adversarial/fragility tests.
- Experiments and configs are rejected if they:
  - materially increase vulnerability to identified attack patterns,
  - reduce robustness in critical crisis regimes.

---

## 9. Summary

This spec defines:
- a layered test taxonomy (unit → integration → engine validation → E2E),
- a shared backtest and scenario harness,
- numeric gates for code, data, engines, and configs,
- tight integration with Kronos (160), Synthetic Scenarios (170), and Monitoring/UI (200).

Together, these make Prometheus v2 test-heavy by design: engines and configs must earn their way into production through repeatable evidence, not intuition.