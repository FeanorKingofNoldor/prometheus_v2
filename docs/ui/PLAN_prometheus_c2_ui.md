# Prometheus C2 UI – Executive Implementation Plan

This plan describes how to turn the current Prometheus v2 architecture + specs + HTML mock (`docs/ui_c2_mock/index.html`) into the **Prometheus C2** native command & control terminal (Godot client + backend APIs).

The audience is "future us" and any agent working in `prometheus_v2` so they can pick this up and continue the work.

---

## 1. Scope and End State

### 1.1 What we are building

Prometheus C2 is a **native desktop UI** that:

- Implements the Bloomberg-style, dark, multi-window UI described in `docs/specs/200_monitoring_and_ui.md`.
- Integrates **3D ANT_HILL worlds** for system / pipeline / DB / embedding visualization (read-only control with local view controls only).
- Provides a **command surface** (2D panels + text terminal + Kronos Chat) to:
  - Launch backtests and experiments.
  - Create synthetic scenario sets / datasets.
  - Trigger DAGs for specific markets/dates.
  - Stage & apply config changes (under Kronos + numeric checks).
- Talks ONLY to backend APIs (Monitoring, Visualization, Control, Kronos, Geo) served by Prometheus; it never touches DBs directly and never submits orders itself.

### 1.2 Tech decisions (locked in)

- **Client runtime:** Godot 4 (2D + 3D) as the engine for C2.
- **Client location:** new top-level directory in this repo: `prometheus_c2/`.
- **Backend APIs:** as specified in sections 9–10 of `docs/specs/200_monitoring_and_ui.md`.
- **Web mock:** `docs/ui_c2_mock/index.html` is the reference layout/ambience for the first Godot implementation (spaceship bridge + terminal vibe).

We will NOT:

- Use WebGL/Three.js for the final C2 client (only for ANT_HILL web prototype).
- Let ANT_HILL initiate any mutating actions; it is visualization-only.

---

## 2. High-Level Phases

1. **APIs & Contracts (backend skeleton)**
2. **Godot project bootstrap (`prometheus_c2/`)**
3. **Core UI shell + panel framework in Godot**
4. **Read-only data wiring (Monitoring + Visualization APIs)**
5. **Command/control wiring (Control + Kronos APIs)**
6. **ANT_HILL 3D worlds in Godot**
7. **World map / globe in Godot**
8. **Refinement, theming, and performance tuning**

These phases can overlap, but the order is important for dependency reasons.

---

## 3. Phase 1 – Backend APIs & Contracts

### 3.1 Implement Monitoring / Status APIs (read-side)

Implement in `prometheus/monitoring/api.py` and related modules, backed by runtime/historical DB and orchestrator metadata:

- `GET /api/status/overview`
- `GET /api/status/pipeline?market_id=...`
- `GET /api/status/regime?region=...&as_of_date=...`
- `GET /api/status/stability?region=...&as_of_date=...`
- `GET /api/status/fragility?region=...&entity_type=...&as_of_date=...`
- `GET /api/status/fragility/{entity_id}?as_of_date=...`
- `GET /api/status/assessment?strategy_id=...&as_of_date=...`
- `GET /api/status/universe?strategy_id=...&as_of_date=...`
- `GET /api/status/portfolio?portfolio_id=...&as_of_date=...`
- `GET /api/status/portfolio_risk?portfolio_id=...&as_of_date=...`
- `GET /api/meta/configs`
- `GET /api/meta/performance?engine_name=...&period=...`
- `WS /api/status/live_stream`

Focus first on providing **mock or partial data** for these endpoints that:

- Matches the JSON shapes in `200_monitoring_and_ui.md`.
- Lets the UI render realistic-looking panels even before full engine implementations are done.

### 3.2 Implement Visualization APIs for ANT_HILL and 3D views

Define and implement in `prometheus/monitoring/visualization_api.py`:

- `GET /api/scenes`
- `GET /api/scene/{view_id}`
- `GET /api/traces/{trace_id}`
- `WS /api/traces/live?market_id=...&mode=LIVE|PAPER|BACKTEST`
- `GET /api/db/runtime/{table}?limit=...&as_of_date=...&filters=...`
- `GET /api/db/historical/{table}?limit=...&date<=...&filters=...`
- `GET /api/embedding_space/{space_id}?...` (e.g., joint_profiles, text_news, regime_states)

