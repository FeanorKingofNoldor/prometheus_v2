# 200 – Monitoring and UI Specification

## 1. Purpose

Define the monitoring and user interface layer for Prometheus v2:
- A **Bloomberg-style**, dark-mode, multi-window desktop UI for power use.
- A future **Android/mobile** view for status + alerts.
- How the UI visualizes per-market pipelines, regimes, stability, soft targets, portfolios, and meta/experiments.
- How the **Kronos Chat** interface exposes the Meta-Orchestrator safely.

This spec describes UX and API contracts, not specific frontend frameworks.

---

## 2. Design Principles

1. **Operational clarity**
   - You should be able to answer in seconds:
     - “Are we safe?” (risk, stability, leverage).
     - “What’s the regime?” (by region).
     - “What are we betting on?” (top positions/themes, fragility shorts).
     - “What changed?” (configs, signals, risk, P&L).

2. **Multi-window, multi-monitor**
   - Any main panel can be detached into its own OS window.
   - Layouts are savable (e.g., “Live US_EQ”, “Global Research”).

3. **Dark, high-contrast theme**
   - Dark background with bright, saturated accents.
   - Consistent color semantics across all views (e.g., red = risk, green = good P&L).

4. **Data provenance and replayability**
   - All views can be switched to **“as-of date”** mode:
     - Show system state as of a historical date T using `engine_decisions`, `decision_outcomes`, and DB snapshots.

5. **LLMs as copilots, not autopilots**
   - Kronos Chat can explain, propose, and analyze.
   - It cannot directly change configs or trade; numeric pipelines and explicit approvals are mandatory.

---

## 3. Theme and Layout

### 3.1 Dark theme tokens

Define a visual design system (independent of UI framework):

- Backgrounds:
  - `bg_primary`: near-black.
  - `bg_panel`: dark gray.
- Text:
  - `fg_primary`: light gray/white.
  - `fg_muted`: mid-gray.
- Accents:
  - `accent_good`: green.
  - `accent_bad`: red.
  - `accent_warning`: amber.
  - `accent_info`: blue/cyan.
- Gridlines and borders in subtle mid-gray.

All charts, tables, and widgets must use these tokens (no arbitrary colors per module).

### 3.2 Layout model

UI is composed of **panels** organized into **workspaces**:

- Panels:
  - Overview Dashboard
  - Regime & Stability
  - Soft Targets & Fragility
  - Assessment & Universe
  - Portfolio & Risk
  - Meta & Experiments
  - Kronos Chat

- Each panel can be:
  - a tab in a workspace,
  - or detached into its own window.

Workspaces are saved/restored:
- “US Live”: Overview + US_EQ Regime/Stability + US_EQ Portfolio.
- “Global Fragility”: Soft Targets + Regime/Stability for multiple regions.
- “Research”: Meta/Experiments + Assessment diagnostics.

---

## 4. Backend Monitoring API (Conceptual)

Monitoring views are powered by a REST/gRPC/WebSocket layer, e.g. under `prometheus/monitoring/api.py`.

We outline key endpoints/data contracts.

### 4.1 System overview

`GET /api/status/overview`

Returns:
- Global KPIs:
  - total P&L (today, MTD, YTD),
  - max drawdown (rolling),
  - net/gross exposure, leverage,
  - global stability index.
- Current regimes per region:
  - `[{region, regime_label, confidence}]`.
- Active alerts (high-level):
  - severity, type, message, affected markets/entities.

### 4.2 Per-market pipeline status

`GET /api/status/pipeline?market_id=US_EQ`

Returns:
- Current market state (`PRE_OPEN`, `SESSION`, `POST_CLOSE`, etc.).
- DAG/job status for that market (from orchestrator):
  - job name,
  - last run status,
  - latency vs SLO,
  - next scheduled run.

This drives a **pipeline timeline widget** in the UI showing per-market state and job health.

### 4.3 Regime & Stability

`GET /api/status/regime?region=US`
- Time series of regime labels and confidences.
- Embedding summaries for visualization (e.g., cluster projections).

`GET /api/status/stability?region=US`
- Stability metrics over time:
  - liquidity, vol, contagion components.
- Current stability index and sub-scores.

These power the Regime & Stability panel.

### 4.4 Soft Targets & Fragility

`GET /api/status/fragility?region=GLOBAL&entity_type=ANY`

