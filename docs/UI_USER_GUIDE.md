# Prometheus C2 UI User Guide

## Overview
The Prometheus C2 (Command & Control) UI is a Bloomberg-style terminal interface built in Godot 4 for monitoring and controlling the Prometheus v2 quantitative trading system. It provides real-time visibility into all system components, from regime detection to portfolio risk.

## Architecture
- **Engine**: Godot 4.x
- **Language**: GDScript
- **Backend**: FastAPI REST server (Python)
- **Transport**: HTTP/JSON
- **Visualization**: 3D scene graphs via ANT_HILL

## Layout
The UI follows a Bloomberg-style layout:

### Top Bar
- **Logo**: Prometheus v2 branding
- **Mode**: System mode (PAPER, LIVE, BACKTEST)
- **KPIs**: P&L today, global stability index, leverage
- **Clock**: System time

### Left Navigation
**Workspaces** (top):
- Overview: System dashboard
- Trading: Active trading operations
- Research: Analysis and experiments
- Monitoring: Live system health
- Global: World-wide view

**Panels** (bottom):
- Overview
- Regime & STAB
- Soft Targets & Fragility
- Assessment & Universe
- Portfolio & Risk
- Meta & Experiments
- Live System
- ANT_HILL
- World Map / Globe
- Terminal
- Kronos Chat

Each panel has a detach button (↗) to open in a separate window.

### Center Area
- **Tab Bar**: Shows active panel title
- **Panel Host**: Displays the selected panel content

### Right Strip
- **Alerts**: Critical system alerts
- **Console**: Live log stream from all components

## Panels

### 1. Overview Panel
**Purpose**: System-wide KPIs and health dashboard

**Data Sources**:
- `/api/status/overview`
- `/api/status/regime?region=US`
- `/api/status/stability?region=US`

**Displays**:
- P&L: Today, MTD, YTD
- Risk: Max drawdown
- Exposure: Net, gross, leverage
- Global stability index
- Regime status per region
- Active alerts

**Refresh**: Auto-refreshes every 10 seconds

### 2. Regime & STAB Panel
**Purpose**: Regime detection and market stability metrics

**Data Sources**:
- `/api/status/regime?region={region}`
- `/api/status/stability?region={region}`

**Displays**:
- Current regime label and confidence
- Regime history (last 90 days)
- Current stability index
- Stability components: liquidity, volatility, contagion
- Stability history (last 90 days)

**Region**: Defaults to US, can be changed in AppState

### 3. Soft Targets & Fragility Panel
**Purpose**: Identify fragile entities (instruments, companies, sovereigns)

**Data Sources**:
- `/api/status/fragility?region={region}&entity_type={type}`
- `/api/status/fragility/{entity_id}`

**Displays**:
- Top 15 entities by soft target score
- Fragility alpha (quantitative measure)
- Fragility class (EXTREME, HIGH, MEDIUM, LOW, NONE)
- Entity type (INSTRUMENT, COMPANY, SOVEREIGN)

**Filters**: Region (GLOBAL, US, EU, ASIA), Entity type (ANY, INSTRUMENT, etc.)

### 4. Assessment & Universe Panel
**Purpose**: Strategy assessment output and universe membership

**Data Sources**:
- `/api/status/assessment?strategy_id={strategy_id}`
- `/api/status/universe?strategy_id={strategy_id}`

**Displays**:
- Top 10 instruments by expected return
- Confidence scores
- Universe size (included vs total candidates)
- Liquidity and quality scores

**Strategy**: Uses AppState.strategy_id (default: US_CORE_LONG_EQ)

### 5. Portfolio & Risk Panel
**Purpose**: Portfolio positions and risk metrics

**Data Sources**:
- `/api/status/portfolio?portfolio_id={portfolio_id}`
- `/api/status/portfolio_risk?portfolio_id={portfolio_id}`

**Displays**:
- Top 10 positions by weight
- P&L: Today, MTD, YTD
- Risk metrics: Volatility, VaR 95%, Expected Shortfall, Max Drawdown
- Scenario P&L

**Actions**:
- Stage risk config changes (max_leverage)

