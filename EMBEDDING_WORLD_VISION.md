# Prometheus v2 – Full Embedding World Vision

## 1. Purpose

This document describes how Prometheus v2 **should run** once the embedding
stack (numeric, text, joint) is fully integrated into the daily pipeline and
backtests, and what is still missing to reach that state.

This is a **design/intent** document, not a strict reflection of current code.

---

## 2. High-Level Architecture in the Embedding World

At a high level there are three layers:

1. **Data & Feature Store**
   - Historical DB (`prometheus_historical`) holds raw data:
     - `prices_daily`, `returns_daily`, `volatility_daily`, `factors_daily`,
       `instrument_factors_daily`, fundamentals, `news_articles`.
   - Feature tables:
     - `numeric_window_embeddings` – numeric window encodings.
     - `text_embeddings` – text encodings (news, filings, transcripts, macro).
     - `joint_embeddings` – joint spaces (profile, regime, STAB, assessment
       context, portfolios, meta).

2. **Engines & Runtime Pipeline**
   - Engines consume **embeddings + minimal raw data** and produce:
     - Regimes, STAB states and risk, Assessment scores, universes,
       portfolios, risk actions, execution decisions.

3. **Meta, λ̂, and Training**
   - Offline training pipelines consume:
     - Embeddings + realised outcomes (returns, drawdowns, transitions,
       backtest metrics) to learn better models.
   - Runtime consumes their outputs (e.g. λ̂ CSVs, trained Assessment models).

The goal is that **most “thinking” happens in embedding space**, while the
pipeline and execution remain stable and relatively simple.

---

## 3. Embedding Surfaces Required in the Final System

### 3.1 Numeric Window Embeddings (`numeric_window_embeddings`)

Models (as of v0 spec):

- `num-regime-core-v1` – regime-oriented numeric windows
- `num-stab-core-v1` – stability/fragility features
- `num-profile-core-v1` – profile/fundamentals windows
- `num-scenario-core-v1` – scenario-oriented windows
- `num-portfolio-core-v1` – portfolio-level numeric features

**Coverage:**

- Entity scope:
  - `INSTRUMENT` (primary), `ISSUER`, `SECTOR`, `MARKET` (later)
- Time:
  - Daily as-of dates over a long history (ideally ≥15–25 years) for
    all instruments in the universe of interest.
- Window:
  - Default 63 trading days (quarterly lookback), with the option to
    add shorter/longer windows for specific models.

### 3.2 Text Embeddings (`text_embeddings`)

Core text models (v0):

- `text-fin-general-v1` – news/financial text (384-dim)
- `text-profile-v1` – issuer-centric text (filings, transcripts, profiles)
- `text-macro-v1` – macro/policy/market commentary

**Coverage:**

- NEWS:
  - All `news_articles` from at least 2010 onward (ideally earlier),
    encoded with `text-fin-general-v1`.
- Profile text:
  - Issuer-level documents (10-K, 10-Q, MD&A, transcripts) for
    `text-profile-v1`.
- Macro text (optional for v0):
  - Macro news and policy statements for `text-macro-v1`.

### 3.3 Joint Embeddings (`joint_embeddings`)

Spaces (from `docs/joint_spaces/` and specs):

- `PROFILE_CORE_V0` (`joint-profile-core-v1`)
  - Fuse numeric profile (`num-profile-core-v1`), behaviour (`num-regime-core-v1`),
    and profile text (`text-profile-v1`).
- `REGIME_CONTEXT_V0` (`joint-regime-core-v1`)
  - Fuse regime numeric (`num-regime-core-v1`) + macro/news text
    (`text-fin-general-v1` or `text-macro-v1`).
- `STAB_FRAGILITY_V0` (`joint-stab-fragility-v1`)
  - Combine `num-stab-core-v1` + scenario embeddings to describe stability
    state and fragility.
- `ASSESSMENT_CTX_V0` (`joint-assessment-context-v1`)
  - Master context vector per instrument/date, combining:
    - Profile joint embedding
    - Regime context embedding
    - STAB/fragility embedding
    - Recent news text context.
- Portfolio/Meta joint spaces (later iterations):
  - `joint-portfolio-core-v1`, `joint-meta-config-env-v1`, etc.

**Coverage:**

