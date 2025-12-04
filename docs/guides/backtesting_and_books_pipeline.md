# Backtesting, Books, and Shared State Spaces

This document describes how Prometheus v2 wires together shared state spaces (encoders, regime, stability, profiles) with engines (Assessment, Universe, Portfolio & Risk, Meta-Orchestrator) for training and backtesting books/sleeves.

It answers:
- What shared spaces exist and what they store.
- Which components depend on which others.
- The exact ordering of offline preparation, model training, and sleeve backtests.

## 1. Shared State Spaces (Conceptual)

Throughout the system we maintain a small number of canonical, time-indexed state spaces. All higher-level engines operate on top of these.

### 1.1 Canonical Data & Calendars

- Historical prices, volumes, returns, and basic fundamentals.
- Instrument/issuer registry.
- Trading calendars per region/asset class.

Everything else assumes this layer is correct and queryable.

### 1.2 Numeric Embedding Space

- Built by the numeric encoder over sliding windows of market data.
- For each `(entity_type, entity_id, as_of_date, window_spec)` we store an embedding vector `z_numeric`.
- Used primarily by:
  - Regime Engine (market-level windows).
  - Pattern discovery / factor analysis.

### 1.3 Regime Space

- For each `(region, as_of_date)` we store a `RegimeState`:
  - `regime_label` in {CRISIS, RISK_OFF, CARRY, NEUTRAL, ...}.
  - `regime_embedding` (often equal or closely related to a numeric embedding).
  - `confidence` and metadata.
- Derived from numeric embeddings plus clustering/prototypes (NumericRegimeModel).

### 1.4 Stability / Soft Target Space (STAB)

- For each `(entity_type, entity_id, as_of_date)` we store:
  - `StabilityVector`: component scores (vol, drawdown, trend, etc.) and an overall stability/fragility index.
  - `SoftTargetState`: mapped soft-target class (STABLE/WATCH/FRAGILE/TARGETABLE/BREAKER) and component contributions.
- Derived from historical prices (and later profiles, joint embeddings, macro) via StabilityModel.

### 1.5 Profile / Issuer Space

- For each `(issuer_id, as_of_date)` we store a `ProfileSnapshot` (conceptual):
  - Structured fields: sector, size, leverage, profitability, quality metrics.
  - Text references: filings, news summaries, transcripts.
  - `profile_embedding`: dense vector combining structured + text features.
  - Optional regime-behavior traits and risk flags.
- Used heavily by Assessment, Universe, Stability/Black Swan.

These spaces are **shared**: multiple downstream engines read the same regime, stability, and profile states, rather than recomputing them ad hoc.

## 2. Engine Dependency Graph (High-Level)

This section summarizes, for each engine, what it depends on and what it produces.

### 2.1 Encoders

- **Depends on:** Canonical data & calendars.
- **Produces:**
  - Numeric window embeddings (`z_numeric`).
  - Text embeddings.
  - Joint text+numeric embeddings (later phases).

### 2.2 Regime Engine

- **Depends on:**
  - Numeric embeddings over market-level windows.
  - (Later) joint embeddings with macro text.
- **Produces:**
  - `RegimeState(region, as_of_date)` for each relevant region.
- **Consumed by:**
  - Assessment (feature `r(t)`).
  - Universe (regime-aware universes).
  - STAB/Black Swan (regime-dependent thresholds).
  - Meta-Orchestrator (conditioned performance metrics).

### 2.3 Stability / STAB Engine

- **Depends on:**
  - Prices and returns.
  - Trading calendars.
  - (Later) profiles and joint embeddings.
- **Produces:**
  - `StabilityVector(entity, as_of_date)`.
  - `SoftTargetState(entity, as_of_date)`.
- **Consumed by:**
  - Assessment (penalize expected returns for fragile names).
  - Universe (exclude or de-weight extreme soft-targets).
  - Black Swan (fragility inputs).
  - Portfolio & Risk (risk budgets and constraints).

### 2.4 Profiles Engine

- **Depends on:**
  - Fundamentals and static descriptors.
  - Text embeddings from filings/news.
- **Produces:**
  - `ProfileSnapshot(issuer, as_of_date)` with `profile_embedding` and risk traits.
- **Consumed by:**
  - Assessment (core feature `p_O(t)`).
  - Universe (quality screens, style buckets).
  - STAB/Black Swan (profile-driven fragility components).

### 2.5 Assessment Engine

- **Depends on:**
  - `profile_embedding p_O(t)`.
  - `RegimeState r(t)`.
  - `SoftTargetState s_I(t)` / stability components.
  - Recent price/factor history features.
  - (Later) text embeddings summarizing recent news.
