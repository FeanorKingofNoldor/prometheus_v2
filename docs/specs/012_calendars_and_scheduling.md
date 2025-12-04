# 012 – Calendars, Scheduling, and Resource Allocation

## 1. Purpose

Prometheus v2 must run a global, multi-market pipeline on a reliable schedule with clear resource expectations.

This spec defines:
- Market/calendar abstractions per region.
- Daily/weekly job schedules for ingestion, feature building, engines, and portfolio updates.
- Resource allocation guidelines (CPU/GPU/IO), concurrency, and SLOs.

It is an extension of 010 (Foundations) and 020 (Data Model), and a prerequisite for robust monitoring and operations.

---

## 2. Market and Calendar Abstractions

### 2.1 Market identifiers

We define logical **markets** that group exchanges and instruments with similar trading hours and holiday patterns.

Examples (initial targets):
- `US_EQ` – US equities (NYSE, NASDAQ, etc.).
- `US_FUT` – US index futures (CME, etc.).
- `EU_EQ` – Major European equities (Xetra, LSE, Euronext... grouped initially).
- `JP_EQ` – Japan equities (TSE).
- `ASIA_EQ` – placeholder for other Asian markets (HK, SG, etc. – can be split later).
- `FX_GLOB` – 24h FX markets.

Each instrument in `instruments` will carry a `market_id` in `metadata` or a dedicated column, used by calendars and scheduling.

### 2.2 TradingCalendar service

Module: `prometheus/core/time.py`

Responsibilities:
- Provide unified access to trading calendars per `market_id`.
- Handle regular sessions, holidays, and early closes.

API sketch:

```python
from datetime import date, datetime
from typing import List

class TradingCalendar:
    """Trading calendar for a specific market (e.g. US_EQ, EU_EQ)."""

    def __init__(self, market_id: str):
        self.market_id = market_id

    def is_trading_day(self, d: date) -> bool:
        """Return True if d is a trading day for this market."""

    def previous_trading_day(self, d: date, n: int = 1) -> date:
        """Return the nth previous trading day before d."""

    def next_trading_day(self, d: date, n: int = 1) -> date:
        """Return the nth next trading day after d."""

    def session_open(self, d: date) -> datetime:
        """Return session open time (UTC) for d."""

    def session_close(self, d: date) -> datetime:
        """Return session close time (UTC) for d."""

    def holidays(self, year: int) -> List[date]:
        """List exchange holidays for this market and year."""
```

Implementation notes:
- Can wrap a library like `exchange_calendars` or maintain our own holiday tables.
- All times returned are in **UTC**, but calendars understand local-time patterns.

### 2.3 Multi-market coverage

From day one, calendar definitions should exist for:
- `US_EQ`, `US_FUT` (core initial markets).
- `EU_EQ`, `JP_EQ`, `ASIA_EQ` (even if we don’t trade them yet, to design schedules).
- `FX_GLOB` (24h with weekend gaps).

This ensures all scheduling logic is ready for expansion.

---

## 3. Job Classes and Pipelines

### 3.1 Job classes

We categorize jobs into:

1. **Ingestion jobs**
   - Pull raw market data, fundamentals, text, macro events into `historical_db`.

2. **Feature/embedding jobs**
   - Compute returns, vol, factors, numeric window features.
   - Compute/persist text and numeric embeddings.
   - Build/update ProfileSnapshots.

3. **Engine jobs**
   - Regime Engine runs.
   - Stability & Soft-Target Engine runs.
   - Assessment Engine (including Fragility Alpha) runs.
   - Universe Selection Engine runs.
   - Portfolio & Risk optimization.

4. **Backtesting / research jobs**
   - Offline experiments and meta-learning.

5. **Monitoring & housekeeping jobs**
   - Health checks, data quality checks.
   - Cleanup / archiving.

### 3.2 Orchestration

We assume the use of a DAG-style orchestrator (e.g., Airflow/Prefect/Dagster or custom), with:
- Explicit task dependencies.
- Retry policies.
- SLA alerts.

The exact tool is not fixed here; this spec defines the DAG structure and SLOs.

---

## 4. Daily Schedules (Initial Focus: US_EQ / S&P 500)

All times below are **UTC** for clarity.

### 4.1 US_EQ weekday schedule (simplified)

**Pre-open window (before US open)**

- **T-1 evening (after US close)**
  - `T-1 21:30–23:00 UTC` (approx):
    - US_EQ ingestion for day T-1 (prices, volumes, corporate actions).
    - Factor and volatility updates (`returns_daily`, `factors_daily`, `volatility_daily`).
    - Profile updates for issuers with new filings/calls/news.
    - Text embeddings and profile embeddings for new text.

