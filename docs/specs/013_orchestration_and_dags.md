# 013 – Orchestration, States, and DAGs

## 1. Purpose

Define how Prometheus v2 is orchestrated across markets and time:
- Explicit **market state machines** (`PRE_OPEN`, `SESSION`, `POST_CLOSE`, `OVERNIGHT`, `HOLIDAY`).
- DAGs (directed acyclic graphs) of jobs per market and per phase.
- How jobs declare dependencies and resource requirements.
- How the orchestrator drives the system “like Swiss clockwork” using calendars.

This builds on 010 (Foundations) and 012 (Calendars & Scheduling).

---

## 2. Orchestration Model

### 2.1 Orchestrator abstraction

We assume a DAG-based orchestrator (Airflow/Prefect/Dagster/custom) with the following capabilities:
- DAG definitions with tasks and dependencies.
- Time-based and event-based triggers.
- Retry policies and failure handling.
- Task metadata (start/end time, status, logs).

We define **logical DAGs and tasks**; actual implementation in a specific tool will mirror these.

### 2.2 Market-aware orchestration

The orchestrator does not rely on hard-coded UTC times alone; instead, for each `market_id` it queries `TradingCalendar(market_id)` to determine:

- Whether a given date is a trading day.
- Exact `session_open` / `session_close` times in UTC.
- HOLIDAY / early close adjustments.

All DAG schedules are expressed as:

> “Run X **when** market M enters state S for date D”

not as “run X at 21:30 UTC on weekdays”.

---

## 3. Market State Machines

For each `market_id` (e.g., `US_EQ`, `EU_EQ`, `JP_EQ`, `FX_GLOB`) we define a daily state machine:

States:
- `HOLIDAY`
- `PRE_OPEN`
- `SESSION`
- `POST_CLOSE`
- `OVERNIGHT`

Transitions per date `D`:
- If `!is_trading_day(D)`: `HOLIDAY` (all day).
- Else:
  - `OVERNIGHT` → `PRE_OPEN` at `session_open(D) - Δ_preopen`.
  - `PRE_OPEN` → `SESSION` at `session_open(D)`.
  - `SESSION` → `POST_CLOSE` at `session_close(D)`.
  - `POST_CLOSE` → `OVERNIGHT` at `session_close(D) + Δ_postclose`.

`Δ_preopen` and `Δ_postclose` are configurable buffers (e.g., 60–120 minutes).

A helper function in `core/time.py`:

```python
from enum import Enum
from datetime import datetime

class MarketState(str, Enum):
    HOLIDAY = "HOLIDAY"
    PRE_OPEN = "PRE_OPEN"
    SESSION = "SESSION"
    POST_CLOSE = "POST_CLOSE"
    OVERNIGHT = "OVERNIGHT"


def get_market_state(market_id: str, now_utc: datetime) -> MarketState:
    """Return the current state of a market based on TradingCalendar."""
```

This state is used by the orchestrator to decide which DAGs can/should run.

---

## 4. DAG Definitions per Market

For each `market_id` we define a family of DAGs:

- `M_ingest_D` – daily ingestion.
- `M_features_D` – feature/embedding construction.
- `M_profiles_D` – profile updates.
- `M_engines_D` – regime, stability & soft-target, assessment, universe, portfolio.
- `M_intraday_monitors` – optional intraday monitors.
- `M_qc_preopen_Dplus1` – pre-open quality checks.

Where `M` is a market id (e.g. `us_eq`, `eu_eq`).

### 4.1 Example: US_EQ DAGs for a trading day T

**DAG: `us_eq_ingest_T`**
- **Trigger:** state=`POST_CLOSE`, `market_id=US_EQ`, date=T.
- **Tasks:**
  - `ingest_prices`
  - `ingest_factors`
  - `ingest_corporate_actions`
  - `ingest_text_events` (if batch mode)

**DAG: `us_eq_features_T`**
- **Trigger:** on success of `us_eq_ingest_T`.
- **Tasks:**
  - `compute_returns`
  - `compute_volatility`
  - `update_factor_exposures`
  - `build_numeric_windows`

**DAG: `us_eq_profiles_T`**
- **Trigger:** in `POST_CLOSE` window, after new fundamentals/filings/earnings.
- **Tasks:**
  - `update_structured_profiles`
  - `embed_profile_texts`
  - `compute_profile_embeddings`
  - `update_risk_flags`

**DAG: `us_eq_engines_T`**
- **Trigger:** on success of `us_eq_features_T` and `us_eq_profiles_T`.
- **Tasks (can be parallelized internally):**
  - `run_regime_engine`
  - `run_stability_softtarget_engine`
  - `run_assessment_engine` (incl. Fragility Alpha)
  - `run_universe_engine`
  - `run_portfolio_risk_engine`
  - `log_engine_decisions` (writes into `engine_decisions`)

