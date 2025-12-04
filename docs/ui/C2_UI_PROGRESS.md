# Prometheus C2 UI – Development Progress

## Overview

Building a Bloomberg-style command & control terminal for Prometheus v2 using:
- **Backend**: FastAPI REST APIs (Python)
- **Frontend**: Godot 4 native desktop client
- **Architecture**: Client-server with strict separation of concerns

## ✅ Phase 1: Backend API Skeleton (COMPLETE)

### Created Files
- `prometheus/monitoring/api.py` - Monitoring/status endpoints
- `prometheus/monitoring/visualization_api.py` - ANT_HILL visualization data
- `prometheus/monitoring/control_api.py` - Control operations (backtests, configs)
- `prometheus/monitoring/meta_api.py` - Kronos Chat + Geo APIs
- `prometheus/monitoring/app.py` - FastAPI application entry point
- `prometheus/monitoring/README.md` - API documentation

### API Endpoints Implemented (with mock data)

**Monitoring** (`/api/status`):
- System overview, pipeline status, regime, stability
- Fragility entities and details
- Assessment, universe, portfolio, portfolio risk

**Visualization** (`/api`):
- Scene metadata and scene graphs for 3D rendering
- Execution traces for playback
- DB table snapshots, embedding space vectors

**Control** (`/api/control`):
- Submit backtests, create synthetic datasets
- Schedule DAG execution, apply config changes
- Job tracking and status

**Kronos** (`/api/kronos`):
- Chat interface with proposal generation

**Geo** (`/api/geo`):
- Country-level data for world map visualization

**Meta** (`/api/meta`):
- Engine configurations and performance metrics

### Testing
✅ Server starts successfully  
✅ Endpoints return proper JSON responses  
✅ Mock data matches schema specifications  

### Run Backend
```bash
cd /home/feanor/coding_projects/prometheus_v2
source venv/bin/activate
uvicorn prometheus.monitoring.app:app --reload --host 0.0.0.0 --port 8000
```

Access docs at: http://localhost:8000/api/docs

---

## ✅ Phase 2: Godot Project Bootstrap (COMPLETE)

### Project Structure Created
```
prometheus_c2/
├── project.godot              # Godot 4 configuration
├── assets/                    # Fonts, icons, shaders
├── src/
│   ├── core/                  # Autoload singletons
│   │   ├── AppState.gd
│   │   ├── CommandBus.gd
│   │   └── WorkspaceManager.gd
│   ├── net/
│   │   └── ApiClient.gd       # Full HTTP client
│   ├── ui/                    # Main shell (TODO)
│   ├── panels/                # Panel implementations (TODO)
│   ├── three_d/               # ANT_HILL 3D (TODO)
│   └── themes/                # UI themes (TODO)
```

### Core Singletons Implemented

**AppState** - Global application state:
- Market, strategy, portfolio context
- Execution mode (LIVE/PAPER/BACKTEST)
- Active workspace and panel tracking
- Signals for state changes

**ApiClient** - Full HTTP client:
- All monitoring endpoints
- All visualization endpoints
- All control endpoints
- Kronos, Geo, Meta endpoints
- Async/await support with JSON parsing

**CommandBus** - High-level control operations:
- Backtest submission
- Synthetic dataset creation
- DAG scheduling
- Config changes
- Job tracking with signals

**WorkspaceManager** - Layout management:
- Workspace definitions (overview, trading, research, etc.)
- Panel detachment to separate windows
- Layout persistence to disk

### Open in Godot
```bash
cd /home/feanor/coding_projects/prometheus_v2/prometheus_c2
godot4 project.godot
```

---

## ✅ Phase 3: Core UI Shell (Prototype Complete)

Implemented:
1. `MainShell.tscn` with Bloomberg-style layout (top bar, left nav, center panels, right console).
2. `BasePanel.gd` with lifecycle hooks (on_activated, on_deactivated, refresh_data).
3. Panel scenes and scripts for Overview, Regime & STAB, Fragility, Assessment & Universe, Portfolio & Risk, Meta & Experiments, Live System, ANT_HILL (text preview), Geo, Terminal, and Kronos Chat.
4. `TerminalTheme.tres` applied via `MainShell.gd` as the global terminal theme.