Returns a table of entities with:
- `entity_id`, `entity_type` (COMPANY, SOVEREIGN, SECTOR, FX).
- `SoftTargetScore`, `FragilityAlpha`, `FragilityClass`.
- Key risk flags from profiles and pricing metrics.

`GET /api/status/fragility/{entity_id}`
- Detailed history of scores.
- Scenario P&L from Stability & Soft-Target engine.
- Existing positions and suggested fragility trades.

### 4.5 Assessment & Universe

`GET /api/status/assessment?strategy_id=...&as_of_date=...`
- For each instrument in the universe:
  - expected return, horizon, confidence,
  - alpha family breakdown (e.g., value, momentum, fragility contributions).

`GET /api/status/universe?strategy_id=...&as_of_date=...`
- Universe membership and scores for each candidate.

### 4.6 Portfolio & Risk

`GET /api/status/portfolio?portfolio_id=...`
- Current positions.
- P&L breakdown (YTD, MTD, daily).
- Exposures by:
  - sector, country, factor, currency, fragility class.

`GET /api/status/portfolio_risk?portfolio_id=...`
- Risk metrics: vol, VaR/ES, drawdown.
- Scenario P&L for key scenarios.

### 4.7 Meta & Experiments

`GET /api/meta/configs`
- Current configs per engine and recent variants.

`GET /api/meta/performance?engine_name=...`
- Performance across configs and regimes over a defined period.

These endpoints must be able to answer queries for **current state** and for **as-of historical dates** (using filters on `engine_decisions`, `decision_outcomes`, etc.).

---

## 5. Core Panels (Desktop UI)

### 5.0 Live System View (Pipelines & Resources)

Purpose: real-time view of what the system is doing **right now**.

Elements:
- **Per-market pipeline timeline** (already powered by `/api/status/pipeline`):
  - Shows which DAGs/tasks are queued, running, succeeded, or failed for each `market_id`.
  - Visualized as a Gantt/timeline with color-coded states.

- **Current task list**:
  - Stream of currently running tasks with:
    - `job_id`, `market_id`, `engine_name` (if applicable),
    - start time, elapsed time,
    - resource profile (CPU/GPU),
    - node/worker identity (if/when clustered).

- **Resource usage panel**:
  - CPU utilization (per core group),
  - RAM usage,
  - GPU usage (V100: memory, SM utilization),
  - IO metrics (optional).

Interactions:
- Filter tasks by `market_id`, `priority_tier`, `engine_name`.
- Click a running task to see its logs and inputs/outputs context.

Backend support:
- WebSocket endpoint, e.g. `GET /api/status/live_stream`, streaming:
  - task start/finish events,
  - periodic resource snapshots.
- Integration with orchestrator’s task metadata and system metrics exporter.

This panel complements the higher-level Overview and per-market pipeline views by giving a "live console" feel, similar to a process monitor for the entire Prometheus stack.

### 5.1 Overview Dashboard (“Flight Deck”)

Top strip:
- Global KPIs: P&L, drawdown, leverage, stability index, regime summary.

Center:
- Regime band timeline (with macro event markers).
- Global stability gauges.

Bottom:
- Active alerts feed (clickable to drill down).

Interactions:
- Select a date range → all charts filter.
- Click an alert → open related panel in same workspace or new window.

### 5.2 Regime & Stability Panel

Left:
- Timeline of regimes by region.
- Heatmap of stability (region × time).

Right:
- Detailed regime state for selected date/region:
  - label, confidence, embedding projection,
  - top drivers (factors, macro events).
- Stability breakdown:
  - liquidity score, vol score, contagion score.

### 5.3 Soft Targets & Fragility Panel

- Sortable table of entities with fragility metrics.
- Filters: region, entity type, fragility class.
- Detail pane with:
  - SoftTargetScore/FragilityAlpha history.
  - Profile snapshot summary.
  - Scenario P&L (for different shocks).
  - Current positions and suggested structures.

### 5.4 Assessment & Universe Panel

- Universe view per strategy:
  - membership, scores, reasons for inclusion/exclusion.
- Assessment detail per instrument:
  - expected return/horizon,
  - contributions from alpha families,
  - recent news/profile highlights.

### 5.5 Portfolio & Risk Panel

- Positions table with P&L, contributions to risk.
- Exposure breakdown charts (sector, factor, region, fragility class).
- Scenario tester: select scenario → P&L distribution and risk metrics.

