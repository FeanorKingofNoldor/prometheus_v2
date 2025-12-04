# Macro Plan – New Trading System Architecture

This document defines the **full target architecture** for the new trading system, starting from a clean project. It identifies all major subsystems ("players"), their responsibilities, inputs/outputs, and data contracts. We will implement the new system strictly according to this plan.

---

## 0. Global Principles & Modes

### 0.1 Modes

The system operates in two conceptual modes, sharing code but **never sharing databases**:

1. **TRAINING / RESEARCH MODE**
   - Uses: synthetic historical DBs and real historical research DBs.
   - Purpose: backtesting, synthetic scenario training, strategy research, profile generation experiments.
   - Data sources: synthetic generators + offline pulls of real history.

2. **PRODUCTION MODE**
   - Uses: production historical DB and production runtime DB.
   - Purpose: nightly preparation and real / paper trading.
   - Data sources: real market/fundamental/macro/news feeds via a controlled ingestion layer.

### 0.2 Global Rules

- **Single source of truth for data**: all external data enters through the **Data Ingestion & Normalization Service**, then into DBs. No other subsystem talks directly to external APIs.
- **Profiles, not raw documents, in live decisions**: live decision-making uses **company/sector profiles** and numeric data, not raw filings/transcripts/news.
- **Versioned, auditable reasoning context**: every trade and major decision is tied to a specific profile version, regime, universe snapshot, prompt template, and agent graph version.
- **Clear contracts**: every subsystem exposes a small, explicit API with well-defined input/output formats.

---

## 1. Data Ingestion & Normalization Service

### 1.1 Role

Single subsystem responsible for fetching, cleaning, validating and loading **all external data** into the system's databases. All other components read data from DB only.

### 1.2 Responsibilities

- Fetch external data:
  - Equity market data (EOD prices, volume, corporate actions, optionally intraday aggregates).
  - Index constituents (S&P 500 initially, later others).
  - Fundamentals (financial statements, derived ratios from providers or our own parsing).
  - Macro & credit time series.
  - Company metadata (sector, industry, country, identifiers).
  - News & events (earnings, AGMs, major corporate actions, investigations, etc.).
  - Filings & transcripts (10-K/10-Q, earnings call transcripts, shareholder meeting docs).
- Normalize data:
  - Enforce schema (types, units, keys), handle missing/erroneous values.
  - Map provider IDs to internal identifiers (ticker, ISIN, internal company_id).
- Validate:
  - Run data quality checks (null checks, range checks, consistency checks, cross-field invariants).
  - Write errors to a data-quality log for inspection.
- Load:
  - Insert/update data in **historical DBs** (training and production) only.

### 1.3 Inputs

- Configuration:
  - Provider credentials and endpoints (API keys, URLs).
  - Mapping specs: provider symbol → internal identifiers.
  - Schedules: daily, weekly, event-driven jobs.
- Triggering:
  - Nightly scheduler for daily data.
  - Event triggers (new filing detected, new earnings call, etc.).

### 1.4 Outputs

- DB tables in historical DBs (examples, exact schema defined in migrations):
  - `companies`
    - Fields: `company_id`, `ticker`, `isin`, `name`, `sector`, `industry`, `country`, `listing_date`, `delisting_date`.
  - `equity_prices_daily`
    - Fields: `ticker`, `date`, `open`, `high`, `low`, `close`, `adj_close`, `volume`, `currency`.
  - `corporate_actions`
    - Fields: `ticker`, `action_date`, `action_type` (SPLIT, DIVIDEND, TICKER_CHANGE,...), `details_json`.
  - `sp500_constituents`
    - Fields: `ticker`, `effective_date`, `end_date`, `index_name`.
  - `financial_statements`
    - Fields: `company_id`, `fiscal_period`, `fiscal_year`, `statement_type` (IS/BS/CF), `report_date`, `values_json`.
  - `fundamental_ratios`
    - Fields: `company_id`, `period_start`, `period_end`, `roe`, `roic`, `gross_margin`, `op_margin`, `leverage`, `revenue_growth`, etc.
  - `macro_time_series`
    - Fields: `series_id`, `date`, `value`, `frequency`, `metadata_json`.
  - `news_events`
    - Fields: `event_id`, `company_id` (nullable), `sector`, `event_date`, `event_type`, `source`, `headline`, `body_text` or `body_ref`, `raw_metadata`.
  - `filings`
    - Fields: `filing_id`, `company_id`, `filing_type` (10-K, 10-Q, AGM_DOC,...), `filing_date`, `period_end`, `text_blob` or `text_ref`, `raw_metadata_json`.
  - `earnings_calls`
    - Fields: `call_id`, `company_id`, `call_date`, `transcript_text` or ref, `raw_metadata_json`.

