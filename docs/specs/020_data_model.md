# 020 – Data Model & Storage Plan

## 1. Purpose

Define the canonical data model and storage layout for Prometheus v2:
- What lives in the **historical DB** vs **runtime DB**.
- Schemas for instruments, issuers, market data, text/events, profiles.
- Embedding and feature stores.
- Decision and outcome logging for the Meta-Orchestrator.

All engines (100–170 specs) must rely on these tables and conventions.

---

## 2. Storage Architecture Overview

### 2.1 Databases

We separate storage into two logical databases:

1. **historical_db** (append-only, immutable after load)
   - Long-run historical market data (prices, returns, factors, vols, correlations).
   - Historical text/events (news, filings, macro events).
   - Derived historical features and embeddings (optional; can also be recomputed).

2. **runtime_db** (mutable, current state)
   - Instruments, issuers, portfolios, strategies.
   - Profile snapshots.
   - Engine configs and versions.
   - Decision logs, executed actions, and realized outcomes.

Both are assumed to be Postgres instances logically separated (can be same cluster with different schemas).

### 2.2 File/Object Storage

For large artifacts (embeddings, model artifacts, possibly full text bodies):
- Use object storage or filesystem with references in DB tables.
- Exact mechanism (e.g. S3, local FS) is implementation detail; DB stores URIs/paths.

---

## 3. Core Entities (runtime_db)

### 3.0 `markets`

Represents logical trading markets (US_EQ, EU_EQ, JP_EQ, FX_GLOB, etc.) used for
calendars, scheduling, and high-level grouping.

**Table:** `markets`

- `market_id` (PK, text) – e.g., `US_EQ`, `EU_EQ`, `JP_EQ`, `ASIA_EQ`, `FX_GLOB`.
- `name` (text)
- `region` (text) – e.g., `US`, `EU`, `JP`, `ASIA`, `GLOBAL`.
- `timezone` (text) – IANA TZ name (e.g., `America/New_York`).
- `calendar_spec` (jsonb) – optional structured config for holidays/early closes
  (or reference to external calendar source).
- `metadata` (jsonb)
- `created_at` (timestamptz)
- `updated_at` (timestamptz)

Instruments reference `market_id` to determine which TradingCalendar and
scheduling rules apply.

### 3.1 `issuers`

Represents companies, sovereigns, sectors, indices, and possibly composite entities.

**Table:** `issuers`

- `issuer_id` (PK, text)
- `issuer_type` (text/enum: `COMPANY`, `SOVEREIGN`, `SECTOR`, `INDEX`, `OTHER`)
- `name` (text)
- `country` (text, nullable)
- `sector` (text, nullable)
- `industry` (text, nullable)
- `metadata` (jsonb) – arbitrary attributes (e.g., rating, region groupings)
- `created_at` (timestamptz)
- `updated_at` (timestamptz)

### 3.2 `instruments`

Represents tradable instruments.

**Table:** `instruments`

- `instrument_id` (PK, text) – canonical ID (`asset_class:symbol` or similar)
- `issuer_id` (FK → issuers.issuer_id, nullable for indices/FX)
- `market_id` (FK → markets.market_id) – logical market grouping (US_EQ, EU_EQ, etc.)
- `asset_class` (text/enum: `EQUITY`, `FUTURE`, `OPTION`, `BOND`, `CDS`, `FX`, `ETF`, etc.)
- `symbol` (text) – exchange/native symbol
- `exchange` (text, nullable)
- `currency` (text)
- `multiplier` (numeric) – contract size multiplier
- `maturity_date` (date, nullable)
- `underlying_instrument_id` (text, FK → instruments, nullable for derivatives)
- `status` (text/enum: `ACTIVE`, `DELISTED`, etc.)
- `metadata` (jsonb)
- `created_at` (timestamptz)
- `updated_at` (timestamptz)

Indexes:
- by `issuer_id`, `asset_class`, `symbol`, `status`.

### 3.3 `portfolios`

**Table:** `portfolios`

- `portfolio_id` (PK, text)
- `name` (text)
- `description` (text)
- `base_currency` (text)
- `metadata` (jsonb)
- `created_at` (timestamptz)
- `updated_at` (timestamptz)

### 3.4 `strategies`

**Table:** `strategies`

- `strategy_id` (PK, text)
- `name` (text)
- `description` (text)
- `metadata` (jsonb)
- `created_at` (timestamptz)
- `updated_at` (timestamptz)

### 3.5 `profiles`

Stores issuer profile snapshots (structural state for Profiles/Fragility).

**Table:** `profiles`