### 5.6 Meta & Experiments Panel

- Config dashboard:
  - current `config_id`s per engine,
  - tested variants with performance metrics.
- Change log:
  - chronological list of config changes, reasons, and backtest results.

---

## 6. Kronos Chat (Meta-Orchestrator Interface)

### 6.1 UX

Panel divided into:
- Left: chat conversation (user ↔ Kronos).
- Right: context and proposals:
  - performance summaries relevant to the current question,
  - proposed config diffs, experiments, or diagnostics.

### 6.2 Capabilities

User can ask Kronos:
- “Why did we de-risk EU banks last week?”
- “Which configs underperform in crisis regimes?”
- “Propose safer Assessment configs with higher weight on fragility.”

Backend responsibilities:
- Fetch relevant **numeric context**:
  - subset of `engine_decisions`, `decision_outcomes`, `engine_configs`, risk reports.
- Call LLM with:
  - structured data + question,
  - tools for metrics queries if needed.
- Return:
  - human-readable explanation,
  - optional **structured proposals** (e.g., JSON/YAML config suggestions).

### 6.3 Safety and control

- Kronos Chat cannot:
  - directly modify `engine_configs` or push trades.
- Any structured proposal must:
  - be displayed and inspectable,
  - go through numeric backtest/validation pipeline,
  - followed by explicit user or policy-based approval.

API sketch:

`POST /api/kronos/chat`
- `input`: user query + optional context filters (engine, period, portfolio).
- `output`: text answer + optional `proposals: [...]`.

---

## 7. Android / Mobile View

A later-phase, read‑mostly interface sharing the same APIs.

### 7.1 Home screen

- Global KPIs: total P&L, daily P&L, leverage, stability index, current regimes.
- Quick status cards per region: green/amber/red.

### 7.2 Alerts view

- List of active alerts.
- Tapping → detail screen with:
  - short summary,
  - affected portfolios/entities,
  - simple charts.

### 7.3 Portfolio summary

- List of portfolios with:
  - P&L, risk, fragility exposure.

Control surface (future):
- Possibly ways to enter pre-defined “risk-off” modes (e.g. scale down exposure) after multi-step confirmation.

---

## 8. Integration with Calendars & Scheduling

The monitoring UI should:
- Display **market state per region** (OPEN/PRE_OPEN/POST_CLOSE/HOLIDAY) using `TradingCalendar`.
- Visualize per-market DAGs/job status based on orchestrator metadata.
- Indicate if core daily SLOs have been met (ingestion, engines, decision logging).

This gives a unified view of both **market state** and **system state**, and is essential for running Prometheus v2 "like a Swiss clockwork" across US, Europe, and Asia.

---

## 9. Prometheus C2 – Native Command & Control Terminal

### 9.1 Purpose and scope

**Prometheus C2** (Command & Control) is the native desktop "terminal" for Prometheus v2. It is a standalone application that:
- Implements the **Bloomberg-style, dark, multi-window UI** defined in this spec.
- Integrates **3D ANT_HILL worlds** for architecture, DB, and embedding visualization.
- Provides a **command surface** for interacting with Prometheus engines:
  - Run backtests and experiments.
  - Trigger DAGs for specific markets/dates.
  - Generate synthetic datasets via the Scenario/Synthetic engine.
  - Stage and apply config changes (after validation).
  - Interact with **Kronos Chat**.

Prometheus C2 is a **client only**: it never talks to databases directly, and it cannot trade. All reads and writes go through explicit backend APIs.

### 9.2 Technology choice

Prometheus C2 SHOULD be implemented as a **native game-like client** using a modern 2D+3D engine. The reference choice is:
- **Godot 4** as the client runtime:
  - 2D UI panels for all monitoring views.
  - 3D scenes for ANT_HILL visualization and future globes/maps.
  - HTTP/WebSocket clients to talk to backend APIs.

The client code lives in a top-level directory, e.g. `prometheus_c2/`, within the `prometheus_v2` repository so that UI and backend evolve together. This can be split into its own repo later if desired.

### 9.3 Client architecture

Prometheus C2 is organized into core subsystems:

- `AppState` – global context:
  - Selected `market_id`, `strategy_id`, `portfolio_id`.
  - `as_of_date` and **mode** (`LIVE`, `PAPER`, `BACKTEST`).
  - Active workspace layout and open panels.