### 1.5 Output Format & Access

- Data is stored in relational tables (PostgreSQL), with JSONB for complex fields where needed.
- Access is read-only for all downstream services; only the ingestion layer writes to these tables.

---

## 2. Profile Service – Company & Sector Profiles

### 2.1 Role

Create and maintain **living, versioned profiles** for companies and sectors. Profiles combine structured numerical attributes, textual narrative, strengths/weaknesses, risk tags, and event summaries. They are the primary high-level context for decisions.

### 2.2 Responsibilities

- Generate initial profiles for all companies in the universe (e.g. S&P 500).
- Update profiles when new information arrives (filings, events, macro shifts).
- Maintain version history with audit trail.
- Expose read APIs for other services:
  - `get_company_profile(ticker, as_of_date)`.
  - `get_sector_profile(sector_id, as_of_date)`.

### 2.3 Data Model – Company Profiles

Core tables (abstract definition):

- `company_profile_versions`
  - `profile_version_id` (PK)
  - `company_id` (FK → companies)
  - `as_of_date` (date the profile is valid for, based on data up to this point)
  - `valid_from`, `valid_to` (temporal validity window)
  - `source_type` (AUTO_INGEST, LLM_REVIEW, HUMAN_ANALYST)
  - `generator_version` (version of profile-building pipeline)
  - `structured_json` (key fields below)
  - `narrative_text` (concise, human-readable profile)
  - `strengths_json` (list of strength objects)
  - `weaknesses_json` (list of weakness objects)
  - `risk_flags_json` (list of flags like HIGH_LEVERAGE, GOVERNANCE_RISK, REGULATORY_RISK)

- `company_profile_audit`
  - `audit_id` (PK)
  - `profile_version_id` (FK)
  - `event_timestamp`
  - `trigger_type` (NEW_10Q, AGM, NEWS_SPIKE, MACRO_SHIFT,...)
  - `raw_sources_json` (filing_ids, news_event_ids, macro series snapshots, etc.)
  - `change_summary_text` (what changed vs previous profile)
  - `change_diff_json` (machine-friendly diff of key fields)

- `company_current_profile`
  - `company_id` (PK)
  - `current_profile_version_id` (FK → company_profile_versions)
  - `last_updated`

### 2.4 Structured JSON for Company Profiles (conceptual fields)

`structured_json` contains at least:

- Identity & classification:
  - `ticker`, `isin`, `name`, `sector`, `industry`, `country`.
- Business model & segments:
  - `business_model_summary` (short text)
  - `segments` (list of {segment_name, revenue_share, ebit_share})
- Financial quality & growth:
  - `financials`: time-series summary for last N years/quarters (aggregated)
  - `quality_score`, `value_score`, `growth_score`, `profitability_score`.
  - `margin_profile`: {gross, operating, net} with trends.
  - `growth_profile`: revenue/EPS growth rates with volatility.
- Capital structure & allocation:
  - `leverage_metrics`: (debt_to_equity, interest_coverage, net_debt_to_ebitda)
  - `capital_allocation_style`: description + flags (e.g. dividend_grower, buyback_heavy).
- Management & governance:
  - `ceo`: {name, tenure_years, background_summary}.
  - `key_executives`: list of {role, name, tenure, notes}.
  - `governance_score`, `governance_flags`.
- Cycle & macro sensitivity:
  - `cycle_behavior`: performance stats by regime/cycle stage.
  - `macro_exposures`: sensitivities to key macro factors if known.
- Sector & style tags:
  - `style_tags`: [QUALITY, VALUE, GROWTH, CYCLICAL, DEFENSIVE, ...].
- Liquidity & tradability:
  - `avg_daily_volume`, `market_cap`, `liquidity_score`.
- Regulatory & structural notes:
  - `structural_attributes`: e.g. {too_big_to_fail: true, systemic_criticality: HIGH}.

`strengths_json`, `weaknesses_json`, `risk_flags_json` are structured lists with fields like {aspect, description, severity, rationale}.

### 2.5 Sector Profiles

Sector profiles have a parallel structure:

- `sector_profile_versions` / `sector_current_profile` tables.
- `structured_json` includes:
  - `sector_id`, `sector_name`.
  - Fundamental aggregates (growth, margins, leverage averages).
  - Macro/cycle sensitivity.
  - Structural notes (regulation, consolidation, disruption risk).
  - Strategy fit info (which strategies work best in which regimes for this sector).

### 2.6 Inputs

The Profile Service reads data exclusively from:

- Historical DB:
  - `companies`, `financial_statements`, `fundamental_ratios`.
  - `macro_time_series`, `news_events`, `filings`, `earnings_calls`, `sp500_constituents`.
  - Any cycle performance tables generated by UniverseSelection/Backtesting.
- Configuration:
  - Profile generation recipes (which features, horizons, thresholds).
  - LLM models & prompt templates for narrative / strengths/weaknesses.

### 2.7 Outputs & API Contracts

- `get_company_profile(ticker, as_of_date)` → returns object with:
  - `company_id`
  - `profile_version_id`
  - `as_of_date`
  - `structured_profile` (parsed from `structured_json`)
  - `narrative_text`
  - `strengths`, `weaknesses`, `risk_flags`
- `get_sector_profile(sector_id, as_of_date)` → same pattern.

These outputs are consumed by UniverseSelection, Assessment Engine v2, and Meta Orchestrator.

---

## 3. Macro Regime Service

### 3.1 Role

Determine the current **macro/credit regime** and stage of the cycle based on macro indicators and credit spreads, using an extended MacroRegimeModule.

### 3.2 Responsibilities

- Maintain historical regime series.
- Provide current and past regime classifications.
- Expose regime information to:
  - UniverseSelection
  - Assessment Engine v2
  - Backtesting
  - Meta Orchestrator

### 3.3 Inputs

- Historical DB:
  - `macro_time_series` (credit spreads, yield curve, vol indices, etc.).
- Configuration:
  - Indicator set and weights.
  - Regime definitions (e.g., credit_expansion, credit_freeze, etc.).

### 3.4 Outputs & API

- DB Tables:
  - `regime_history`:
    - `date`, `regime_id`, `regime_name`, `sub_stage`, `score_components_json`, `confidence`.
- API:
  - `get_regime(as_of_date)` → `{regime_id, regime_name, sub_stage, confidence, scores}`.

---

## 4. Universe Selection Service

### 4.1 Role

Given a regime and full historical data, construct **candidate universes** (sets of tickers) tailored to each regime/strategy, using performance in similar cycles and profile attributes.

### 4.2 Responsibilities

- Analyze historical performance by regime/cycle stage.
- Produce per-regime universe definitions and sector weights.
- Use both numeric data and selected profile attributes (e.g. quality score, cycle sensitivity).

### 4.3 Inputs

- Historical DB:
  - `equity_prices_daily`
  - `sp500_constituents`
  - `fundamental_ratios`
  - `regime_history`
- Profiles:
  - Company and sector structured attributes via Profile Service.
- Strategy configs:
  - Desired number of names, diversification constraints, factor tilts (quality/value/growth), sector caps.

### 4.4 Outputs & API

- DB Tables:
  - `universe_snapshots`:
    - `universe_id`, `as_of_date`, `regime_id`, `strategy_id`, `metadata_json`.
  - `universe_members`:
    - `universe_id`, `company_id`, `weight_hint`, `selection_scores_json`.
- API:
  - `build_universe(as_of_date, regime, strategy_id)` → returns `universe_id` and list of candidate tickers with metadata.
  - `get_universe(universe_id)`.

Universe outputs feed into Backtesting and Assessment Engine v2.

---

## 5. Backtesting Engine

### 5.1 Role

Simulate trading strategies over historical or synthetic data, using the same interfaces and profiles as in production, to evaluate performance and stress-test strategies.

### 5.2 Responsibilities

- Provide time simulation (iterate over trading days).
- Simulate market prices and fills based on historical/synthetic data.
- Track portfolio, PnL, risk metrics, trade logs.
- Integrate with:
  - Regime Service.
  - Universe Service.
  - Profile Service.
  - Assessment Engine v2 (or simplified strategy logic for tests).

### 5.3 Inputs

- Training DB (`training_historical`) or production historical DB for research.
- Universe definitions from UniverseSelection.
- Regime history from Macro Regime Service.
- Profiles from Profile Service at each simulated date.
- Strategy configurations (parameter sets for evaluation).

### 5.4 Outputs