**DAG: `us_eq_qc_preopen_Tplus1`**
- **Trigger:** state=`PRE_OPEN` for T+1.
- **Tasks:**
  - `check_previous_day_decisions_logged`
  - `check_data_quality_flags`
  - `check_portfolio_exposures_within_limits`

### 4.2 Other markets

Markets like `EU_EQ`, `JP_EQ`, etc. follow the same pattern with their own DAGs and triggers keyed to their session times.

Some engines (Regime, Stability & Soft-Target) might have **global variants**:
- `global_regime_T` DAG that depends on `{us_eq_features_T, eu_eq_features_T, jp_eq_features_T}` all completing.

---

## 5. Job Metadata and Dependencies

### 5.1 Job declaration

Each job/task is defined with metadata:

- `job_id`: unique string (e.g., `us_eq_ingest_T.ingest_prices`).
- `market_id`: or `GLOBAL`.
- `required_state`: one of `MarketState` or `None` for state-agnostic jobs.
- `dependencies`: list of other tasks/DAGs.
- `resource_profile`: {CPU, RAM, GPU?}.
- `priority_tier`: {1, 2, 3} as per 012 (Tier 1 must-run, etc.).

The orchestrator interprets this metadata to:
- Decide when a job is **eligible** to run (state + dependencies satisfied).
- Route it to appropriate resource pools.

### 5.2 Failure handling

Per job, define:
- `max_retries`: e.g., 3.
- `retry_delay`: e.g., 5–15 minutes.
- `on_failure`: 
  - `ALERT_AND_STOP_DOWNSTREAM` for Tier 1 jobs.
  - `ALERT_AND_SKIP` for some Tier 2/3 jobs.

Example:
- If `us_eq_ingest_T.ingest_prices` fails after all retries:
  - Raise high-severity alert.
  - Block `us_eq_engines_T` or run them in a marked **degraded mode** if explicitly supported.

---

## 6. Integrating Continuous Event-Driven Data

### 6.1 Streaming/periodic ingest

Some inputs (news, filings, macro headlines) arrive continuously. For these:

- Run **continuous jobs**, e.g.:
  - `news_ingest_stream` (every minute or via streaming client).
  - `filings_ingest_watch` (monitors vendors for new filings).

These jobs write directly into `historical_db` tables (e.g., `news_articles`, `filings`).

### 6.2 Scheduled cuts for engines

Engines do not react to every single event in real time (at least in early phases). Instead:

- They consume **snapshots** at defined cut times:
  - nightly POST_CLOSE per market,
  - and around scheduled high-impact events (e.g., FOMC, macro releases, big earnings days).

For scheduled events:

- Use `macro_events` / corporate calendars to:
  - define event-specific DAGs, e.g. `us_macro_fomc_T`.
  - trigger targeted jobs:
    - profile updates for affected issuers,
    - partial Stability & Soft-Target reevaluation,
    - risk checks.

This keeps the system timely but controlled.

---

## 7. Multi-Market, Follow-the-Sun Operation

### 7.1 Daily cycle across regions

On a typical 24h cycle (UTC):

- Asia (
`JP_EQ`, `ASIA_EQ`) closes first → run their ingestion/features/engines.
- Europe (`EU_EQ`) closes next → run EU jobs.
- US (`US_EQ`, `US_FUT`) closes last → run US jobs.

For each region, the corresponding DAGs are triggered by their local `POST_CLOSE` state.

A **global view DAG** (`global_regime_T`, `global_meta_T`) can:
- run after all key regional feature/engine DAGs complete.
- compute global regime, stability, and meta-analytics.

### 7.2 Orchestrator-level clustering

Initially, all DAGs run on your Threadripper+V100 box.
Later, you can:
- tag tasks by region and resource (e.g., heavy GPU jobs vs CPU-only),
- scale out to multiple workers/nodes while keeping the same logical DAG structure.

---

## 8. Monitoring Integration

The orchestrator must expose job/DAG state so that `prometheus/monitoring` can:

- Build `/api/status/pipeline?market_id=...` responses (see 200 spec):
  - current market state,
  - job statuses, latencies, next runs.

UI should display:
- A **per-market timeline** showing state transitions and DAG statuses.
- SLO status for core DAGs (e.g., ingestion and engines per market).

This allows you to visually confirm that all regional pipelines are running on schedule and see where any delays or failures occur.

---

## 9. Summary

- Markets are modeled as state machines determined by trading calendars.
- DAGs per market/phase express all ingestion, feature, and engine jobs.
- Jobs declare required states, dependencies, and resources.
- Continuous event ingestion feeds into scheduled engine cuts.
- A follow-the-sun pattern orchestrates Asia → Europe → US cycles.
- Monitoring consumes orchestrator metadata to show both **market state** and **system state** in the UI.

This orchestration plan, combined with 012 (Calendars & Scheduling) and 200 (Monitoring & UI), is the blueprint for running Prometheus v2 with mechanical reliability across all regions.