- `profile_id` (PK, bigserial)
- `issuer_id` (FK → issuers.issuer_id)
- `as_of_date` (date)
- `structured` (jsonb) – normalized fundamentals, ratios, qualitative flags
- `embedding_vector_ref` (text, nullable) – reference to stored embedding (e.g. in `profile_embeddings` or external store)
- `risk_flags` (jsonb) – precomputed scores (e.g. leverage_score, governance_risk)
- `created_at` (timestamptz)

Constraints:
- Unique index on (`issuer_id`, `as_of_date`, `profile_id`) with `as_of_date` non-null.

---

## 4. Market Data & Factors (historical_db)

### 4.1 `prices_daily`

**Table:** `prices_daily`

- `instrument_id` (text, FK → runtime_db.instruments.instrument_id)
- `date` (date)
- `open` (numeric)
- `high` (numeric)
- `low` (numeric)
- `close` (numeric)
- `adjusted_close` (numeric)
- `volume` (numeric)
- `currency` (text)
- `metadata` (jsonb)

PK: (`instrument_id`, `date`).

### 4.2 `returns_daily`

Precomputed returns to speed up features.

**Table:** `returns_daily`

- `instrument_id` (text)
- `date` (date)
- `ret_1d` (numeric)
- `ret_5d` (numeric, nullable)
- `ret_21d` (numeric, nullable)
- `metadata` (jsonb)

PK: (`instrument_id`, `date`).

### 4.3 `factors_daily`

**Table:** `factors_daily`

- `factor_id` (text) – e.g., `MKT`, `VAL`, `MOM`, `SIZE`, etc.
- `date` (date)
- `value` (numeric)
- `metadata` (jsonb)

PK: (`factor_id`, `date`).

### 4.4 `instrument_factors_daily`

Links instruments to factor exposures.

**Table:** `instrument_factors_daily`

- `instrument_id` (text)
- `date` (date)
- `factor_id` (text)
- `exposure` (numeric)

PK: (`instrument_id`, `date`, `factor_id`).

### 4.5 Volatility & correlation panels

We may store precomputed vol/corr, or compute on the fly. For efficiency:

**Table:** `volatility_daily`

- `instrument_id` (text)
- `date` (date)
- `vol_21d` (numeric)
- `vol_63d` (numeric)
- `metadata` (jsonb)

**Table:** `correlation_panels`

- `panel_id` (PK, text) – identifies the universe/timeframe used.
- `start_date` (date)
- `end_date` (date)
- `universe_spec` (jsonb)
- `matrix_ref` (text) – reference to stored correlation matrix (e.g. file URI).
- `created_at` (timestamptz)

---

## 5. Text & Event Data (historical_db)

### 5.1 `news_articles`

**Table:** `news_articles`

- `article_id` (PK, bigserial)
- `timestamp` (timestamptz, UTC)
- `source` (text)
- `language` (text)
- `headline` (text)
- `body` (text or text_ref if stored externally)
- `metadata` (jsonb)

### 5.2 `news_links`

Many-to-many links between news and entities/instruments.

**Table:** `news_links`

- `article_id` (bigint, FK → news_articles.article_id)
- `issuer_id` (text, nullable)
- `instrument_id` (text, nullable)

PK: (`article_id`, `issuer_id`, `instrument_id`).

### 5.3 `filings`

**Table:** `filings`

- `filing_id` (PK, bigserial)
- `issuer_id` (text)
- `filing_type` (text) – e.g., `10-K`, `10-Q`, local equivalents
- `date` (date)
- `text_ref` (text) – URI to full text
- `metadata` (jsonb)

### 5.4 `earnings_calls`

**Table:** `earnings_calls`

- `call_id` (PK, bigserial)
- `issuer_id` (text)
- `date` (date)
- `transcript_ref` (text)
- `metadata` (jsonb)

### 5.5 `macro_events`

**Table:** `macro_events`

- `event_id` (PK, bigserial)
- `event_type` (text) – e.g., `FOMC`, `ECB_MEETING`, `PAYROLLS`, etc.
- `timestamp` (timestamptz)
- `country` (text, nullable)
- `description` (text)
- `text_ref` (text, nullable)
- `metadata` (jsonb)

---

## 6. Embeddings & Feature Stores

Embeddings can be stored in DB (as vectors or bytea) or in external stores with refs. We define DB schemas that at minimum track references.

### 6.1 `text_embeddings`

**Table:** `text_embeddings`

- `embedding_id` (PK, bigserial)
- `source_type` (text: `NEWS`, `FILING`, `CALL`, `MACRO_EVENT`, `PROFILE_TEXT`, etc.)
- `source_id` (bigint/text) – foreign key into corresponding table
- `model_id` (text)
- `vector` (bytea or vector type, nullable if external)
- `vector_ref` (text, nullable) – URI if stored externally
- `created_at` (timestamptz)