- DB Tables in `research_results` or training DB:
  - `backtest_runs`:
    - `run_id`, `strategy_id`, `config_json`, `start_date`, `end_date`, `universe_id`, `metrics_json`.
  - `backtest_trades`:
    - `run_id`, `trade_id`, `date`, `ticker`, `direction`, `size`, `price`, `profile_version_id`, `regime_id`, `universe_id`, `decision_metadata_json`.
  - `backtest_daily_equity`.

Backtests will be used to pick strategies and parameters, and to validate profile formats.

---

## 6. Assessment Engine v2 (Live Decision Layer)

### 6.1 Role

Given profiles, regime, technicals, portfolio state, and strategy configs, decide **what to trade, when, and how big**. This replaces the old entthing logic with a clean, profile-driven decision layer.

### 6.2 Responsibilities

- For each universe snapshot and day:
  - Evaluate each candidate ticker using its profile + market context.
  - Decide: long/short/skip, conviction, suggested size and trade plan (entry/exit logic where applicable).
  - Rank candidates and apply portfolio-level constraints.
- Produce concise, auditable rationales for trades.
- Provide a uniform decision interface to Risk and Execution.

### 6.3 Inputs

For each decision cycle (e.g. daily or intraday slice):

- Company profiles:
  - `get_company_profile(ticker, as_of_date)` results (profile version, structured fields, narrative, strengths/weaknesses, risk flags).
- Sector profiles:
  - `get_sector_profile(sector_id, as_of_date)`.
- Regime & macro:
  - `{regime_id, regime_name, sub_stage, scores}` from Regime Service.
- Universe snapshot:
  - `universe_id`, list of candidate tickers and selection metadata from UniverseSelection.
- Market & technicals:
  - `stock_metrics` for each ticker and date (technical indicators, volatility, correlations, etc.).
- Portfolio state:
  - Current positions, PnL, exposures, risk usage.
- Strategy configuration:
  - Allowed instruments, target number of positions, factor tilts, risk budgets, time horizon.

### 6.4 Outputs & API

- Decision objects (per ticker):
  - `ticker`
  - `decision_type`: LONG_ENTRY, LONG_HOLD, LONG_EXIT, SHORT_ENTRY, SHORT_HOLD, SHORT_EXIT, SKIP.
  - `conviction_score` (0–1 or discrete levels).
  - `target_weight` or `notional_target`.
  - `stop_loss_hint`, `take_profit_hint` (optional, for strategies that want LLM‑suggested levels).
  - `profile_version_id`, `sector_profile_version_id`.
  - `regime_id`, `universe_id`, `strategy_id`.
  - `prompt_template_id`, `agent_graph_version`.
  - `decision_rationale_short` (short text; the full chain-of-thought stays internal).

- Aggregated plan:
  - Ranked list of decisions, plus portfolio-level summary (how capital is allocated, how risk is distributed).

These outputs feed into Risk Management and Execution.

---

## 7. Risk Management Service

### 7.1 Role

Take proposed trades from Assessment Engine v2 and enforce risk constraints, producing an executable order plan.

### 7.2 Responsibilities

- Enforce:
  - Max positions, position size limits, sector and factor concentration limits.
  - Liquidity constraints (max %ADV, min price, volatility limits).
  - Capital and leverage constraints.
- Adjust or veto trades that violate constraints.
- Compute final position targets.

### 7.3 Inputs

- Proposed decisions from Assessment Engine v2.
- Portfolio state: current positions, PnL, exposures.
- Risk configs: per-strategy risk budgets, per-name caps, sector caps, drawdown limits.
- Market liquidity metrics.

### 7.4 Outputs

- Final target positions per ticker:
  - `ticker`, `target_position`, `delta_position`, `priority`, `risk_reasoning_summary`.
- Risk events:
  - Logs when trades are vetoed or significantly reduced due to risk rules.

These outputs go to Execution and are logged for Meta Orchestrator.

---

## 8. Execution Service (Broker / Backtesting Bridge)

### 8.1 Role

Translate target positions from Risk Management into concrete orders, route them to the appropriate execution venue (broker in production, backtesting engine in training), and track fills.

### 8.2 Responsibilities

- Generate orders and order schedules from target position changes.
- Connect to IBKR or other brokers in production; to Backtesting Engine in training.
- Handle order lifecycle: submission, modification, cancellation, fill tracking.
- Write trade fills and execution logs to runtime DB.

### 8.3 Inputs