- `ApiClient` – HTTP/WebSocket wrapper:
  - Implements all `/api/status/...`, `/api/scene/...`, `/api/traces/...`, `/api/db/...`, `/api/embedding_space/...`, `/api/geo/...`, `/api/control/...`, and `/api/kronos/...` calls.
  - Maintains live WebSocket connections for `/api/status/live_stream` and `/api/traces/live`.

- `CommandBus` – unified control plane from UI to backend:
  - Provides high-level commands for the rest of the client:
    - `run_backtest(...)`
    - `create_synthetic_dataset(...)`
    - `schedule_dag(...)`
    - `apply_config_change(...)`
  - Translates commands into `ApiClient` calls and tracks job IDs, progress, and logs.

- `WorkspaceManager` – manages panels and layouts:
  - Workspaces like "US Live", "Global Fragility", "Research".
  - Multi-monitor/multi-window layouts, save/restore.

Panels are implemented as reusable 2D scenes:
- Overview Dashboard.
- Regime & Stability.
- Soft Targets & Fragility.
- Assessment & Universe.
- Portfolio & Risk.
- Meta & Experiments.
- Live System (pipelines & resources).
- Kronos Chat.
- Text Terminal (command-line style interface).
- ANT_HILL 3D world(s).
- World Map / Globe.

Each panel:
- Reads data via `ApiClient`.
- Writes context back into `AppState` (e.g., selected portfolio, country, regime bucket).
- May dispatch commands via `CommandBus`.

### 9.4 ANT_HILL integration

The ANT_HILL visualization is integrated as one or more 3D panels inside Prometheus C2. It consumes the **Visualization API** (see section 10) to:
- Render subsystem/engine/DB topologies as 3D scenes.
- Replay and stream traces as animated packets along lanes.
- Show DB table contents on in-world billboards.
- Display embedding spaces in 3D, with axis legends and filters.

ANT_HILL is **read-only with respect to Prometheus control**:
- It may offer rich local controls for visualization (camera, filters, trace playback, highlighting) only.
- It MUST NOT directly trigger backtests, synthetic data generation, DAG runs, or config changes.

All **mutating actions** (e.g., run backtest, create synthetic dataset, schedule DAG, apply config) live in 2D panels such as Meta & Experiments, Portfolio & Risk, and the Terminal panel, which call the Control APIs via `CommandBus`. ANT_HILL may visually reflect the results of those actions (e.g., showing a completed backtest run) but does not initiate them.

### 9.5 Terminal and Kronos Chat

Prometheus C2 includes:
- A **Terminal panel**:
  - Text input and log scrollback.
  - Commands like `backtest run ...`, `synthetic create ...`, `dag run ...`.
  - Client parses commands into structured `CommandBus` calls.

- A **Kronos Chat panel**:
  - Uses `POST /api/kronos/chat` to get explanations and structured proposals.
  - Shows proposals (config changes, experiments) in a side panel.
  - User can promote proposals into real actions via the Control API (never automatic).

Kronos Chat is implemented **on the backend**, close to the DBs and engines. It uses well-defined tools/endpoints (Monitoring + Control APIs), and may later be exposed via MCP, but MCP is not required by this spec.

---

## 10. Backend API Contracts for Monitoring, Visualization, and Control

This section defines the concrete API surface that Prometheus C2 (and Kronos Chat) rely on. All endpoints are JSON/HTTP unless noted; real-time feeds use WebSockets.

### 10.1 Monitoring / Status APIs

The **Monitoring APIs** are the read-side for all 2D panels and are largely derived from this spec's earlier sections:

- `GET /api/status/overview`
  - Global KPIs: P&L (daily/MTD/YTD), drawdown, net/gross exposure, leverage.
  - Global stability index.
  - Current regimes per region: `{region, regime_label, confidence}`.
  - High-level alerts: severity, type, message, affected markets/entities.

- `GET /api/status/pipeline?market_id=US_EQ`
  - Market state: `PRE_OPEN`, `SESSION`, `POST_CLOSE`, `HOLIDAY`, etc.
  - Per-DAG/job status: job name, last run status, latency vs SLO, next scheduled run.

- `GET /api/status/regime?region=US[&as_of_date=...]`
- `GET /api/status/stability?region=US[&as_of_date=...]`
  - Regime and stability time series and current values.