- **T morning before open**
  - Sanity checks:
    - DB health checks (core/db_health).
    - Data quality checks on yesterday’s data (data_ingestion/validation).

**During US session**

- Optional intraday jobs (later phases):
  - Intraday regime/stability monitors based on high-frequency indicators.
  - Intraday risk monitoring and alerts.

**After US close (day T)**

- `T 21:00–23:30 UTC`:
  - Finalize US_EQ and US_FUT prices for T.
  - Update daily factors, vol, correlations.
  - Run Regime Engine for T (global + per-region regimes).
  - Run Stability & Soft-Target Engine for T (entities and portfolios).
  - Run Assessment Engine for T (+ Fragility Alpha).
  - Run Universe Selection for T.
  - Run Portfolio & Risk optimization to compute target positions for T+1.
  - Log all engine decisions into `engine_decisions`.

- `T late night`:
  - Optionally run smaller backtests/meta-analytics for rapid feedback.

### 4.2 Other regions

As we expand:

- EU_EQ jobs run after European closes; JP_EQ after Japan closes, etc.
- Some engines (Regime, Stability & Soft-Target) may be run **once globally** per day based on combined data, while others (Assessment, Universe, Portfolio) can have region-specific runs.

For planning now:
- Define per-market "closing windows" and ensure our orchestration supports separate DAGs per `market_id`.

---

## 5. Resource Allocation & Sizing Guidelines

### 5.1 Job cost classes

We classify jobs by rough resource profile:

- **IO-bound**:
  - Data ingestion, SQL-heavy feature extraction.
- **CPU-bound**:
  - Most classical ML, numeric feature computation, basic simulations.
- **GPU-bound**:
  - LLM calls (if local), heavy deep learning training, large joint encoders.

### 5.2 Initial single-node assumptions

Phase 1 (S&P 500 focus) can run on a single beefy machine:
- N CPU cores (e.g., 16–32), plenty of RAM (64–128 GB), optional 1 GPU.
- Nightly window for heavy jobs (engines, backtests): ~3–6 hours post-US close.

Guidelines:
- Ingestion and feature jobs should complete within **1–2 hours** post close.
- Engine runs (Regime, Stability & Soft-Target, Assessment, Universe, Portfolio) should target **< 1 hour** total.
- Remaining time can be used for research/backtests.

### 5.3 Scaling plan

As we move to multiple regions and more assets:

- Move to a small cluster or cloud environment where:
  - IO-heavy jobs run on dedicated data nodes.
  - ML/engine jobs run on compute nodes (CPU/GPU pools).
- Use the orchestrator to:
  - Tag tasks with resource requirements (CPU/GPU/memory).
  - Configure concurrency limits per resource pool.

### 5.4 Prioritization

Under resource pressure:
- **Tier 1** jobs (must run):
  - Ingestion, data quality checks.
  - Regime, Stability & Soft-Target, Assessment, Universe, Portfolio for live strategies.
- **Tier 2** jobs (degradable):
  - Some backfill tasks, non-critical analytics.
- **Tier 3** (best-effort):
  - Big backtests, long-running research pipelines.

The scheduler must always prioritize Tier 1, especially around market close.

---

## 6. Monitoring, SLOs, and Alerts

Each job/DAG will have SLOs:

- Example SLOs (for US_EQ):
  - All daily data ingestion jobs completed by `T+1 00:00 UTC`.
  - Regime/Stability/Assessment/Universe/Portfolio engines completed by `T+1 01:00 UTC`.
  - Decision logs present and consistent by `T+1 01:15 UTC`.

Monitoring integration:
- `prometheus/monitoring` should:
  - Expose metrics (job latency, success/failure counts, retries).
  - Trigger alerts if SLOs are violated (e.g., page or push notification).

---

## 7. Follow-the-Sun Considerations

For a future fully global setup:
- Run region-specific pipelines shortly after each region’s close.
- Maintain a **global view** that aggregates:
  - latest regimes per region,
  - stability/fragility per entity/region,
  - portfolio exposures across time zones.

The current spec enforces that all schedules and calendars are keyed by `market_id` and time in UTC, so we can gradually move from "US_EQ only" to full global coverage without redesigning the scheduling logic.

---

This calendars and scheduling spec should be used by:
- `core/time.py` implementation.
- Data ingestion/orchestration code.
- Monitoring & UI (to show which regions are open/closed and which jobs are pending/running).