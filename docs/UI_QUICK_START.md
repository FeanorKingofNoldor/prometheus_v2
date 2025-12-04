# Prometheus C2 UI - Quick Start Guide

## 5-Minute Setup

### 1. Start the Backend
```bash
cd /home/feanor/coding_projects/prometheus_v2
./start_prometheus.sh
```

This will:
- Check database connection
- Apply migrations if needed
- Start API server on http://localhost:8000
- Display UI launch instructions

### 2. Launch the UI
1. Open Godot 4
2. Import Project: `/home/feanor/coding_projects/prometheus_v2/prometheus_c2`
3. Run `res://src/ui/MainShell.tscn` (F5)

### 3. Explore the UI
The UI opens in Overview panel showing system KPIs. Navigate using:
- **Left sidebar**: Click panel names
- **Detach button (↗)**: Open panel in new window
- **Top bar**: View P&L, stability, leverage

## First Backtest

### Via Terminal Panel
1. Click "Terminal" in left nav
2. Type: `backtest run US_CORE_LONG_EQ 2023-01-01 2024-01-01 US_EQ`
3. Wait for job completion message
4. Refresh panels to see data

### Via Python Script
```bash
cd /home/feanor/coding_projects/prometheus_v2/prometheus
python scripts/demo_backtest.py
```

### Via REST API
```bash
curl -X POST http://localhost:8000/api/control/run_backtest \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_id": "US_CORE_LONG_EQ",
    "start_date": "2023-01-01",
    "end_date": "2024-01-01",
    "market_ids": ["US_EQ"]
  }'
```

## Panel Cheat Sheet

| Panel | Purpose | Key Data |
|-------|---------|----------|
| Overview | System dashboard | P&L, exposure, regimes, alerts |
| Regime & STAB | Market conditions | Regime label, stability index |
| Fragility | Vulnerable entities | Soft target score, fragility class |
| Assessment | Alpha generation | Expected returns, confidence |
| Portfolio | Positions & risk | Weights, VaR, scenarios |
| Meta | Intelligence layer | Diagnostics, proposals, changes |
| Live System | Pipeline status | Job states, latency, SLO |
| ANT_HILL | 3D visualization | System architecture |
| Geo | Geographic view | Country exposure, stability |
| Terminal | Command interface | Run backtests, config changes |
| Kronos Chat | NL interface | Ask questions, get insights |

## Terminal Commands

```bash
# Run backtest
backtest run [strategy_id] [start_date] [end_date] [markets]

# Create synthetic data
synthetic create [name] [scenario_type] [num_samples]

# Schedule DAG
dag run [market_id] [dag_name]

# Apply config
config apply [engine] [key] [value]

# List jobs
jobs list

# Watch job
jobs watch [job_id]

# Help
help
```

## Common Workflows

### 1. Daily Monitoring
1. Open **Overview** workspace
2. Check P&L and alerts
3. Review **Regime & STAB** for market conditions
4. Check **Live System** for pipeline health

### 2. Risk Review
1. Open **Trading** workspace
2. **Portfolio & Risk** panel: Check positions and risk metrics
3. **Fragility** panel: Identify vulnerable holdings
4. **Terminal**: Apply risk config changes if needed

### 3. Research & Analysis
1. Open **Research** workspace
2. **Assessment & Universe** panel: Review alpha signals
3. **Meta & Experiments** panel: Generate improvement proposals
4. **ANT_HILL** panel: Visualize system architecture

### 4. Configuration Changes
Via Meta Panel:
1. Generate diagnostics for strategy
2. Generate proposals (auto or manual)
3. Review confidence scores
4. Approve proposals
5. Apply (dry-run first)

Via Terminal:
```bash
config apply risk max_leverage 2.0
```

### 5. Backtest Analysis
1. Run backtest via Terminal
2. Wait for completion
3. **Meta** panel: Generate diagnostics
4. **Portfolio** panel: Review risk metrics
5. **Geo** panel: Check geographic exposure

## Multi-Window Tips

**Detach Panels for Multi-Monitor Setup:**
- Alerts → Monitor 1 (always visible)
- Overview → Monitor 1 (main dashboard)
- Regime & STAB → Monitor 2 (market context)
- Portfolio & Risk → Monitor 2 (positions)
- Terminal → Monitor 3 (command execution)

**How to Detach:**
1. Click ↗ next to panel name in left nav
2. Panel opens in new window
3. Close window to reattach

## API Endpoints (For Reference)

### Monitoring
- `GET /api/status/overview` - System KPIs
- `GET /api/status/regime?region=US` - Regime status
- `GET /api/status/stability?region=US` - Stability metrics
- `GET /api/status/fragility?region=GLOBAL` - Fragility entities
- `GET /api/status/assessment?strategy_id=X` - Assessment output
- `GET /api/status/universe?strategy_id=X` - Universe members
- `GET /api/status/portfolio?portfolio_id=X` - Portfolio positions
- `GET /api/status/portfolio_risk?portfolio_id=X` - Risk metrics
- `GET /api/status/pipeline?market_id=X` - Pipeline status

### Visualization
- `GET /api/scenes` - Available 3D scenes
- `GET /api/scene/{view_id}` - Scene graph data
- `GET /api/traces` - Execution traces

### Control
- `POST /api/control/run_backtest` - Submit backtest
- `POST /api/control/create_synthetic_dataset` - Create synthetic data
- `POST /api/control/schedule_dag` - Schedule DAG
- `POST /api/control/apply_config_change` - Apply config

### Intelligence
- `GET /api/intelligence/diagnostics/{strategy_id}` - Diagnostics
- `POST /api/intelligence/proposals/generate/{strategy_id}` - Generate proposals
- `GET /api/intelligence/proposals` - List proposals
- `POST /api/intelligence/proposals/{id}/approve` - Approve proposal
- `POST /api/intelligence/proposals/{id}/apply` - Apply proposal
- `GET /api/intelligence/changes` - List applied changes
- `POST /api/intelligence/changes/{id}/revert` - Revert change

### Geo
- `GET /api/geo/countries` - Country list
- `GET /api/geo/country/{code}` - Country detail

### Kronos
- `POST /api/kronos/chat` - Chat with Kronos

Full API docs: http://localhost:8000/docs

## Troubleshooting

**Backend won't start:**
```bash
# Check databases exist
psql -l | grep prometheus

# Check migrations
cd prometheus && python -m core.migrations.apply_all
```

**UI shows connection errors:**
```bash
# Verify backend is running
curl http://localhost:8000/api/status/overview

# Check firewall
sudo ufw status
```

**Empty panel data:**
- Run a backtest first to populate database
- Check panel's data source in console log
- Verify strategy_id/portfolio_id/market_id in AppState

**Godot import errors:**
- Ensure Godot 4.x (not 3.x)
- Reimport all files: Project → Tools → Reimport

## Next Steps

1. **Read full guide**: `docs/UI_USER_GUIDE.md`
2. **Explore Meta/Kronos**: `docs/META_KRONOS_INTELLIGENCE.md`
3. **Run demo scripts**: `prometheus/scripts/demo_*.py`
4. **Try Kronos Chat**: Ask "Why did we de-risk US banks last week?"
5. **Generate proposals**: Meta panel → "Generate Proposals"
6. **Detach panels**: Setup multi-monitor workspace

## Support

- UI Code: `prometheus_c2/src/`
- Backend Code: `prometheus/`
- Issues: File in project tracker
- Questions: Check docs or ask Kronos Chat panel
