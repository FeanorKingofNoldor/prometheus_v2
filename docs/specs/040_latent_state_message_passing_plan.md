# 040 – Latent State & Message Passing Plan

This document outlines **where** in Prometheus v2 we should apply the
latent-state + message-passing pattern ("entity absorbs relevant
embeddings from its neighbours/events") and **how** it integrates with
existing subsystems.

The goal is to have **one coherent pattern** that can be reused across
multiple engines, but applied **incrementally** and with clear
priorities.

## 1. Pattern Summary

Core idea:

- Each logical entity (issuer, regime, book, etc.) has a **state
  vector** `h(t)` in a learned latent space.
- Incoming data (news, price windows, macro events, exposures, etc.) is
  encoded into **event vectors** `x` in the same space (or projected
  into it).
- At each update step, for each entity we:
  - Retrieve a **small set of relevant events** via a combination of
    hard links and vector similarity.
  - Aggregate them via attention/message passing into a **summary
    message** `m(t)`.
  - Update state `h(t+1) = f(h(t), m(t))` with a simple, testable
    update rule (e.g. GRU-style, or gated EMA).
- Downstream engines (STAB, Universe, Assessment, Allocator, etc.) read
  **state vectors and derived scalars** instead of raw events.

We refer to this generically as the **Latent State Engine (LSE)**
pattern.

## 2. State Families & Priorities

We define several **state families**. Each has its own state space,
encoders, and update logic, but all share the same LSE pattern.

### 2.1 ISSUER_STATE (highest priority)

**Entity:** issuers (companies, sovereigns, indices, sectors).

**Role:** dynamic profile / risk state of an issuer, integrating:

- Price behaviour (already partially captured in STAB & Profiles v1).
- News & text flow (headlines, filings, rating changes, etc.).
- Potentially fundamental deltas (balance sheet, earnings surprises).

**Inputs / events:**

- Price windows (numeric embeddings already exist for STAB/encoders).
- News articles and events (text embeddings projected into issuer space).
- Issuer-specific discrete events (earnings, downgrades, lawsuits,
  corporate actions).

**Outputs:**

- `h_issuer(t)` vectors (per issuer, per date) in
  `R^d_issuer_state`.
- Derived scalars, e.g.:
  - `news_stress_score`, `event_intensity`.
  - topic/cluster scores later.

**Consumers:**

- STAB v2 (news-aware stability model).
- Profiles v2 (richer profile embeddings, risk flags).
- Universe v2 (screening on issuer-level news/structural state).

**Priority:** **highest**. This is the first place we apply the LSE
pattern.

### 2.2 REGIME_STATE (second priority)

**Entity:** regions/markets (US, EU, ASIA, GLOBAL, sectors).

**Role:** dynamic macro/regime state, integrating:

- Cross-asset returns (indices, rates, FX, commodities).
- Macro time series (inflation, CB decisions, PMIs, etc.).
- Macro/news text flow (CB speeches, policy headlines, geopolitical
  news).

**Inputs / events:**

- Cross-asset numeric windows (already used in RegimeEngine numeric
  model).
- Macro time series windows.
- Macro/news articles.

**Outputs:**

- `h_regime(region, t)` in `R^d_regime_state`.
- Derived regime scalars (risk-on/off, liquidity stress, etc.).

**Consumers:**

- RegimeEngine v2 (may replace or augment current numeric-only model).
- Book allocator (weights per book based on regime).
- Universe / STAB may use regime state as a feature.

**Priority:** **medium**; good candidate after ISSUER_STATE is stable.

### 2.3 BOOK_STATE (third priority)

**Entity:** trading books/strategies (e.g. `US_CORE_LONG_EQ`,
`FRAG_SHORT_EQ`, `MACRO_HEDGE`).

**Role:** dynamic state of each book, integrating:

- PnL and drawdown history.
- Volatility, skew, tail behaviour.
- Exposure to regimes, factors, sectors.

**Inputs / events:**

- Daily (or weekly) PnL, vol, drawdown metrics.
- Exposure changes (beta to indices, sectors, factors).
- Regime state & other engine outputs.

**Outputs:**

- `h_book(book_id, t)` in `R^d_book_state`.
- Book-level risk scalars ("overextended", "recent trauma", etc.).

**Consumers:**

- Book allocator / Meta engine (decide how much risk to allocate to
  each book).
- Monitoring / alerting.

**Priority:** **medium/low**; important for meta-allocation but not
blocking ISSUER_STATE/REGIME_STATE work.

### 2.4 NETWORK_STATE (contagion / graph risk) (later)

**Entity:** nodes in a financial graph:

- Issuers, banks, sovereigns, sectors.

**Role:** model contagion and systemic risk via message passing on a
graph.

**Inputs / events:**

- Node states (ISSUER_STATE, REGIME_STATE).
- Edge types and weights (exposures, supply chains, cross-holdings).

**Outputs:**

- `h_node(t)` in `R^d_network_state` capturing systemic stress.

**Consumers:**

- STAB / Fragility engines.
- Assessment / risk dashboards.

**Priority:** **later**; more complex and depends on ISSUER_STATE being
solid.

### 2.5 CROSSASSET_STATE (instruments across asset classes) (later)

**Entity:** individual instruments (equities, ETFs, futures, bonds, FX,
commodities).

**Role:** embed instruments into a unified cross-asset space; enable
cross-asset hedging, co-movement, and cluster analysis.

**Inputs / events:**

- Return/vol/volume windows.
- Possibly text embeddings for asset-specific news.

**Outputs:**

- `h_instrument(t)` in `R^d_crossasset_state`.

**Consumers:**

- Hedge selection / cross-asset universe.
- Assessment / Exposure analysis.

**Priority:** **later**; natural extension once basic universes &
books are live.

## 3. Integration with Existing Prometheus v2 Code

This section enumerates where the LSE pattern plugs into current code.

### 3.1 Profiles subsystem

Current:

- `prometheus/profiles` builds `ProfileSnapshot` objects with:
  - `structured` JSON (issuer metadata + price-based numeric features).
  - `risk_flags` from price features.
  - `embedding` via `BasicProfileEmbedder` (simple handcrafted mapping).

Future with LSE:

- Add an `ISSUER_STATE` engine that maintains `h_issuer(t)` over time.
- Profiles v2:
  - Either:
    - Replace `embedding` with `h_issuer(t)` (or a simple projection of
      it), or
    - Store both snapshot and state embedding.
  - Add risk flags derived from `h_issuer(t)` (e.g. news stress,
    structural flags).

Benefits:

- Profiles become **dynamic** and reflect event history, not just
  simple price snapshots.
- All downstream engines that consume Profiles (STAB, Universe,
  Assessment) benefit automatically.

### 3.2 STAB (Stability / Soft Target engine)

Current:

- `BasicPriceStabilityModel` uses price-based features only.
- It already integrates `weak_profile` via Profiles v1.

Future with LSE:

- Extend STAB to consume `h_issuer(t)` and/or scalars derived from it.
- Examples:
  - `news_instability_score` from issuer news state.
  - `event_intensity` (frequency / magnitude of recent events).
- STAB v2 components:
  - `instability_price`, `instability_news`, `instability_macro`,...
  - Combined into a richer soft-target index.

Benefits:

- STAB can respond to **informational stress** even before it is fully
  realised in prices.
- Better ranking of fragile names; improved early warning.

### 3.3 Regime engine

Current:

- Numeric RegimeEngine uses numeric price/volume embeddings.

Future with LSE:

- Introduce `REGIME_STATE` vectors integrating:
  - Cross-asset windows.
  - Macro series.
  - Macro/news text.
- RegimeEngine v2 reads from `h_regime(region, t)` instead of recomputing
  everything from scratch.

Benefits:

- More robust, multi-modal regime estimates.
- Clean hook for macro/news into allocation & hedging without rewriting
  everything.

### 3.4 Universe engine

Current:

- `BasicUniverseModel` uses:
  - 63d liquidity features (volume, realised vol).
  - Latest STAB state (with `weak_profile`).

Future with LSE:

- Universe v2 can:
  - Directly screen on issuer state features (e.g. intensity of
    negative news, structural issues).
  - Construct multiple universes:
    - Long-friendly (`CORE_EQ_*`) filtering out highly stressed issuers.
    - Short/fragility universes (`FRAGILITY_EQ_*`) focusing on stressed
      issuers.

Benefits:

- High-information universes with **minimal extra per-instrument
  compute**, because the heavy lifting is in the shared issuer state.

### 3.5 Assessment & Meta engines (future)

Future modules can consume the same state vectors:

- Assessment engine: summarises risk per entity (issuer, book) using
  state vectors.
- Meta/Allocator engine: uses `BOOK_STATE` and `REGIME_STATE` to adjust
  book risk dynamically.

## 4. Implementation Plan (High-Level)

We plan to implement LSE in **phases**, each with its own experiments
and backtests.

1. **Pipeline State Machine & Books v0** (current work, no LSE changes):
   - Finish `engine_runs` / phases.
   - Wire current Regime, Profiles v1, STAB v1, Universe v1, and at
     least one book.

2. **News & Issuer State – Storage & Encoders (N1):**
   - Add `news_articles` & `news_article_embeddings` to **historical
     DB**.
   - Implement `NewsIngestor` + `NewsEmbedder` (frozen encoder v1).

3. **IssuerStateEngine v0 – simple features (N2):**
   - Add `issuer_state_embeddings` table.
   - Implement a simple state (counts/sentiment) with no attention yet.
   - Plug into pipeline `SIGNALS` phase.

4. **IssuerStateEngine v1 – full message passing (N3):**
   - Implement retrieval + attention aggregation + update rule.
   - Populate `h_issuer(t)` over historical data for backtests.

5. **STAB v2 (N4):**
   - Integrate news-driven issuer state into STAB as new components.
   - Backtest vs STAB v1.

6. **Universe v2 / Books v1 (N5):**
   - Update Universe and selected books to use STAB v2 + issuer state.
   - Backtest multi-book behaviour.

7. **REGIME_STATE, BOOK_STATE, NETWORK_STATE, CROSSASSET_STATE (later
   phases):**
   - Apply the same pattern to other families as needed, reusing the
     same infra.

## 5. Build on Current Code or Start from Scratch?

We **build on what we have**.

Reasons:

- Core infra (config, DB, TimeMachine, encoders, Regime, STAB, Profiles,
  Universe) is **real and coherent** and exactly what the LSE pattern
  needs to sit on top of.
- LSE mostly adds:
  - New tables and modules (state embeddings, news embeddings).
  - New engines (IssuerStateEngine, RegimeStateEngine, BookStateEngine).
  - Additional components in existing models (STAB v2, Universe v2).
- Starting from scratch would:
  - Throw away working, tested engines.
  - Not change the underlying idea; we would rebuild the same infra but
    slower.

We may refactor some pieces (e.g. profile embeddings, STAB inputs) to be
cleaner LSE consumers, but **we do not reset the project**. Instead, we
layer LSE on top of the existing architecture as a new capability and
refine engines iteratively.