Remaining for later polish:
- Final font imports and visual tweaks to fully match the HTML mock.
- 3D ANT_HILL visuals and world map/globe rendering.

---

## 📋 Phases 4-9 (PLANNED)

### Phase 4: Wire Read-Only Data
Connect panels to backend Monitoring/Visualization APIs

### Phase 5: Wire Control Plane
Implement Terminal, forms, and job submission UI

### Phase 6: Kronos Chat Integration
Build chat interface with proposal action buttons

### Phase 7: ANT_HILL 3D Worlds
Implement scene loader, trace player, and visualization

### Phase 8: World Map/Globe
Build 2D map and optional 3D globe

### Phase 9: Polish and Performance
Theming, multi-window support, performance tuning

---

## Key Design Decisions

### Backend APIs
- **Mock data first**: All endpoints return realistic mock data to enable UI development in parallel
- **Progressive wiring**: Will connect to real engines/DB as they mature
- **Consistent patterns**: All endpoints follow FastAPI conventions with Pydantic models

### Godot Client
- **Autoload singletons**: Global state and services accessible throughout the app
- **Panel architecture**: All panels inherit from BasePanel with consistent lifecycle
- **Read-only ANT_HILL**: 3D visualization is strictly read-only; no control operations
- **Workspace persistence**: Layout saved to disk for session restore

### API Client Pattern
- **Async/await**: All API calls use Godot's await for non-blocking execution
- **Error handling**: Graceful degradation with error dictionaries
- **Type safety**: Strong typing in GDScript where possible

---

## File Locations

### Backend
- `/home/feanor/coding_projects/prometheus_v2/prometheus/monitoring/`
  - `api.py`, `visualization_api.py`, `control_api.py`, `meta_api.py`, `app.py`

### Frontend
- `/home/feanor/coding_projects/prometheus_v2/prometheus_c2/`
  - `project.godot`, `src/core/`, `src/net/`

### Documentation
- `/home/feanor/coding_projects/prometheus_v2/docs/`
  - `PLAN_prometheus_c2_ui.md` - Full implementation plan
  - `specs/200_monitoring_and_ui.md` - UI specification
  - `ui_c2_mock/index.html` - HTML reference design

---

## Next Session TODO

1. **Create MainShell.tscn**:
   - Top bar (logo, mode, KPIs, clock)
   - Left nav (workspaces, panel list)
   - Center (tab bar, panel container)
   - Right strip (alerts, console)

2. **Implement BasePanel.gd**:
   - Properties: panel_id, display_name
   - Methods: on_activated(), on_deactivated(), refresh_data()

3. **Create panel stubs**:
   - OverviewPanel.tscn/gd
   - RegimeStabPanel.tscn/gd
   - FragilityPanel.tscn/gd
   - PortfolioRiskPanel.tscn/gd
   - (etc.)

4. **Import fonts and create theme**:
   - JetBrains Mono for monospace
   - Clean sans font for UI
   - TerminalTheme.tres matching HTML mock colors

---

## Testing Checklist

### Backend
- [x] Server starts without errors
- [x] `/` endpoint returns service info
- [x] `/api/status/overview` returns proper JSON
- [x] CORS allows local connections
- [x] Basic TestClient integration tests for key monitoring/meta/geo endpoints
- [ ] WebSocket endpoints (future)

### Frontend (current prototype)
- [x] Godot project opens without errors
- [x] Autoloads initialize successfully (AppState, ApiClient, CommandBus, WorkspaceManager)
- [x] ApiClient can connect to backend
- [x] Test API calls return data in Overview/Regime/Fragility/Portfolio panels
- [x] MainShell renders correctly and can switch panels/workspaces
- [x] Terminal and Meta & Experiments panels can submit jobs to control APIs
- [x] KronosChat panel can call `/api/kronos/chat` and display answers/proposals
- [ ] Theme and fonts fully match HTML mock

---

## Resources

- **Godot 4 Docs**: https://docs.godotengine.org/en/stable/
- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **Plan Document**: `docs/PLAN_prometheus_c2_ui.md`
- **Spec Document**: `docs/specs/200_monitoring_and_ui.md`
- **HTML Mock**: `docs/ui_c2_mock/index.html`

---

**Status**: Phase 1 ✅ Complete | Phase 2 ✅ Complete | Phase 3 🚧 Ready to Start