Initially, scenes and traces can be **static or semi-static** templates that mirror:

- The master architecture diagram.
- A single end-of-day pipeline.
- A simple DB district.

Later, they should be driven by:

- Actual engine configs and DAGs.
- Real runtime/historical DB schemas.

### 3.3 Implement Control APIs (write-side)

Implement control endpoints under `prometheus/monitoring/control_api.py` (or similar):

- `POST /api/control/run_backtest`
- `POST /api/control/create_synthetic_dataset`
- `POST /api/control/schedule_dag`
- `POST /api/control/apply_config_change`
- `GET /api/control/jobs/{job_id}`

Initially, wire these to:

- A job registry that can track jobs + statuses.
- Stub handlers that queue jobs for orchestrator or simply record them.

Later, they will:

- Integrate with real DAG orchestration, backtest infra, and ScenarioEngine.

### 3.4 Implement Kronos Chat API

Create a simple stub for `POST /api/kronos/chat` that:

- Accepts `{question, context}`.
- Returns dummy `answer` + empty `proposals`.

This can be progressively wired up to a real LLM + numeric tools later.

### 3.5 Implement Geo APIs

Support the world map / globe:

- `GET /api/geo/countries?as_of_date=...`
- `GET /api/geo/country/{country_code}?as_of_date=...`

Initially, return mock data for a handful of countries; wire to real STAB + portfolio exposures later.

---

## 4. Phase 2 – Godot Project Bootstrap (`prometheus_c2/`)

### 4.1 Create Godot project

- Create a new directory `prometheus_c2/` at repo root.
- In Godot 4, initialize a new project using that directory.
- Set up basic folders:

  ```text
  prometheus_c2/
    project.godot
    addons/
    assets/
      fonts/
      icons/
      shaders/
    src/
      core/
      ui/
      panels/
      three_d/
      net/
      themes/
  ```

### 4.2 Core autoload singletons

Configure these as autoloads in Godot:

- `src/core/AppState.gd` – global context:
  - `market_id`, `strategy_id`, `portfolio_id`.
  - `as_of_date`, `mode` (LIVE/PAPER/BACKTEST).
  - Current workspace and active panel.

- `src/net/ApiClient.gd` – wrapped HTTP/WS client:
  - Methods for all Monitoring, Visualization, Control, Kronos, Geo endpoints.
  - Configurable `API_BASE_URL`.

- `src/core/CommandBus.gd` – high-level commands:
  - `run_backtest`, `create_synthetic_dataset`, `schedule_dag`, `apply_config_change`, `open_job`.
  - Uses `ApiClient` and manages job status cache.

- `src/core/WorkspaceManager.gd` – layout state:
  - Which panels are open per workspace.
  - Saved layouts.

### 4.3 Shared theme & fonts

- Import mono/sans fonts matching the web mock (e.g., JetBrains Mono + a clean sans).
- Create a Godot theme resource (e.g. `themes/TerminalTheme.tres`) that encodes:
  - Colors (bg, fg, accent-good, accent-info, warning, etc.).
  - Panel styles (rounded corners, borders, glows).

The goal is to visually approximate `docs/ui_c2_mock/index.html`.

---

## 5. Phase 3 – Core UI Shell + Panel Framework in Godot

### 5.1 Main viewport

Create `src/ui/MainShell.tscn` + `MainShell.gd`:

- Top bar:
  - Logo, mode, global KPIs, regime + System STAB, clock.
- Left navigation:
  - Workspaces list.
  - Panel list (Overview, Regime & STAB, Soft Targets, Assessment & Universe, Portfolio & Risk, Meta & Experiments, Live System, ANT_HILL, World Map / Globe, Terminal, Kronos Chat).
- Center area:
  - Tab bar for quickly switching active panels within the workspace.
  - Central panel container where actual panels are docked.
- Right strip:
  - Alerts.
  - System console.

Use Godot containers (VBoxContainer, HBoxContainer, SplitContainer, etc.) to mirror the HTML mock layout.

### 5.2 Panel base class

Create `src/panels/BasePanel.gd`:

- Properties:
  - `panel_id: String`.
  - `display_name: String`.