- `GET /api/status/fragility?region=GLOBAL&entity_type=ANY[&as_of_date=...]`
- `GET /api/status/fragility/{entity_id}?[as_of_date=...]`
  - Soft-target and fragility metrics per entity and detail for a single entity.

- `GET /api/status/assessment?strategy_id=...&as_of_date=...`
- `GET /api/status/universe?strategy_id=...&as_of_date=...`
  - Per-instrument assessment scores and universe membership.

- `GET /api/status/portfolio?portfolio_id=...&as_of_date=...`
- `GET /api/status/portfolio_risk?portfolio_id=...&as_of_date=...`
  - Portfolio positions, P&L, exposures, risk metrics, scenario P&L.

- `GET /api/meta/configs`
- `GET /api/meta/performance?engine_name=...&period=...`
  - Engine configs and performance per config/regime.

- `WS /api/status/live_stream`
  - Streams task start/finish events and periodic resource usage snapshots.

All time-based endpoints MUST support "as-of" semantics where meaningful via `as_of_date` and/or `date_range` parameters, using runtime DB tables (`engine_decisions`, `decision_outcomes`, etc.) as the source of truth.

### 10.2 Scenes and Traces for 3D Visualization

The **Visualization APIs** feed ANT_HILL and any other 3D/2D graph-based views.

#### 10.2.1 Scenes

- `GET /api/scenes`
  - List of `{id, name, description, tags}` for all available views.

- `GET /api/scene/{view_id}`
  - Returns topology for the requested view as:
  - Nodes: id, type, label, position, size, metadata.
  - Connections: from, to, lane, label, edge_type.
  - Ports: per-node input/output port definitions.

Scenes SHOULD cover:
- System overview (master architecture).
- Engine pipelines per market/strategy.
- Runtime and historical DB "districts".
- Encoder/embedding spaces.
- Geo/country stability map (see 10.6).

#### 10.2.2 Traces

- `GET /api/traces/{trace_id}`
  - Finite trace for deterministic replay (e.g., a single EOD run or backtest episode).

- `WS /api/traces/live?market_id=US_EQ&mode=LIVE|PAPER|BACKTEST`
  - Live event stream for current system activity.

Each event MUST include:
```json
{
  "t": "2025-01-02T21:30:00Z",
  "seq": 1234,
  "type": "engine_step",    // engine_step | data_flow | order_event | fill_event | decision_event | error
  "engine": "RegimeEngine",
  "phase": "start",         // for engine_step
  "source_id": "prices_daily",
  "target_id": "RegimeEngine",
  "lane": "prices",
  "payload": { "as_of_date": "2025-01-02", "region": "US" },
  "severity": "info"        // info | warn | error
}
```

### 10.3 DB Snapshots and Embedding Spaces

#### 10.3.1 DB snapshots

- `GET /api/db/runtime/{table}?limit=20&as_of_date=...&filters=...`
- `GET /api/db/historical/{table}?limit=20&date<=...&filters=...`

Return format:
```json
{
  "columns": ["instrument_id", "trade_date", "close", "volume"],
  "rows": [
    ["AAPL", "2025-01-02", 160.12, 23000000],
    ["MSFT", "2025-01-02", 320.45, 18000000]
  ]
}
```

This format is intentionally simple so it can feed both:
- 2D grid widgets in Prometheus C2.
- 3D billboards in ANT_HILL.

#### 10.3.2 Embedding spaces

- `GET /api/embedding_space/joint_profiles?as_of_date=...&universe=SNP500`
- `GET /api/embedding_space/text_news?window=2024-12-01..2025-01-02&sector=TECH`

Return format:
```json
{
  "axis_labels": ["PC1", "PC2", "PC3"],
  "points": [
    {
      "id": "AAPL",
      "label": "AAPL",
      "x": -1.23, "y": 0.45, "z": 2.10,
      "color": "#22c55e",
      "size": 1.2,
      "metadata": {
        "sector": "Tech",
        "stability_score": 0.8,
        "fragility_score": 0.2
      }
    }
  ]
}
```

Coordinates may come from native 3D embeddings or from PCA/UMAP projections over higher-dimensional vectors stored in the `*_embeddings` tables.

### 10.4 Control APIs (Interactive Commands)

The **Control APIs** are the only way Prometheus C2 (and Kronos) may initiate changes or long-running jobs.

