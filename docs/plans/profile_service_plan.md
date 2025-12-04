# Profile Service – Company & Sector Profiles – Detailed Plan

## 1. Purpose & Scope

Maintain **living, versioned profiles** for companies and sectors. Profiles combine structured metrics, narrative descriptions, strengths/weaknesses, risk flags, and cycle behavior. They are the canonical high-level context for all strategy decisions.


## 2. High-Level Architecture

Modules under `profiles/`:

- `models/`
  - Data models for profile versions and audit records (no ORM choice decided here, but conceptually aligned with DB schema).
- `builders/`
  - `company_profile_builder`
  - `sector_profile_builder`
- `updaters/`
  - Logic to detect when a profile needs updating (new filings, earnings, news, big macro shifts).
- `storage/`
  - DB read/write helpers for profile tables.
- `api/`
  - Interfaces for other subsystems (e.g. `get_company_profile`, `get_sector_profile`).


## 3. Company Profiles – Data Flow

### 3.1 Inputs

- From Historical DB:
  - `companies`
  - `financial_statements`
  - `fundamental_ratios`
  - `macro_time_series` (for cycle sensitivity if needed)
  - `news_events`
  - `filings`
  - `earnings_calls`
- From Universe/Backtesting (optional, for cycle behavior):
  - Cycle performance tables (e.g. `cycle_performance_by_regime`).
- Config:
  - Definition of profile fields and scoring logic.
  - LLM model + prompt templates for narrative and strengths/weaknesses.

### 3.2 Outputs – Tables

- `company_profile_versions`
- `company_profile_audit`
- `company_current_profile`

These tables are defined in the macro plan; here we define the builder’s behavior.


## 4. Company Profile Builder Logic

### 4.1 Initial Profile Construction

For each `company_id` in `companies`:

1. Extract base data:
   - Identity, sector/industry, listing info.
2. Aggregate fundamentals:
   - Last N years and quarters from `financial_statements` and `fundamental_ratios`.
   - Compute or read quality, value, growth and profitability metrics.
3. Build cycle behavior summary:
   - Use historical `regime_history` + price series (from Universe/Backtesting results where available) to compute how the stock behaves in different regimes.
4. Build structural attributes:
   - Liquidity, market cap, style tags, structural flags (too_big_to_fail, etc.).
5. Compose `structured_json`:
   - As per macro plan fields.
6. Generate narrative:
   - LLM prompt using structured fields and key financial/time-series summaries.
   - Output `narrative_text` and candidate lists of strengths/weaknesses/risk flags.
7. Save as new `company_profile_versions` row, create `company_profile_audit` entry, and set `company_current_profile` pointer.

### 4.2 Update Triggers

The updater monitors:

- New filings for a company (`filings`).
- New earnings calls (`earnings_calls`).
- Significant news events (`news_events`) tagged as MAJOR, GUIDANCE_CHANGE, MANAGEMENT_CHANGE, etc.
- Significant changes in `fundamental_ratios` or cycle behavior.

On trigger:

1. Load last profile version for `company_id`.
2. Recompute or update derived metrics and structured fields.
3. Re-run narrative generator focusing on **what changed**.
4. Create new `company_profile_versions` row with updated `as_of_date` and `valid_from`.
5. Close previous version’s `valid_to`.
6. Write `company_profile_audit` describing changes and linking to raw sources.
7. Update `company_current_profile` pointer.

### 4.3 Access API

- `get_company_profile(ticker, as_of_date=None)`:
  - Resolve `company_id` by ticker.
  - If `as_of_date` is None: return `company_current_profile`.
  - Else: find profile version with `valid_from <= as_of_date < valid_to`.
  - Return object:
    - `company_id`, `profile_version_id`, `as_of_date`,
    - `structured_profile`, `narrative_text`, `strengths`, `weaknesses`, `risk_flags`.


## 5. Sector Profiles – Data Flow & Logic

### 5.1 Inputs

- From Historical DB:
  - `companies`
  - `equity_prices_daily`
  - `fundamental_ratios`
  - `regime_history`
- From Company Profiles:
  - Aggregated quality/value/growth scores per sector.
- Config:
  - Sector taxonomy (what constitutes a sector for our purposes).

### 5.2 Outputs – Tables

- `sector_profile_versions`
  - Similar structure to company profiles, but with aggregates.
- `sector_current_profile`

### 5.3 Sector Profile Builder Logic

1. For each sector:
   - Compute aggregate fundamentals (average growth, margins, leverage, etc.).
   - Compute performance across regimes (sector-level cycle behavior).
   - Aggregate company-level style tags and risk flags.
2. Build `structured_json`:
   - Sector ID/name, aggregates, macro sensitivity, strategy fit.
3. Generate narrative via LLM:
   - Summary of sector structure, macro drivers, key risks, typical cycle behavior.
4. Save version and update current pointer; write audit entry.

### 5.4 Access API

- `get_sector_profile(sector_id, as_of_date=None)`:
  - Same pattern as company profiles.


## 6. Interactions with Other Players

- **Universe Selection**:
  - Uses profile attributes (quality, growth, cycle sensitivity, risk flags) when building universes.
- **Assessment Engine v2**:
  - Consumes company profiles and sector profiles per ticker for decision-making.
- **Meta Orchestrator**:
  - Reads profile versions to analyze which attributes correlate with good/bad outcomes.
- **Black Swan Engine**:
  - May tag profiles with crisis-related flags when certain events occur (e.g. war-exposed sectors, sanctions risk).


## 7. Failure Modes & Safeguards

- If profile builder cannot create/update a profile due to missing critical data:
  - Mark profile as `incomplete` in `structured_json` with an explicit flag.
  - Avoid emitting half-baked narratives; Assessment Engine v2 must see `data_quality_flag` in the profile and can downweight or skip the name.
- Ensure LLM calls are deterministic enough for reproducibility by storing `generator_version` and prompt templates.


## 8. LLM Agents & TODOs for Later Enhancements

For the current implementation, LLM-based narrative generation is wired through
shared `llm_core` infrastructure with a **stubbed client**. Profiles carry
minimal but real narrative text and placeholders for strengths/weaknesses/risk
flags. Full provider integration and rich prompts are deliberately deferred to a
later iteration.

- TODO (v4): Replace the stub LLM client with real provider integration and
  prompt templates backed by the `prompt_templates` and `llm_config` tables.
- TODO (v4): Introduce richer company/sector context objects for LLM agents,
  including fundamentals summaries, event digests, and macro sensitivity.
- TODO (v4): Add profile audit entries explicitly referencing which LLM model
  and prompt template were used for each version.

## Future: Cross-modal profile embedding space

In a later phase, the Profile Service will expose dense embeddings that
combine fundamentals, price/behavior windows, and curated text into a shared
space, as described in
`docs/new_project_plan/joint_embedding_shared_spaces_plan.md`. Universe,
Assessment, and Meta will consume these embeddings for neighbor searches and
robustness analysis.
