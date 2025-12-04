# Universe Selection Service – Detailed Plan

## 1. Purpose & Scope

Given a regime, date, and strategy configuration, produce a **candidate universe** of securities tailored to that environment and strategy. Uses historical performance, fundamentals, profiles, and constraints.


## 2. High-Level Architecture

Modules under `universe/`:

- `analyzer/` – computes performance metrics and factor stats across regimes.
- `builder/` – constructs universes with constraints.
- `storage/` – manages `universe_snapshots` and `universe_members` tables.
- `api/` – `build_universe(...)`, `get_universe(universe_id)`.


## 3. Data Contracts

### 3.1 Inputs

- Historical DB:
  - `equity_prices_daily`
  - `sp500_constituents` (later, other indices)
  - `fundamental_ratios`
  - `regime_history`
- Profiles:
  - Company and sector profiles (structured attributes) via Profile Service.
- Config:
  - Strategy-specific filters and ranking criteria.
  - Regime-specific overrides (e.g. prefer quality in late cycle).

### 3.2 Outputs – Tables

- `universe_snapshots`
  - `universe_id` (PK)
  - `as_of_date`
  - `regime_id`
  - `strategy_id`
  - `metadata_json` (e.g. selection rules summary)

- `universe_members`
  - `universe_id`
  - `company_id`
  - `weight_hint` (not final weight; just an initial suggestion)
  - `selection_scores_json` (metrics used to rank/select)


## 4. Universe Construction Flow

### 4.1 Precomputation / Analysis

Periodic jobs (e.g. overnight) compute and refresh:

- `cycle_performance` stats:
  - For each company/sector/regime: average returns, drawdowns, risk-adjusted metrics.
- Factor metrics:
  - Quality, value, growth, momentum, volatility factors.

These can be stored in helper tables for fast lookup.

### 4.2 Per-Run Universe Build

For input `(as_of_date, regime, strategy_id)`:

1. Determine base pool:
   - Start from `sp500_constituents` (or configured index) as of `as_of_date`.
   - Filter out delisted, too illiquid, restricted names.
2. Load relevant data for each candidate:
   - Price history and factor metrics.
   - Fundamental ratios.
   - Profile attributes (quality_score, style_tags, risk_flags, cycle_behavior summary).
3. Apply strategy filters:
   - Example: keep only QUALITY and GROWTH style tags, exclude GOV_RISK flags.
4. Rank candidates according to strategy-specific scoring:
   - Composite of historical cycle performance, factor scores, and profile attributes.
5. Apply constraints:
   - Max names.
   - Sector/industry caps.
   - Style/factor exposure targets.
6. Produce `universe_members` list:
   - With `selection_scores_json` capturing why each name is included.
7. Insert `universe_snapshots` + `universe_members` rows and return `universe_id`.


## 5. Interactions with Other Players

- **Backtesting Engine**:
  - Uses `universe_snapshots` as the starting candidate sets for historical simulations.
- **Assessment Engine v2**:
  - Iterates over `universe_members` to make trade decisions.
- **Profile Service**:
  - Provides company/sector attributes during ranking.
- **Meta Orchestrator**:
  - Analyzes which universe construction rules work better/worse over time.
- **Black Swan Engine**:
  - Under EMERGENCY, Universe Selection may be instructed to shrink universes or only include certain sectors.


## 6. Failure Modes & Safeguards

- If required data is missing (e.g. no recent fundamentals for many names):
  - Mark names with `data_quality` tags and either exclude or downweight.
- If no suitable candidates found after filters:
  - Universe build returns a small or empty set; this is a signal for Risk/Assessment to possibly stand aside.


## 7. TODOs for Later Enhancements

For the current implementation, the universe builder already:

- Uses S&P 500 membership as of `as_of_date` as the base pool.
- Applies a concrete liquidity filter.
- Computes factor metrics and trailing performance via the analyzer modules.
- Scores and ranks candidates with a simple composite function.
- Applies simple sector caps via `max_names_per_sector` from
  `universe_strategy_configs`.
- Reads strategy parameters from the `universe_strategy_configs` runtime table
  when present, falling back to built-in defaults.
- Writes `universe_snapshots` and `universe_members` with selection scores.
- Can persist combined performance and factor metrics into the
  `universe_company_metrics` helper table via
  `universe.api.precompute_universe_company_metrics` for faster future builds.

The following items are intentionally deferred to a later iteration (v4+) and
kept as explicit TODOs, primarily because they depend on richer factor and
profile data than is currently available:

- TODO (v4): Add more advanced factor exposure targets and portfolio-level
  exposure checks using a richer factor model.
- TODO (v4): Integrate profile-based style tags and risk flags more deeply into
  the scoring and constraint logic once profiles carry more structured fields.

## Future: Robustness-oriented universe embedding space

Universe Selection will eventually leverage a shared embedding space over
profiles and stability metrics to favor entities that live in historically
robust regions and to downweight or exclude fragile clusters, as captured in
the "Universe Selection – Robustness-Oriented Space" use case in
`docs/new_project_plan/joint_embedding_shared_spaces_plan.md`.

## v1: STAB- and regime-aware core universes

The initial v1 implementation of the core equity universe engine
(`BasicUniverseModel`) already consumes soft-target (STAB) information
in two ways:

- A *static* filter on the latest soft-target state (score and class)
  via the STAB engine, with configurable rules to exclude BREAKER
  entities and fragile entities with weak profiles.
- A *dynamic* state-change risk modifier based on a
  `StabilityStateChangeForecaster`, which provides per-instrument
  soft-target state-change risk scores. These scores are combined into a
  scalar `stab_risk_score` in [0, 1] and used as a multiplicative
  penalty on the base universe ranking, producing more conservative
  universes when entities are likely to migrate towards TARGETABLE or
  BREAKER.

A similar hook exists for regime state-change risk so that universes can
become explicitly regime-aware without entangling the core selection
logic with any particular forecaster implementation.

## Future: Mathematical extensions for universe construction

To avoid hard-wiring fragile heuristics, the universe service will
incrementally adopt math tools that can be shared with other engines.

- **v3 – Lambda and opportunity-density integration**
  - Consume cluster-level lambda/opportunity-density scores (and their
    forecasts) as additional inputs when ranking and tiering candidates
    inside universes.
  - Expose lambda-based diagnostics (e.g. average lambda per sector,
    share of universe coming from high-lambda clusters) as part of
    `selection_scores_json` for Meta and Risk analysis.
- **v3/v4 – Information-theoretic and tail-aware selection**
  - Use entropy and tail-index style metrics (from the lambda/regime and
    scenario toolkits) as features for favouring securities that behave
    robustly across regimes rather than purely on point estimates of
    return.
  - Optionally incorporate simple tail-dependence/co-movement summaries
    (e.g. copula-based or stress-scenario co-moves) into sector/cluster
    caps so universes do not over-concentrate in names that tend to
    crash together.
- **v4+ – Scenario-informed universes**
  - Read scenario-engine outputs (170) to construct "robustness-tested"
    universes that explicitly pass basic scenario filters (e.g. no
    single name or sector responsible for outsized drawdowns across a
    core set of stress paths).

Universe Selection will eventually leverage a shared embedding space over
profiles and stability metrics to favor entities that live in historically
robust regions and to downweight or exclude fragile clusters, as captured in
the "Universe Selection – Robustness-Oriented Space" use case in
`docs/new_project_plan/joint_embedding_shared_spaces_plan.md`.