- **Produces (per horizon H):**
  - `expected_return_H(I, t)` or a normalized score per instrument.
  - Optional labels (strong_buy/buy/hold/sell/short).
- **Consumed by:**
  - Universe Engine (ranking/filtering signals).
  - Portfolio & Risk (alpha vector for optimization).
  - Meta-Orchestrator (config performance evaluations).

### 2.6 Universe Selection Engine

- **Depends on:**
  - Assessment outputs per horizon.
  - STAB states and profile traits.
  - Regime state.
  - Strategy configs (style, liquidity, exclusions).
- **Produces (per strategy/book):**
  - `U_book(t)` – candidate instruments for that book at time t.
  - Optional inclusion scores/tiers.
- **Consumed by:**
  - Portfolio & Risk for that book.

### 2.7 Portfolio & Risk Engine

- **Depends on:**
  - Universe `U_book(t)` for each book.
  - Assessment scores for those instruments.
  - Risk model (covariance and factor exposures).
  - STAB/Black Swan metrics.
  - Constraints and risk budgets (from configs + Meta-Orchestrator).
- **Produces:**
  - `TargetPortfolio_book(t)` – weights/positions per instrument within that book.
  - Risk reports (ex-ante risk, factor exposures, stress tests).
- **Consumed by:**
  - Execution Service (to generate orders).
  - Meta-Orchestrator (for realized outcomes).

### 2.8 Meta-Orchestrator (Kronos v2)

- **Depends on:**
  - Decision logs from all engines (inputs, configs, outputs, realized PnL).
  - Regime and STAB history snapshots at decision times.
  - (Optionally) Synthetic scenario results.
- **Produces:**
  - Config recommendations per engine.
  - Sleeve/book risk budgets (possibly regime-dependent).
  - Performance analytics.
- **Consumed by:**
  - Engine configuration layer.
  - Human operators.

### 2.9 Execution Service

- **Depends on:**
  - Target portfolios from all active books.
  - Current holdings.
  - Broker/exchange constraints.
- **Produces:**
  - Concrete orders and trades.

## 3. Offline Preparation Dependencies

Before training Assessment models or backtesting sleeves, we must prepare the shared spaces and state histories.

### 3.1 Step 0 – Canonical Data & Calendars

- Load and validate historical market data, fundamentals, and calendars.
- This is the foundation for all later steps.

### 3.2 Step 1 – Numeric Embeddings

- For each relevant region and window spec (e.g. 63-day windows):
  - Compute and store numeric embeddings via the numeric encoder.
- These embeddings are used for regime discovery and potentially other analyses.

### 3.3 Step 2 – Offline Regime History

- Using numeric embeddings and a regime model (e.g. NumericRegimeModel):
  - Define regime prototypes/clusters.
  - Classify each `(region, as_of_date)` into a `RegimeState`.
- Persist `regimes` and `regime_transitions` in the runtime DB.

### 3.4 Step 3 – STAB / Stability History

- For each instrument over the historical period:
  - Run STAB model to compute `StabilityVector` and `SoftTargetState` at each date.
- Persist into `stability_vectors` and `soft_target_classes` tables.

### 3.5 Step 4 – Profile History

- For each issuer (and mapped instruments) over time:
  - Build and store `ProfileSnapshot` objects and `profile_embedding`s.
- This can be done at a lower frequency (e.g. monthly/quarterly) if fundamentals move slowly.

At the end of this phase, every (instrument, date) of interest has:
- Regime state for its region.
- Stability/soft-target state.
- A linked issuer profile embedding.

This is the minimum required shared context for Assessment and backtesting.

## 4. Assessment Model Training Pipeline

Given the prepared history, we train Assessment models per asset-class scope and horizon.

### 4.1 Define Scope and Horizon Grid

- Choose an asset-class/region scope, e.g. `US_EQ` (liquid US equities).
- Choose a small grid of horizons to explore, e.g. `H = {5d, 20d, 60d}`.

### 4.2 Build Datasets per Horizon

For each horizon `H`:

- For each `(instrument, as_of_date)` in the scope where `t + H` is within history:
  - Inputs `x_t`:
    - `profile_embedding p_O(t)` for the issuer.
    - `RegimeState r(region, t)`.
    - `SoftTargetState s_I(t)` and stability components.
    - Price/factor features over recent windows.
    - Static descriptors (sector, country, size, etc.).
  - Target `y_t^(H)`:
    - Realized forward return over horizon H (raw or excess), possibly winsorized.
- Store datasets (or define a reproducible data-building pipeline).

### 4.3 Train Assessment Models