- Methods:
  - `func on_activated() -> void` – called when panel becomes visible.
  - `func on_deactivated() -> void`.
  - `func refresh_data() -> void` – triggers API calls.

Each concrete panel scene inherits from `BasePanel`.

### 5.3 Implement key panel shells (no data yet)

Create stub scenes + scripts for at least:

- `OverviewPanel.tscn` / `.gd`
- `RegimeStabPanel.tscn` / `.gd`
- `FragilityPanel.tscn` / `.gd`
- `AssessmentUniversePanel.tscn` / `.gd`
- `PortfolioRiskPanel.tscn` / `.gd`
- `MetaExperimentsPanel.tscn` / `.gd`
- `LiveSystemPanel.tscn` / `.gd`
- `AntHillPanel.tscn` / `.gd` (3D placeholder viewport for now)
- `GeoPanel.tscn` / `.gd`
- `TerminalPanel.tscn` / `.gd`
- `KronosChatPanel.tscn` / `.gd`

Initially, only implement the layout (cards, placeholders) mirroring the web mock; no real API calls.

---

## 6. Phase 4 – Wire Read-Only Data (Monitoring + Visualization)

### 6.1 Overview & Live System

- **OverviewPanel**:
  - On `refresh_data`, call:
    - `ApiClient.get_status_overview()`.
    - `ApiClient.get_status_regime()` (for summary regime view).
    - `ApiClient.get_status_stability()` (for System STAB index).
  - Populate the KPI boxes and timeline placeholders.

- **LiveSystemPanel**:
  - Use `get_status_pipeline(market_id)` for per-market DAG status.
  - Subscribe to `WS /api/status/live_stream` for task and resource events.
  - Render a simplified Gantt/timeline + task list.

### 6.2 Regime & STAB, Soft Targets

- **RegimeStabPanel**:
  - Use `get_status_regime(region, date_range)` for regime timeline.
  - Use `get_status_stability(region, date_range)` for stability heatmap.

- **FragilityPanel**:
  - Use `get_status_fragility(region, entity_type, as_of_date)` to build soft target tables.
  - Use entity details endpoint for right-side drill-down.

### 6.3 Assessment, Universe, Portfolio & Risk

- **AssessmentUniversePanel**:
  - Use `get_status_assessment(strategy_id, as_of_date)`.
  - Use `get_status_universe(strategy_id, as_of_date)`.

- **PortfolioRiskPanel**:
  - Use `get_status_portfolio(portfolio_id, as_of_date)`.
  - Use `get_status_portfolio_risk(portfolio_id, as_of_date)`.

### 6.4 ANT_HILL & DB/Embedding views

- **AntHillPanel**:
  - Start with 2D/3D placeholder; then:
    - Fetch scenes with `get_scene(view_id)`.
    - Fetch traces with `get_trace(trace_id)` or subscribe to `traces/live`.
    - Optionally fetch DB snapshots and embedding spaces for overlays.
  - Implement a minimal Godot 3D scene that:
    - Draws nodes and connections as meshes.
    - Animates simple packets along edges.
  - Keep all of this strictly **read-only**.

### 6.5 Geo (world map / globe)

- **GeoPanel**:
  - For first pass, implement a 2D map (e.g., static background + clickable regions) using `/api/geo/countries`.
  - Shade countries by stability/fragility.
  - On click, load `/api/geo/country/{code}` and show details.

---

## 7. Phase 5 – Wire Control & Terminal (Mutating Actions)

### 7.1 CommandBus integration

- Implement `CommandBus` methods for:
  - `run_backtest(params)` → `POST /api/control/run_backtest`.
  - `create_synthetic_dataset(params)` → `POST /api/control/create_synthetic_dataset`.
  - `schedule_dag(params)` → `POST /api/control/schedule_dag`.
  - `apply_config_change(params)` → `POST /api/control/apply_config_change`.
  - `watch_job(job_id)` → `GET /api/control/jobs/{job_id}` (+ periodic refresh / WS subscription if added).

- Expose these methods to UI panels but **not** to ANT_HILL.

### 7.2 TerminalPanel

- Implement parsing of basic commands:
  - `backtest run ...`
  - `synthetic create ...`
  - `dag run ...`
  - `config apply ...`

- Map parsed commands to `CommandBus` calls and append logs to the console.