- Universe: all instruments you ever want to assess/backtest.
- Time: daily or regularly sampled as-of dates over the backtest and
  training periods.

---

## 4. Engines in the Embedding World

### 4.1 Regime Engine

**Goal:** classify regime state per region/date and provide regime risk.

**Inputs:**

- Numeric regime embeddings (`num-regime-core-v1`)
- Optionally joint regime context (`REGIME_CONTEXT_V0`)
- History of past regimes and transitions.

**Outputs:**

- `regimes` rows with:
  - `regime_label`, `confidence`, `regime_embedding`
- `regime_transitions` (transition history)
- Regime state-change risk series
  - via `RegimeStateChangeForecaster` and offline `backfill_regime_change_risk.py`.

### 4.2 STAB / Stability Engine

**Goal:** classify stability state and forecast soft-target changes.

**Inputs:**

- Numeric STAB embeddings (`num-stab-core-v1`)
- Joint STAB context (`STAB_FRAGILITY_V0`)
- Observed soft-target transitions over time.

**Outputs:**

- `stability_vectors`, `soft_target_classes`
- STAB state-change risk metrics (per instrument/cluster)
  - via `StabilityStateChangeForecaster` and
    `backfill_stability_change_risk.py`.

### 4.3 Assessment Engine

In the full embedding world, **context Assessment** is the primary backend.

**Inputs:**

- `ASSESSMENT_CTX_V0` embeddings (`joint-assessment-context-v1`)
- Possibly numeric factors (vol, beta, etc.) and meta-features.

**Outputs:**

- `instrument_scores` with:
  - `expected_return`, `score`, `confidence`, `signal_label`
  - For multiple horizons (e.g. 5/21/63 trading days).

The existing **basic Assessment** (price + STAB) remains as:

- A baseline model (`assessment-basic-v1`)
- A diagnostic or fallback when context embeddings are missing.

### 4.4 Universe Engine (BasicUniverseModel with λ and risk)

**Goal:** choose the daily investable universe for each sleeve.

**Inputs:**

- Assessment scores (basic or context) for the appropriate
  `assessment_strategy_id` and horizon.
- STAB classes and STAB risk scores.
- Regime risk (global region-level risk score).
- λ̂(x; features) predictions (opportunity density).

**Outputs:**

- `universe_members` for each `(universe_id, as_of_date)` with diagnostics:
  - λ‑related fields in `reasons` (e.g. `lambda_score`, `lambda_score_weight`)
  - STAB/Regime-related fields (risk scores, probabilities).

### 4.5 Portfolio Engine & Risk

**Goal:** convert universes and scores into target portfolios and
risk-managed weights.

**Inputs:**

- Universe memberships + Assessment scores.
- Scenario risk metrics (from scenario engines and STAB/Regime risk series).
- Constraints/caps/limits from portfolio/risk config.

**Outputs:**

- `target_portfolios` and `book_targets`.
- `risk_actions` for all weight adjustments.

### 4.6 Backtest & ExecutionBridge

**Goal:** simulate market and broker behavior faithfully over historical periods.

**Inputs:**

- TimeMachine + MarketSimulator for a given market and date range.
- Sleeve pipeline (STAB → Assessment → Universe → Portfolio → Risk).

**Outputs:**

- `backtest_runs`, `backtest_daily_equity`, `backtest_trades`.
- `orders`, `fills`, `positions_snapshots`, `executed_actions`.
- Exposure diagnostics (λ and risk metrics attached per-date).

### 4.7 Meta-Orchestrator

**Goal:** select the best sleeves/configs based on backtest evidence.

**Inputs:**

- `backtest_runs` + `DecisionOutcome`s
- Exposure diagnostics (lambda buckets, STAB/Regime risk exposure).

**Outputs:**

- `engine_decisions` rows for sleeve selection.
- Potentially, learned policies on how to combine sleeves in real time.

---

## 5. λ and Opportunity-Density in the Embedding World

### 5.1 Baseline λₜ(x)

Currently implemented in `backfill_opportunity_density.py`, λₜ(x) is:

- A function of **returns + realised vol + STAB class** per cluster
  `(market_id, sector, soft_target_class)`.
- Computed from `prices_daily` + `soft_target_classes`.

In the embedding world, λ̂(x; features) should be driven by features like:

- Aggregated numeric embeddings (e.g. mean/dispersion of
  `num-regime-core-v1` or `ASSESSMENT_CTX_V0` over cluster members).
- STAB and Regime risk scores.
- Possibly text-based context features.

### 5.2 λ̂ experiments and runtime

Offline:

1. Backfill λₜ(x) over a long period.
2. Build feature tables using embeddings + STAB/Regime context.
3. Train λ̂ models and output predictions with `run_opportunity_density_experiment.py`.
4. Write predictions CSVs with λ̂ per cluster/date.

Runtime / Backtests:

- Universes use `CsvLambdaClusterScoreProvider` to look up λ̂ and adjust
  ranking scores.
- Backtests and Meta record λ exposure diagnostics in
  `backtest_daily_equity.exposure_metrics_json` and `backtest_runs.metrics_json`.

---

## 6. Current Status vs Gaps

### 6.1 Implemented / Usable

- Numeric infrastructure: `NumericWindowEncoder`, `numeric_window_embeddings` table.
- Text infrastructure: HF-based encoders, `text_embeddings` table.
- Joint spaces: implementations and backfill scripts for profile, regime,
  STAB, assessment context.
- λₜ(x) baseline: `backfill_opportunity_density.py`.
- λ̂ runtime integration points:
  - `CsvLambdaClusterScoreProvider` + universe configs + backtest campaign.
- Backtest and Meta infrastructure:
  - Sleeve backtests, MarketSimulator, BacktestBroker, MetaOrchestrator wiring.
- Basic (non-embedding) engines and full-day core pipeline.

### 6.2 Partially Implemented

- Daily pipeline paths that **optionally** use embeddings (e.g. basic
  Assessment with `use_assessment_context=True`).
- Regime and STAB risk forecasters hooked into exposure diagnostics but not
  yet driven by learned embedding-based models.
- λ̂ training and deployment scripts (some pieces present, not fully wired).

### 6.3 Missing / To Be Done for “Full Embedding World”

1. **Dense embedding backfills for chosen periods**
   - Decide on initial training/backtest window (e.g. 2010–2024 or 2005–2024).
   - Backfill `numeric_window_embeddings` daily for that window and all
     required models.
   - Backfill text + joint embeddings (NEWS, profile, regime context, STAB,
     assessment context) for the same window.

2. **Flip engines to prefer embeddings where appropriate**
   - Regime Engine: use `num-regime-core-v1` / joint regime context as
     primary features, not raw prices.
   - STAB Engine: use `num-stab-core-v1` / joint STAB context if available.
   - Assessment: make `ContextAssessmentModel` the default backend once
     `ASSESSMENT_CTX_V0` is reliably populated.

3. **λ̂ models that explicitly consume embeddings**
   - Define feature schemas that include numeric/joint embeddings.
   - Implement `run_opportunity_density_experiment.py` with embedding-based
     feature loaders.
   - Ship predictions CSVs and validate they are being consumed by daily
     universes and backtests.

4. **End-to-end validation**
   - Run backtests with and without embeddings over identical periods.
   - Compare performance (Sharpe, drawdown, lambda-bucketed returns,
     regime-sliced performance).
   - Use MetaOrchestrator to select sleeves with embedding-based engines
     vs baseline.

5. **Scaling & Ops**
   - Make long-running backfills (numeric/text/joint) robust:
     - Chunking over dates/instruments.
     - Resumable jobs.
     - Monitoring and logging.
   - Consider a small embedding service for online inference to avoid
     re-running HF models in every script.

---

## 7. Summary

The **full embedding world** for Prometheus v2 is a system where:

- Numeric, text, and joint embeddings form a dense feature surface over
  markets, instruments, and time.
- Engines (Regime, STAB, Assessment, λ̂, Meta) are mostly **heads on top of
  this representation**, rather than ad hoc feature calculators.
- The daily pipeline and backtests consume embeddings directly and in a
  consistent, versioned way.
- Offline training backfills and λ̂ experiments periodically refresh model
  parameters and prediction surfaces consumed by the runtime.

The core infrastructure is already in place; the remaining work is mostly
about **backfilling embeddings for realistic horizons, flipping engine
backends to use them by default, and wiring λ̂/Meta around them**.