**Portfolio**: Uses AppState.portfolio_id (default: MAIN)

### 6. Meta & Experiments Panel
**Purpose**: Meta-learning intelligence layer

**Data Sources**:
- `/api/intelligence/diagnostics/{strategy_id}`
- `/api/intelligence/proposals`
- `/api/intelligence/changes`

**Displays**:
- Strategy diagnostics (underperforming regimes/configs)
- Pending proposals with confidence scores
- Applied changes with before/after metrics
- Reversion actions

**Actions**:
- Generate proposals
- Approve/reject proposals
- Apply proposals (dry-run or commit)
- Revert changes

### 7. Live System Panel
**Purpose**: Real-time pipeline and DAG status

**Data Sources**:
- `/api/status/pipeline?market_id={market_id}`

**Displays**:
- Market state (SESSION, CLOSED, etc.)
- Job list with status
- Last run time
- Latency vs SLO

**Market**: Uses AppState.market_id (default: US_EQ)

### 8. ANT_HILL Panel
**Purpose**: 3D visualization of system architecture

**Data Sources**:
- `/api/scenes`
- `/api/scene/{view_id}`
- `/api/traces`

**Displays**:
- Available scenes
- Scene summary (node count, connections)
- Execution traces

**Views**: root, regime, stability, portfolio, orchestration, runtime_db, historical_db, encoders

### 9. World Map / Globe Panel
**Purpose**: Geographic exposure and country-level risk

**Data Sources**:
- `/api/geo/countries`
- `/api/geo/country/{country_code}`

**Displays**:
- Top 10 countries by absolute exposure
- Stability index per country
- Fragility risk classification
- Number of positions
- Exposure by asset class for focused country

### 10. Terminal Panel
**Purpose**: Command-line interface for control operations

**Commands**:
- `help` - Show command list
- `backtest run [strategy_id] [start_date] [end_date] [market_ids_csv]` - Submit backtest job
- `synthetic create [dataset_name] [scenario_type] [num_samples]` - Create synthetic dataset
- `dag run [market_id] [dag_name]` - Schedule DAG execution
- `config apply [engine_name] [config_key] [config_value]` - Apply config change
- `jobs list` - List active jobs
- `jobs watch [job_id]` - Watch job status

**Features**:
- Command history (up/down arrows)
- Job status tracking
- Auto-parsing of numeric values
- Integration with CommandBus

### 11. Kronos Chat Panel
**Purpose**: Natural language interface to Kronos meta-orchestrator

**Data Sources**:
- `/api/kronos/chat`

**Features**:
- Ask questions about performance, regimes, configs
- Receive answers with context
- View proposed configuration changes
- Full conversation history

**Example Questions**:
- "Why did we de-risk US banks last week?"
- "Which configs underperform in crisis regimes?"
- "Propose safer Assessment configs for MAIN."

## Workspaces

Workspaces are predefined collections of panels for different workflows:

### Overview Workspace
Panels: Overview, Regime & STAB, Live System
- Quick system health check
- Current market regime
- Pipeline status

### Trading Workspace
Panels: Portfolio & Risk, Soft Targets & Fragility, Terminal
- Active trading operations
- Risk monitoring
- Command execution

### Research Workspace
Panels: Assessment & Universe, Meta & Experiments, ANT_HILL
- Strategy analysis
- Meta-learning insights
- System architecture visualization

### Monitoring Workspace
Panels: Live System, Regime & STAB, Portfolio & Risk, World Map
- Comprehensive system health
- Multi-region monitoring
- Geographic exposure

### Global Workspace
Panels: World Map, Regime & STAB, Soft Targets & Fragility
- International markets
- Cross-region regime analysis
- Global fragility assessment

## Multi-Window Support

Any panel can be detached into its own window:

1. Click the ↗ button next to the panel name in the left nav
2. The panel opens in a new window (1280x720, centered)
3. Close the window to reattach the panel

**Use Cases**:
- Multi-monitor setups
- Simultaneous monitoring of multiple markets
- Keep alerts visible while working in other panels

## Data Flow

### Backend Requirements
The UI requires a running Prometheus backend server at `http://localhost:8000`. The backend provides:

- **Monitoring APIs** (`/api/status/*`): Real-time system status
- **Visualization APIs** (`/api/scenes`, `/api/traces`): 3D scene data
- **Control APIs** (`/api/control/*`): Job submission
- **Intelligence APIs** (`/api/intelligence/*`): Meta-learning
- **Geo APIs** (`/api/geo/*`): Geographic data
- **Kronos API** (`/api/kronos/chat`): Natural language interface

### Data Population
Most APIs return empty data until backtests or live trading populate the database. To populate:

1. Run backtest: `backtest run US_CORE_LONG_EQ 2023-01-01 2024-01-01 US_EQ`
2. Wait for completion
3. Refresh panels to see data

### Database Tables
- `regimes`: Regime detection history
- `stability_vectors`: Entity-level stability scores
- `fragility_measures`: Fragility assessments
- `soft_target_classes`: Soft target classifications
- `instrument_scores`: Assessment output
- `universe_members`: Universe membership
- `target_portfolios`: Portfolio targets
- `portfolio_risk_reports`: Risk metrics
- `meta_config_proposals`: Configuration proposals
- `config_change_log`: Applied changes

## Configuration

### AppState Globals
- `mode`: PAPER, LIVE, BACKTEST
- `active_workspace`: Current workspace name
- `active_panel`: Current panel ID
- `strategy_id`: Default strategy (US_CORE_LONG_EQ)
- `portfolio_id`: Default portfolio (MAIN)
- `market_id`: Default market (US_EQ)

### API Base URL
Default: `http://localhost:8000`
Change in `prometheus_c2/src/net/ApiClient.gd`:
```gdscript
const API_BASE_URL: String = "http://localhost:8000"
```

### Theme
UI uses `res://src/themes/TerminalTheme.tres` for consistent Bloomberg-style terminal aesthetic.

## Keyboard Shortcuts
*(To be implemented)*
- `Ctrl+R`: Refresh active panel
- `Ctrl+T`: Open Terminal panel
- `Ctrl+K`: Open Kronos Chat panel
- `Ctrl+W`: Close detached window
- `Ctrl+Tab`: Cycle through panels
- `Ctrl+1-5`: Switch workspaces

## Troubleshooting

### Backend Connection Failed
**Symptom**: All panels show "Error loading: HTTP 0" or "Connection refused"
**Solution**: 
1. Start backend server: `cd prometheus && uvicorn monitoring.server:app --reload`
2. Verify http://localhost:8000/docs is accessible
3. Check firewall settings

### Empty Panel Data
**Symptom**: Panels load but show "no data" or empty lists
**Solution**: Run a backtest to populate the database

### Slow Panel Load
**Symptom**: Panels take >5 seconds to load
**Solution**: 
1. Check backend logs for slow queries
2. Verify database indexes exist
3. Reduce date range for historical queries

### Detached Window Crashes
**Symptom**: Detached panel window becomes unresponsive
**Solution**: Close and reopen. Report as bug if reproducible.

### Job Submission Fails
**Symptom**: Terminal commands return "job submission failed"
**Solution**:
1. Check backend logs for errors
2. Verify job parameters are valid
3. Ensure database is writable

## Performance Tips

1. **Limit Panel Updates**: Only refresh panels when visible
2. **Use Workspaces**: Switch workspaces instead of individual panels
3. **Detach Heavy Panels**: Move resource-intensive panels to separate windows
4. **Close Unused Windows**: Minimize number of detached panels
5. **Reduce KPI Refresh Rate**: Increase `KPI_REFRESH_INTERVAL` in MainShell.gd

## Next Steps

After familiarizing yourself with the UI:

1. Run your first backtest
2. Generate configuration proposals
3. Monitor live pipeline execution
4. Explore ANT_HILL visualizations
5. Chat with Kronos about system behavior

## Support

For issues, questions, or feature requests, consult:
- Code: `/home/feanor/coding_projects/prometheus_v2/prometheus_c2/`
- Backend API docs: http://localhost:8000/docs
- Meta/Kronos docs: `docs/META_KRONOS_INTELLIGENCE.md`