- Target positions and priorities from Risk Management.
- Broker configuration (account, host/port, order types allowed).
- Market data for slippage modeling (in training mode).

### 8.4 Outputs

- `trades` table in runtime DB:
  - `trade_id`, `timestamp`, `ticker`, `direction`, `size`, `price`, `order_id`, `strategy_id`, `profile_version_id`, `regime_id`, etc.
- Execution logs for debugging.

---

## 9. Meta Orchestrator (Kronos v2)

### 9.1 Role

Analyze the behavior and performance of the entire system over time and propose changes to configurations, thresholds, and strategy weights.

### 9.2 Responsibilities

- Ingest decision logs, trades, outcomes (PnL, risk metrics) and the associated context:
  - `profile_version_id`, `sector_profile_version_id`.
  - `regime_id`, `universe_id`, `strategy_id`.
  - `prompt_template_id`, `agent_graph_version`.
- Identify patterns of:
  - Systematic over/under‑performance by regime, sector, profile attributes.
  - Prompt/agent configurations that work or fail.
- Generate adaptation proposals:
  - Adjust strategy configs (filters, thresholds).
  - Adjust risk limits.
  - Suggest prompt or agent graph changes.

### 9.3 Inputs

- Runtime DB and research results DB:
  - `trades`, `positions`, `pipeline_decisions`, `backtest_runs`, `backtest_trades`, performance metrics.
- Profile and regime data:
  - Snapshots of `company_profile_versions`, `sector_profile_versions`, `regime_history`.

### 9.4 Outputs

- `meta_controller_config_proposals` table:
  - Proposals for specific strategies/settings with rationale.
- Optional direct updates (if auto‑apply is enabled) to configuration tables.

---

## 10. Monitoring, Logging & Observability

### 10.1 Role

Provide complete visibility into system health, data quality, and decision-making, with an audit trail that allows reconstructing any trade’s context.

### 10.2 Responsibilities

- Application logs (errors, warnings, info) per subsystem.
- Data quality dashboards (ingestion failures, missing data, validation errors).
- Decision timeline views:
  - For any date and ticker, see regime, universe membership, profile version, decisions, trades, and outcomes.

### 10.3 Inputs/Outputs

- Inputs: logs and metrics from all services.
- Outputs: dashboards, alerts, reports stored in DB and/or external monitoring tools.

---

## 11. Configuration & Strategy Definitions

### 11.1 Role

Centralize all configurable aspects of the system: strategies, risk parameters, prompt templates, agent graph definitions, etc.

### 11.2 Responsibilities

- Maintain:
  - Strategy definitions (name, style, instruments, horizon).
  - Per-regime configuration overrides.
  - Risk configs (per-strategy and global).
  - Prompt templates and LLM configs for profile builder, assessment engine, and meta orchestrator.
- Provide versioning for configs so that decisions can be tied to specific config versions.

### 11.3 Inputs/Outputs

- Inputs: manual changes, meta-orchestrator proposals.
- Outputs: configuration documents/tables used by all services, with version IDs referenced in logs.

---

## 12. Summary of Players and Their Contracts

**Players:**
- Data Ingestion & Normalization Service
- Profile Service (Company & Sector)
- Macro Regime Service
- Universe Selection Service
- Backtesting Engine
- Assessment Engine v2 (Live Decision Layer)
- Risk Management Service
- Execution Service
- Meta Orchestrator (Kronos v2)
- Black Swan Emergency Engine
- Monitoring & Observability
- Configuration & Strategy Management

For each, this plan defines:
- Responsibilities.
- Input sources (always via DBs and defined APIs, never random external calls except in Data Ingestion).
- Output tables and API contracts.

**Next step (not to be executed yet):** derive detailed subplans for each player (implementation details, internal modules, and class/function-level designs) using this macro plan as the top-level map. We will only start coding once all subplans are written and agreed upon.

---

## 13. Black Swan Emergency Engine

### 13.1 Role

Continuously monitor global news, macro signals, and selected social media sources to detect **systemic, regime-breaking events** ("black swans" and major crises). When triggered, it initiates and manages an **Emergency SOP** that can override normal strategy behavior (e.g. rapid de-risking, trading halts, special hedges).

### 13.2 Responsibilities

- Aggregate and analyze **global information streams** for extreme events:
  - Major news outlets (global and regional).
  - Financial news wires.
  - Curated social media accounts (e.g. key political, central bank, industry leaders, high-signal commentators).