### 7.3 Meta & Experiments panel controls

- Provide GUI forms for:
  - Staging config changes and calling `apply_config_change`.
  - Launching standard experiments (backtest grids) via `run_backtest`.

### 7.4 Portfolio & Risk controls

- Provide forms for editing risk settings for a portfolio:
  - Max leverage, soft target exposure caps, turnover budgets.
- Backend: these should write config entries (via a small config service / DB table) or call targeted Control APIs.

All control flows must log actions and never operate silently.

---

## 8. Phase 6 – Kronos Chat Integration

### 8.1 Frontend

- In `KronosChatPanel`:
  - Implement a chat UI (input box + transcript list).
  - On send, call `POST /api/kronos/chat` with `{question, context}` derived from AppState.
  - Render `answer` in the transcript.
  - Render `proposals` in a side list, with buttons:
    - “Simulate backtest” → `CommandBus.run_backtest` with provided params.
    - “Stage config” → open Meta/Experiments panel with fields pre-filled.

### 8.2 Backend (stub → real)

- Start with dummy responses.
- Later, wire to a real LLM + numeric tooling that uses Monitoring + Control APIs internally.

---

## 9. Phase 7 – ANT_HILL 3D Worlds in Godot

### 9.1 Scene loader

- Implement `three_d/SceneGraph.gd` that:
  - Takes scene JSON from `/api/scene/{view_id}`.
  - Creates 3D nodes (meshes) and connections.
  - Manages camera and controls.

### 9.2 Packet/trace renderer

- Implement `three_d/TracePlayer.gd` that:
  - Consumes event streams from `/api/traces/{trace_id}` or `/api/traces/live`.
  - Spawns packet instances and animates them along connections.

### 9.3 DB & embedding overlays

- Implement billboards and axis helpers similar to the web ANT_HILL, driven by DB/embedding APIs.

### 9.4 Strict read-only behavior

- Double-check there are **no** Control API calls from any `three_d/*` scripts.
- Any “action” from ANT_HILL is routed as a selection/highlight into panels, not as a job.

---

## 10. Phase 8 – World Map / Globe in Godot

### 10.1 2D map

- Implement a control in `GeoPanel` that draws a stylized 2D map and colors countries using `/api/geo/countries`.
- Add interaction to set AppState country filter and coordinate with other panels.

### 10.2 3D globe

- Build a 3D sphere with country borders; project colors onto it.
- Support orbit/zoom and click-to-select country.
- Reuse the same `/api/geo/*` endpoints; the globe is purely client-side.

---

## 11. Phase 9 – Polish, Theming, and Performance

### 11.1 Match the “spaceship bridge + matrix terminal” vibe

- Iterate on theme and effects:
  - Scanline overlays, subtle flicker (optional).
  - Glow around critical alerts and high-STAB entities.

### 11.2 Multi-window support

- Use Godot’s windowing to allow panels to detach into separate OS windows.
- Store workspace layouts in a simple config file per user.

### 11.3 Performance considerations

- Limit number of active panels rendering heavy 3D at once.
- Add quality presets (HIGH/MEDIUM/LOW) controlling:
  - ANT_HILL detail.
  - Globe detail.
  - Refresh frequency of heavy charts.

---

## 12. Milestones & Checkpoints

1. **Milestone 1 – Static Godot shell**
   - `prometheus_c2` project created.
   - MainShell + panel shells implemented.
   - No real data, but you can click around like the HTML mock.

2. **Milestone 2 – Monitoring data wired (read-only)**
   - Overview, Regime&STAB, Soft Targets, Assessment, Portfolio & Risk, Live System panels all show mock or partial real data from Monitoring APIs.

3. **Milestone 3 – Control plane wired**
   - Terminal panel and Meta/Experiments panel can launch jobs via Control APIs.
   - Jobs are visible in Live System and console.

4. **Milestone 4 – ANT_HILL and Geo integrated**
   - ANT_HILLPanel and GeoPanel render 3D scenes using Visualization + Geo APIs (read-only).

5. **Milestone 5 – Kronos Chat online**
   - KronosChatPanel exchanges with backend chat API and can spawn experiments/config staging flows.

At that point, Prometheus C2 is functionally complete; further work is polish, performance, and deeper integration with real engine implementations.
