# Monitoring & Observability – Detailed Plan

## 1. Purpose & Scope

Provide visibility into system health, data quality, and decision flows. Enable reconstruction of any trade’s context and fast diagnosis of issues.


## 2. High-Level Architecture

Modules under `monitoring/`:

- `metrics/` – emit metrics from all components (ingestion rates, latencies, error counts).
- `logging/` – structured logs with correlation IDs across services.
- `dashboards/` – provide views into data ingestion status, regimes, universes, profiles, decisions, trades.
- `alerts/` – alert rules for critical failures or anomalies.


## 3. Data Contracts

### 3.1 Inputs

- Logs and metrics from all other subsystems.
- Status tables like `ingestion_runs`, `black_swan_state_history`, `meta_controller_config_proposals`.

### 3.2 Outputs

- Not additional core tables; mainly dashboards and alerting rules.
- Optionally a `system_events` table summarizing major events (e.g. EMERGENCY state changes, config updates).


## 4. Key Views

- **Data Ingestion Dashboard**:
  - Latest ingestion run status for each feed.
  - Data quality metrics.
- **Profile Dashboard**:
  - Coverage (how many companies have current profiles).
  - Profile update latencies.
- **Regime & Universe Dashboard**:
  - Current regime and recent history.
  - Active universe snapshots.
- **Decision & Trade Timeline**:
  - For a given ticker/date, show regime, universe membership, profile versions, decisions, risk actions, trades.
- **Black Swan Dashboard**:
  - Current emergency state, recent events, SOP actions.
- **Meta Orchestrator Dashboard**:
  - Proposals, statuses, applied changes.


## 5. Interactions with Other Players

- Receives metrics/logs from all components.
- Provides humans and possibly automated systems (Meta Orchestrator) with observability.


## 6. Current Implementation Status (Monitoring core)

- Implemented modules under `prometheus/monitoring/`:
  - `logging_setup.py` – helper to configure structured logging via
    `prometheus.core.logging`.
  - `metrics.py` – placeholder metrics API (`record_metric`) for future
    integration with a metrics backend.
  - `dashboards.py` – placeholder dashboard descriptors.
  - `alerts.py` – placeholder alert definition descriptors.
  - `web/` – FastAPI-based monitoring API exposing JSON endpoints for health,
    ingestion runs, profiles, backtests, decisions, risk actions, trades, and
    meta proposals.
- Frontend:
  - `prometheus/monitoring/frontend/` – React + TypeScript + Tailwind + Vite
    single-page app providing an initial Overview dashboard (DB health,
    backtest list, placeholder equity curve) and navigation skeleton for other
    views.
- Tests:
  - `tests/unit/test_monitoring_web_imports.py` – smoke tests for monitoring
    web API imports and `create_app` entrypoint (FastAPI optional).
  - Frontend is exercised manually via `npm run dev`.
- Dev workflows:
  - `dev_workflows/PHASE11_MONITORING.md` (to be added) will describe how to
    run the monitoring API and frontend locally.


## 7. Deferred Enhancements / TODOs (later passes)

The following items are intentionally **not** part of the current monitoring
core and should be implemented in later passes:

- Metrics backend integration
  - Wire `metrics.record_metric` into a real backend (e.g. Prometheus or
    StatsD), and add instrumentation to key subsystems.
- Dashboard expansion
  - Implement dedicated views for ingestion, profiles, regimes/universes,
    decisions & trades, Black Swan state, and Meta proposals using the web API.
- Alerts
  - Implement alert rules and wiring to a notification system (e.g. email,
    Slack, PagerDuty) based on DB status and metrics.
- System event timeline
  - Add an optional `system_events` table and endpoints to support the
    "Decision & Trade Timeline" view described above.
- Authentication and access control
  - Restrict access to the monitoring UI and API in multi-user or
    production deployments.