- `POST /api/control/run_backtest`
  - Body:
  ```json
  {
    "strategy_id": "main_us_eq",
    "portfolio_id": "live_us_eq",
    "market_id": "US_EQ",
    "start_date": "2020-01-01",
    "end_date": "2021-01-01",
    "synthetic_dataset_id": null,
    "config_overrides": {}
  }
  ```
  - Response: `{ "job_id": "bt_2020_us_eq_main_001" }`.

- `POST /api/control/create_synthetic_dataset`
  - Body (example):
  ```json
  {
    "name": "us_eq_crisis_2020_like",
    "base_universe": "SNP500",
    "regime": "CRISIS",
    "volatility_scale": 1.8,
    "correlation_pattern": "flight_to_quality",
    "horizon_days": 252
  }
  ```
  - Response: `{ "dataset_id": "syn_2020_crisis_01" }`.

- `POST /api/control/schedule_dag`
  - Body:
  ```json
  { "dag_name": "us_eq_engines_T", "as_of_date": "2025-01-02" }
  ```

- `POST /api/control/apply_config_change`
  - Body:
  ```json
  {
    "engine_name": "AssessmentEngine",
    "config_id": "cfg_assessment_v12",
    "new_config_body": { "...": "..." },
    "reason": "Kronos suggestion + manual approval",
    "approved_by": "feanor"
  }
  ```

- `GET /api/control/jobs/{job_id}`
  - Returns job status, progress, and recent logs.

All Control API calls MUST:
- Be logged for audit.
- Enforce appropriate safety and authorization rules.

### 10.5 Kronos Chat API and Tooling

The **Kronos Chat API** exposes a safe LLM-powered interface to the Meta-Orchestrator.

- `POST /api/kronos/chat`
  - Request:
  ```json
  {
    "question": "Why did we de-risk EU banks last week?",
    "context": {
      "portfolio_id": "live_eu_eq",
      "date_range": ["2025-01-01", "2025-01-31"],
      "engine": "PortfolioEngine"
    }
  }
  ```
  - Response:
  ```json
  {
    "answer": "We de-risked EU banks because ...",
    "proposals": [
      {
        "type": "config_change",
        "engine_name": "AssessmentEngine",
        "new_config_body": { "...": "..." },
        "summary": "Lower weight on carry signals in CRISIS regimes."
      },
      {
        "type": "experiment",
        "backtest_params": {
          "strategy_id": "main_eu_eq",
          "start_date": "2015-01-01",
          "end_date": "2024-12-31",
          "config_overrides": { "...": "..." }
        }
      }
    ]
  }
  ```

Kronos Chat:
- MUST use the Monitoring and Control APIs (or equivalent internal functions) as its tools.
- MUST NOT issue raw SQL or access databases directly.
- MUST NOT apply config changes or trade without explicit promotion via the Control API and numeric validation.

Internally, these tools MAY also be exposed via MCP for external LLM hosts, but MCP is optional and not required by this spec.

### 10.6 Geo / Country-Level Stability and Exposure

To support a world map / globe visualization for country-level risk:

- `GET /api/geo/countries?as_of_date=...`
  - Returns a list of countries with:
  ```json
  {
    "countries": [
      {
        "code": "US",
        "name": "United States",
        "region": "NA",
        "stability_index": 0.87,
        "fragility_index": 0.12,
        "soft_target_class": "LOW",
        "risk_flags": ["elevated_valuation"],
        "portfolio_exposure": {
          "gross": 0.25,
          "net": 0.18,
          "long_exposure": 0.30,
          "short_exposure": 0.12
        }
      }
    ]
  }
  ```

- `GET /api/geo/country/{country_code}?as_of_date=...`
  - Returns detailed history for a single country:
    - Stability/fragility time series.
    - Top contributing sectors/instruments.
    - Recent macro events.
    - Scenario P&L from stability/soft-target engines.

Prometheus C2 will:
- Implement a 2D flat map first (per-country polygons or textured map), colored by stability/fragility.
- Later, add a 3D globe view, projecting the same data onto a sphere and allowing interactive rotation and selection.
- Use these endpoints to coordinate country selection with other panels (Regime/Stability, Fragility, Portfolio, etc.).

---

This spec is the reference for implementing `prometheus/monitoring` (backend APIs) and the **Prometheus C2** native terminal (`prometheus_c2/`), as well as any future mobile or web UIs built on top of the same API surface.