- Maintain a **real-time risk state** separate from normal regimes:
  - `black_swan_state`: {NORMAL, ELEVATED_RISK, EMERGENCY}.
  - Track type of emergency (war, terror attack, pandemic, systemic financial crisis, cyberattack, etc.).
- Detect and classify candidate black swan events using high-reasoning LLM agents.
- Decide when to **escalate/de-escalate** the emergency state, with hysteresis and human-override options.
- Trigger an **Emergency SOP**:
  - Notify Risk Management, Assessment Engine, and Execution.
  - Apply pre-defined emergency rules (e.g. reduce gross exposure, tighten limits, halt certain strategies, restrict to liquid instruments, switch to hedge mode).
- Log every detection, escalation, decision, and resolution with full context for later analysis by Meta Orchestrator.

### 13.3 Inputs

- From Data Ingestion & Normalization Service:
  - `news_events` (global and company-specific), including headlines, body_text, source, and tags.
  - `macro_time_series` for fast-moving stress indicators (e.g. credit spreads, volatility indices, cross-asset dislocations).
- From Configuration & Strategy Management:
  - Whitelists/blacklists of news sources and social media accounts.
  - Definitions of emergency types and their initial SOP templates.
  - Sensitivity settings (how conservative or aggressive the engine should be).
- Optional direct streaming channels (if implemented):
  - Real-time newswire stream.
  - Real-time social media firehose for whitelisted accounts.

### 13.4 Outputs & API

- DB Tables:
  - `black_swan_events`:
    - `event_id`, `detected_at`, `event_type` (WAR, TERROR_ATTACK, PANDEMIC, FINANCIAL_CRISIS, CYBERATTACK, OTHER),
    - `confidence_score`,
    - `severity_score`,
    - `sources_json` (news_event_ids, social_media_refs, macro anomalies),
    - `llm_assessment_summary` (short narrative),
    - `emergency_state_after` (NORMAL/ELEVATED_RISK/EMERGENCY).
  - `black_swan_state_history`:
    - `timestamp`, `state`, `trigger_event_id` (nullable), `reason_text`.
  - `black_swan_sop_actions`:
    - `action_id`, `event_id`, `applied_component` (RISK, ASSESSMENT, EXECUTION, UNIVERSE, CONFIG),
    - `action_type` (e.g. REDUCE_GROSS_EXPOSURE, HALT_NEW_POSITIONS, LIQUIDATE_SPECIFIC_SECTORS, ENABLE_HEDGES),
    - `parameters_json`,
    - `status` (PENDING, APPLIED, OVERRIDDEN),
    - `applied_at`, `applied_by` (AUTO/HUMAN).

- API:
  - `get_black_swan_state()` → `{state, last_change_timestamp, current_event_id (optional)}`.
  - `get_active_black_swan_event()` → latest high-severity event if any.
  - `propose_emergency_actions()` → list of suggested SOP actions per subsystem, with rationale.

### 13.5 Interaction with Other Players

- **Risk Management Service**:
  - On state EMERGENCY or ELEVATED_RISK, apply engine-proposed overrides:
    - Lower risk limits, cap gross and net exposures.
    - Increase liquidity requirements.
    - Potentially force de-risking of illiquid or high-risk names.
- **Assessment Engine v2**:
  - Adjust decision logic and prompts based on `black_swan_state` and `event_type`:
    - Prefer capital preservation, avoid new exposures in highly uncertain areas.
    - Treat certain patterns (e.g. initial crash) differently than normal regimes.
- **Universe Selection Service**:
  - Under EMERGENCY, shrink universes to the most liquid, robust names, or disable certain strategies entirely.
- **Execution Service**:
  - May change order types and aggression (e.g. more passive, avoid crossing spreads aggressively in stressed conditions).
- **Meta Orchestrator (Kronos v2)**:
  - Analyze outcomes of emergency actions after the fact.
  - Learn which SOP variants work best for different event types and refine future emergency playbooks.

### 13.6 Human Oversight & Fail-safes

- Black Swan Emergency Engine must:
  - Support **manual overrides** (force EMERGENCY state on/off, approve or veto SOP actions).
  - Expose clear dashboards/alerts for operators.
  - Be designed with conservative defaults (favor protecting capital over chasing opportunity when in doubt).

The Black Swan Emergency Engine operates continuously in the background, informs other services through a small set of state and event APIs, and never bypasses the central Data Ingestion layer for persistence. Its purpose is to detect and structure extreme events and drive a coordinated emergency response across the entire system.