- For each `H`:
  - Train `Assessment_<scope>_<H>` on its dataset.
  - Evaluate on held-out time slices (e.g. early period vs late period).
  - Save model artifacts and configuration IDs.

### 4.4 Evaluate By Regime

- For each trained model and horizon:
  - Compute predictive metrics (rank IC, decile spreads) overall.
  - Compute the same metrics **by regime label** (CRISIS, CARRY, etc.).
- This reveals which horizons and model configs are robust and where they shine/fail.

## 5. Sleeve / Book Backtesting Pipeline

A "book" or sleeve is a configuration that ties together:
- Scope (e.g. `US_EQ`).
- Horizon and Assessment model ID.
- Style (long-only vs long/short).
- Constraints (turnover, leverage, risk limits).
- Simple regime rules (e.g. off in CRISIS, scaled in RISK_OFF).

### 5.1 Define Candidate Sleeve Configs

Example for `US_EQ`:

- `CORE_20d`: long-only, low turnover, uses `Assessment_US_EQ_20d`.
- `CORE_60d`: long-only, uses `Assessment_US_EQ_60d`.
- `TACTICAL_5d`: small-risk, higher-turnover, uses `Assessment_US_EQ_5d`.

Each sleeve config specifies:
- Which Assessment model(s) to call.
- How Universe builds `U_book(t)`.
- Portfolio & Risk parameters specific to that sleeve.

### 5.2 Backtest Procedure per Sleeve

For each sleeve config and for each historical period:

1. **Walk-forward loop over dates**:
   - At each `t` in the backtest window:
     - Read precomputed `RegimeState`, `StabilityState`, and profiles.
     - Score instruments via the sleeve’s Assessment model(s) using only data up to `t`.
     - Build universe `U_book(t)` (filters + ranking using Assessment, STAB, profiles).
     - Run Portfolio & Risk to produce `TargetPortfolio_book(t)` within that universe and constraints.
     - Simulate execution and record positions and PnL.

2. **Aggregate performance metrics**:
   - Overall Sharpe, max drawdown, turnover, capacity indicators.
   - Regime-conditional metrics (per regime label).
   - Period-split metrics (e.g. early vs late half of history).

3. **Store metrics as a vector**:
   - `m(config) = [Sharpe_overall, MaxDD, Turnover, Sharpe_CARRY, Sharpe_CRISIS, ...]`.

### 5.3 Config-Space Analysis (Meta-Orchestrator)

- Collect `m(config)` for all tested sleeve configs.
- Use these metric vectors to:
  - Identify Pareto-efficient configs (cannot improve one key metric without hurting another).
  - Prefer simpler configs when performance is similar.
  - Detect configs that only work in narrow slices (e.g. great Sharpe in CARRY but catastrophic in CRISIS).
- Select a small set of sleeves to run live (e.g. `US_CORE_EQ_20d`, plus or minus one tactical sleeve), with initial risk budgets per sleeve.

## 6. Live Operation Dependencies

Once sleeves are chosen and wired into engine configs, live operation follows the same dependency ordering as the backtests but operates on "today" instead of historical t.

At each decision time (e.g. EOD):

1. **Data & Encoders**
   - Ingest latest prices/fundamentals.
   - Update numeric embeddings for required windows.

2. **Regime & STAB**
   - Regime Engine classifies `RegimeState(region, today)`.
   - STAB engine updates `StabilityVector` and `SoftTargetState` for relevant instruments.

3. **Assessment for Active Sleeves**
   - For each sleeve, run its configured Assessment model(s) across the coverage universe.

4. **Universe per Sleeve**
   - Build `U_book(today)` using Assessment scores, STAB, profiles, and configs.

5. **Portfolio & Risk per Sleeve**
   - Optimize `TargetPortfolio_book(today)` under constraints and current risk budgets.

6. **Meta-Orchestrator & Execution**
   - Meta-Orchestrator may adjust sleeve-level risk budgets based on regime and recent performance.
   - Execution Service nets all book-level target weights into trade lists and sends orders.

All dependencies are the same as in the backtest; the only difference is that in backtest we simulate this process over historical t, while live we execute it at the current time.

## 7. Summary

- Shared spaces (regime, stability, profiles, numeric embeddings) are computed first and reused everywhere.
- Assessment models are trained on top of those spaces for specific horizons and scopes.
- Books/sleeves are configurations that bind an Assessment model, Universe rules, and Portfolio & Risk constraints.
- Backtests simulate the full pipeline for each sleeve, producing metric vectors that live in a "config space" for Meta-Orchestrator.
- Live trading reuses the same dependency structure at a single time point, with Meta-Orchestrator governing which sleeves run and how much risk they take based on observed performance and current regime.