Indexes:
- `source_type, source_id, model_id` unique.

### 6.2 `numeric_window_embeddings`

**Table:** `numeric_window_embeddings`

- `embedding_id` (PK, bigserial)
- `entity_type` (text: `INSTRUMENT`, `ISSUER`, `SECTOR`, `MARKET`)
- `entity_id` (text)
- `window_spec` (jsonb) – describes lookback window, features used
- `as_of_date` (date)
- `model_id` (text)
- `vector` (bytea or vector type, nullable)
- `vector_ref` (text, nullable)
- `created_at` (timestamptz)

Unique index: (`entity_type`, `entity_id`, `as_of_date`, `model_id`, `window_spec`).

### 6.3 `joint_embeddings`

**Table:** `joint_embeddings`

- `joint_id` (PK, bigserial)
- `joint_type` (text: `REGIME_WINDOW`, `EPISODE`, `MACRO_STATE`, etc.)
- `as_of_date` (date)
- `entity_scope` (jsonb) – describes what this embedding covers
- `model_id` (text)
- `vector` (bytea or vector type, nullable)
- `vector_ref` (text, nullable)
- `created_at` (timestamptz)

---

## 7. Decision & Outcome Logging (runtime_db)

These tables support the Meta-Orchestrator and ensure replayability.

### 7.1 `engine_decisions`

**Table:** `engine_decisions`

- `decision_id` (PK, uuid)
- `timestamp` (timestamptz, UTC)
- `engine_name` (text) – e.g., `REGIME`, `STABILITY`, `FRAGILITY_ALPHA`, `ASSESSMENT`, `UNIVERSE`, `PORTFOLIO`
- `config_id` (text)
- `context_id` (text) – e.g., `{date}_{portfolio_id}_{strategy_id}`
- `as_of_date` (date)
- `input_refs` (jsonb) – references to data/embeddings used (e.g., entity_ids, window specs)
- `raw_input_summary` (jsonb) – optional summarized features used
- `proposed_action` (jsonb) – engine-specific output:
  - regime label, stability vector, scores, proposed positions, etc.

Indexes:
- by `engine_name`, `context_id`, `as_of_date`.

### 7.2 `executed_actions`

Maps engine decisions to actual trades/positions.

**Table:** `executed_actions`

- `action_id` (PK, uuid)
- `decision_id` (uuid, FK → engine_decisions.decision_id)
- `timestamp` (timestamptz)
- `portfolio_id` (text)
- `instrument_id` (text)
- `side` (text: `BUY`/`SELL`/`OPEN`/`CLOSE` etc.)
- `quantity` (numeric)
- `price` (numeric)
- `metadata` (jsonb)

### 7.3 `decision_outcomes`

Stores realized results of decisions after a chosen horizon.

**Table:** `decision_outcomes`

- `decision_id` (uuid, FK → engine_decisions.decision_id)
- `horizon_days` (int)
- `eval_date` (date)
- `pnl` (numeric) – realized P&L attributable to this decision over horizon
- `return` (numeric)
- `drawdown` (numeric)
- `risk_metrics` (jsonb) – e.g., realized vol, max DD, factor exposures
- `label` (text, nullable) – e.g., `GOOD`, `BAD`, `NEUTRAL`, for meta-learning

PK: (`decision_id`, `horizon_days`).

---

## 8. Configs & Model Registry (runtime_db)

### 8.1 `engine_configs`

**Table:** `engine_configs`

- `config_id` (PK, text)
- `engine_name` (text)
- `version` (text)
- `config_body` (jsonb) – full config as parsed YAML
- `created_at` (timestamptz)
- `created_by` (text)

### 8.2 `models`

**Table:** `models`

- `model_id` (PK, text)
- `engine_name` (text)
- `type` (text: `TEXT_ENCODER`, `NUMERIC_ENCODER`, `JOINT_ENCODER`, `ALPHA_MODEL`, etc.)
- `artifact_ref` (text) – path/URI to model weights
- `training_data_spec` (jsonb)
- `metrics` (jsonb)
- `created_at` (timestamptz)
- `created_by` (text)

---

## 9. Notes & Open Points

- Vector storage: we may use Postgres `vector` type or store binary blobs/URIs; this spec is abstract, implementation can choose.
- For extremely large text bodies, we may store only refs in DB; ingestion code must enforce consistency.
- Backtest snapshots: for strict historical replay, we might maintain **as-of snapshots** for certain tables (e.g., profiles); this doc assumes profiles are already time-stamped and immutable once written.

This data model is the baseline; individual engine specs (100–170) can reference these tables and, if needed, propose small extensions, but must not introduce ad-hoc parallel schemas.