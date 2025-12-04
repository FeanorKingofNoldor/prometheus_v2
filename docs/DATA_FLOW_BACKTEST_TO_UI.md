# Prometheus v2 - Data Flow: Backtest to UI

## Overview

This document explains how data flows from backtest execution through the mock broker into the database, and how the monitoring UI reads and displays that data.

## Complete Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                      BACKTEST EXECUTION                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ BacktestRunner (prometheus/backtest/runner.py)                  │
│  • Orchestrates backtest over date range                        │
│  • Calls target_positions_fn for each date                      │
│  • Uses BacktestBroker for order execution                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ apply_execution_plan (prometheus/execution/api.py)              │
│  • Computes orders from current vs target positions             │
│  • Submits orders to broker                                     │
│  • Processes fills (BACKTEST mode)                              │
│  • Records everything to database                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ BacktestBroker (prometheus/execution/backtest_broker.py)        │
│  • BrokerInterface implementation for BACKTEST mode             │
│  • Stores orders in memory                                      │
│  • Delegates to MarketSimulator for pricing                     │
│  • process_fills() generates Fill objects                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ MarketSimulator + TimeMachine                                   │
│  • Simulates market using historical data                       │
│  • Computes fills at historical prices                          │
│  • Manages position book                                        │
│  • Tracks P&L and equity                                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Database Storage (prometheus/execution/storage.py)              │
│  • record_orders() → orders table                               │
│  • record_fills() → fills table                                 │
│  • record_positions_snapshot() → positions_snapshots table      │
│  • All in runtime database                                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Backtest Specific Storage                                       │
│  • backtest_runs → run metadata, metrics                        │
│  • backtest_trades → per-trade records                          │
│  • backtest_daily_equity → equity curve                         │
│  • executed_actions → unified execution log                     │
│  • engine_decisions/decision_outcomes → meta tracking           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Portfolio/Risk Reports Generation                               │
│  • target_portfolios → target weights                           │
│  • portfolio_risk_reports → risk metrics, VaR, scenarios        │
│  • Computed by portfolio engine during backtest                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   MONITORING APIs                                │
│ (prometheus/monitoring/api.py)                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
    ┌───────────────────┬─────────────────┬──────────────────┐
    │ /api/status/*     │ /api/control/*  │ /api/intelligence│
    │ • overview        │ • run_backtest  │ • diagnostics    │
    │ • portfolio       │ • jobs          │ • proposals      │
    │ • portfolio_risk  │                 │                  │
    └───────────────────┴─────────────────┴──────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   PROMETHEUS C2 UI (Godot)                       │
│ • Overview Panel: P&L, exposure from portfolio_risk_reports     │
│ • Portfolio Panel: positions from positions_snapshots           │
│ • Portfolio Risk Panel: metrics from portfolio_risk_reports     │
│ • Terminal Panel: submit backtests via /api/control/*           │
│ • Meta Panel: diagnostics/proposals via /api/intelligence/*     │
└─────────────────────────────────────────────────────────────────┘
```

## Detailed Component Breakdown

### 1. Backtest Execution Layer

#### BacktestRunner
**File**: `prometheus/backtest/runner.py`

**Responsibilities**:
- Orchestrates backtest over date range
- For each trading day:
  1. Calls `target_positions_fn(date)` to get desired positions
  2. Calls `apply_execution_plan()` to execute
  3. Records equity curve point
  4. Stores fills as trades

**Key Data Written**:
- `backtest_runs` table: run metadata, final metrics
- `backtest_daily_equity` table: equity curve
- `backtest_trades` table: individual trades
- `engine_decisions` table: meta-level decision tracking

#### apply_execution_plan()
**File**: `prometheus/execution/api.py`

**Flow**:
1. Get current positions from broker
2. Compute orders needed (plan_orders)
3. Submit orders to broker
4. In BACKTEST mode: call `broker.process_fills(date)`
5. Record orders, fills, positions to database

**Key Data Written**:
- `orders` table: all submitted orders
- `fills` table: all executions
- `positions_snapshots` table: positions after execution
- `executed_actions` table: unified execution log

### 2. Mock Broker Layer

#### BacktestBroker
**File**: `prometheus/execution/backtest_broker.py`

**Interface**: Implements `BrokerInterface`

**Methods**:
- `submit_order(order)` → stores order in memory, returns order_id
- `get_positions()` → returns current holdings from simulator
- `get_account_state()` → returns equity, cash, etc
- `process_fills(date)` → **BACKTEST SPECIFIC**: generates fills for date

**Flow**:
1. Orders stored in `_orders` dict in memory
2. `process_fills()` called at EOD
3. Delegates to MarketSimulator to price orders
4. Generates Fill objects
5. Updates order status to FILLED

**Key Feature**: Synchronous execution - all fills generated immediately when `process_fills()` is called. No async waiting.

#### MarketSimulator
**File**: `prometheus/execution/market_simulator.py`

**Responsibilities**:
- Maintains position book
- Prices orders using historical data (via TimeMachine)
- Computes P&L and equity
- Generates Fill objects with realistic prices

**Pricing**:
- Uses close prices from historical database
- Applies commission model
- Simulates slippage (optional)

#### TimeMachine
**File**: `prometheus/execution/time_machine.py`

**Responsibilities**:
- Iterates through historical trading days
- Provides price data for each date
- Time-travels through historical data

### 3. Database Storage

#### Runtime Database Tables

**orders**:
```sql
order_id, timestamp, instrument_id, side, order_type, quantity, 
limit_price, stop_price, status, mode, portfolio_id, decision_id, metadata
```
- Records every order submitted
- `mode='BACKTEST'` for backtest runs
- Links to `decision_id` for meta tracking

**fills**:
```sql
fill_id, order_id, timestamp, instrument_id, side, quantity, 
price, commission, mode, metadata
```
- Records every execution
- Price = historical close from MarketSimulator
- Commission calculated per commission model

**positions_snapshots**:
```sql
snapshot_id, portfolio_id, timestamp, as_of_date, instrument_id, 
quantity, avg_cost, market_value, unrealized_pnl, mode, metadata
```
- Point-in-time positions after execution
- One row per instrument per date
- Used by Portfolio Panel to show holdings

**portfolio_risk_reports**:
```sql
report_id, portfolio_id, as_of_date, created_at, risk_metrics, 
scenario_pnl, exposures_by_sector, exposures_by_factor, metadata
```
- Comprehensive risk metrics
- VaR, ES, volatility, drawdown
- Scenario analysis results
- Used by Portfolio Risk Panel

**target_portfolios**:
```sql
portfolio_id, as_of_date, created_at, target_positions, 
optimization_params, metadata
```
- Desired portfolio weights
- Used by Portfolio Panel to show targets

#### Backtest Specific Tables

**backtest_runs**:
```sql
run_id, sleeve_id, strategy_id, start_date, end_date, 
config_json, created_at, metrics_json
```
- One row per backtest run
- `metrics_json` contains: cumulative_return, sharpe_ratio, max_drawdown, etc.

**backtest_trades**:
```sql
run_id, trade_id, as_of_date, instrument_id, side, quantity, 
price, commission, pnl, sleeve_id, strategy_id, config_snapshot
```
- Individual trade records
- Links to fills via timestamp

**backtest_daily_equity**:
```sql
run_id, as_of_date, equity, drawdown, exposure_metrics_json
```
- Daily equity curve
- Used for charting and metrics

### 4. Monitoring API Layer

#### Status APIs (`/api/status/*`)
**File**: `prometheus/monitoring/api.py`

Queries runtime database tables to provide real-time views:

**GET /api/status/overview**:
- Aggregates from `portfolio_risk_reports`
- Latest `stability_vectors` for global stability
- Latest `regimes` for regime status
- Returns: P&L, exposure, stability, regimes, alerts

**GET /api/status/portfolio?portfolio_id=X**:
- Queries latest `target_portfolios`
- Extracts weights from `target_positions` JSONB
- Queries `portfolio_risk_reports` for exposures
- Returns: positions, P&L (placeholder), exposures

**GET /api/status/portfolio_risk?portfolio_id=X**:
- Queries latest `portfolio_risk_reports`
- Extracts `risk_metrics` JSONB
- Extracts `scenario_pnl` JSONB
- Returns: volatility, VaR, ES, max_drawdown, scenarios

#### Control APIs (`/api/control/*`)
**File**: `prometheus/monitoring/control_api.py`

**POST /api/control/run_backtest**:
- Accepts backtest parameters
- Creates job record in memory
- Returns job_id
- Job execution handled by orchestrator (not yet implemented)

Current Implementation: Jobs are tracked in `_job_registry` dict. Full orchestration (Airflow/Prefect) planned but not blocking.

#### Intelligence APIs (`/api/intelligence/*`)
**File**: `prometheus/monitoring/intelligence_api.py`

**GET /api/intelligence/diagnostics/{strategy_id}**:
- Queries `backtest_runs` filtered by strategy
- Joins with `engine_decisions` and `decision_outcomes`
- Analyzes performance by regime/config
- Returns diagnostic report

**POST /api/intelligence/proposals/generate/{strategy_id}**:
- Runs diagnostics
- Generates configuration change proposals
- Stores in `meta_config_proposals`
- Returns proposals with confidence scores

### 5. UI Layer (Godot C2)

#### ApiClient
**File**: `prometheus_c2/src/net/ApiClient.gd`

Singleton that wraps all HTTP calls:
```gdscript
var overview = await ApiClient.get_status_overview()
var portfolio = await ApiClient.get_status_portfolio("MAIN")
var risk = await ApiClient.get_status_portfolio_risk("MAIN")
```

#### Panel Data Flow Examples

**Overview Panel**:
1. Calls `ApiClient.get_status_overview()`
2. API queries `portfolio_risk_reports` for exposure
3. API queries `stability_vectors` for stability
4. API queries `regimes` for regime status
5. Panel displays: P&L, exposure, stability, regimes

**Portfolio & Risk Panel**:
1. Calls `ApiClient.get_status_portfolio("MAIN")`
2. API queries `target_portfolios` for latest weights
3. Panel shows top 10 positions by weight
4. Calls `ApiClient.get_status_portfolio_risk("MAIN")`
5. API queries `portfolio_risk_reports` for risk metrics
6. Panel shows: volatility, VaR, ES, drawdown, scenarios

**Meta & Experiments Panel**:
1. Calls `ApiClient.get_diagnostics("US_CORE_LONG_EQ")`
2. API analyzes backtest runs, finds underperformers
3. Panel shows strategy diagnostics
4. User clicks "Generate Proposals"
5. Calls `ApiClient.generate_proposals("US_CORE_LONG_EQ")`
6. API generates config change proposals
7. Panel shows proposals with confidence scores
8. User approves and applies
9. Calls `ApiClient.apply_proposal(proposal_id)`
10. API updates `strategy_configs` table

## Data Population Flow

### Initial State (Empty Database)
```
Runtime DB: Empty tables
Historical DB: Market data loaded
UI: Shows "no data" or zeros
```

### After First Backtest
```
1. User runs: backtest run US_CORE_LONG_EQ 2023-01-01 2024-01-01 US_EQ

2. BacktestRunner executes:
   - For each trading day:
     a. Compute target positions (Assessment + Universe + Portfolio)
     b. Apply execution plan
     c. BacktestBroker.process_fills()
     d. Record orders, fills, positions
     e. Record equity point

3. Database populated:
   ✓ orders: ~250-500 orders (depending on turnover)
   ✓ fills: ~250-500 fills (assuming all filled)
   ✓ positions_snapshots: ~250 snapshots (1 per day)
   ✓ backtest_runs: 1 run with metrics
   ✓ backtest_daily_equity: ~250 equity points
   ✓ backtest_trades: ~250-500 trades
   ✓ regimes: populated by regime engine
   ✓ stability_vectors: populated by stability engine
   ✓ fragility_measures: populated by fragility engine
   ✓ instrument_scores: populated by assessment engine
   ✓ universe_members: populated by universe engine
   ✓ target_portfolios: populated by portfolio engine
   ✓ portfolio_risk_reports: populated by portfolio engine

4. UI now shows data:
   ✓ Overview: P&L, exposure, stability from backtest
   ✓ Regime & STAB: Regime history from backtest period
   ✓ Fragility: Fragile entities identified during backtest
   ✓ Assessment: Instrument scores from assessment engine
   ✓ Portfolio: Positions from last backtest day
   ✓ Portfolio Risk: Risk metrics computed during backtest
   ✓ Meta: Can generate diagnostics and proposals
```

## Mode Comparison

### BACKTEST Mode
- **Broker**: BacktestBroker
- **Execution**: Synchronous via `process_fills(date)`
- **Pricing**: Historical close prices
- **Data**: Written to runtime DB with `mode='BACKTEST'`
- **Speed**: Fast (no network calls)
- **Use Case**: Strategy research, config optimization

### PAPER Mode (Future)
- **Broker**: PaperBroker
- **Execution**: Async via IBKR Paper API
- **Pricing**: Live market prices (paper account)
- **Data**: Written to runtime DB with `mode='PAPER'`
- **Speed**: Real-time latency
- **Use Case**: Pre-production testing

### LIVE Mode (Future)
- **Broker**: LiveBroker
- **Execution**: Async via IBKR Live API
- **Pricing**: Live market prices (real account)
- **Data**: Written to runtime DB with `mode='LIVE'`
- **Speed**: Real-time latency
- **Use Case**: Production trading

**Key Insight**: All three modes use the same `BrokerInterface` and write to the same database tables (distinguished by `mode` column). The UI reads from the same tables regardless of mode.

## Key Insights

### 1. Mock Broker ≠ Separate Process
The BacktestBroker is **not** a separate service or process. It's a Python class that:
- Implements BrokerInterface
- Runs in the same process as the backtest
- Stores orders in memory
- Delegates pricing to MarketSimulator
- Generates fills synchronously

### 2. Database is the Bridge
The monitoring UI **does not** connect directly to the broker. Instead:
- Backtest writes data to PostgreSQL runtime DB
- Monitoring APIs read from runtime DB
- UI polls APIs via HTTP
- Clean separation of concerns

### 3. No Real-Time Updates During Backtest
When a backtest is running:
- Data written to DB as backtest progresses
- UI must refresh panels to see updates
- No push notifications (yet)
- Manual refresh or auto-refresh every 10s

### 4. Job Tracking is Decoupled
When you submit a backtest via Terminal:
- POST /api/control/run_backtest creates job record
- Returns job_id immediately
- Actual backtest execution delegated to orchestrator
- UI polls GET /api/control/jobs/{job_id} for status
- Currently: orchestrator not implemented, jobs stay PENDING

### 5. Meta Layer Reads Backtest Results
Intelligence APIs analyze historical backtest data:
- Queries `backtest_runs` for performance
- Joins with `engine_decisions` for configs
- Computes diagnostics (Sharpe, drawdown by regime/config)
- Generates proposals for improvement
- Stores in `meta_config_proposals`
- UI displays via Meta & Experiments Panel

## Testing the Flow

### Step 1: Run Backtest
```python
# prometheus/scripts/demo_backtest.py
from prometheus.backtest.campaign import run_sleeve_backtest

run_id = run_sleeve_backtest(
    strategy_id="US_CORE_LONG_EQ",
    start_date=date(2023, 1, 1),
    end_date=date(2024, 1, 1),
    market_ids=["US_EQ"],
)
print(f"Backtest complete: {run_id}")
```

### Step 2: Verify Database
```sql
-- Check backtest run
SELECT run_id, strategy_id, start_date, end_date, metrics_json
FROM backtest_runs
ORDER BY created_at DESC
LIMIT 1;

-- Check equity curve
SELECT COUNT(*) FROM backtest_daily_equity WHERE run_id = '...';

-- Check orders/fills
SELECT COUNT(*) FROM orders WHERE mode = 'BACKTEST';
SELECT COUNT(*) FROM fills WHERE mode = 'BACKTEST';

-- Check positions
SELECT COUNT(*) FROM positions_snapshots WHERE mode = 'BACKTEST';

-- Check risk reports
SELECT COUNT(*) FROM portfolio_risk_reports;
```

### Step 3: Test Monitoring APIs
```bash
# Overview
curl http://localhost:8000/api/status/overview

# Portfolio
curl http://localhost:8000/api/status/portfolio?portfolio_id=MAIN

# Portfolio Risk
curl http://localhost:8000/api/status/portfolio_risk?portfolio_id=MAIN

# Diagnostics
curl http://localhost:8000/api/intelligence/diagnostics/US_CORE_LONG_EQ
```

### Step 4: View in UI
1. Launch Godot UI (F5)
2. Overview Panel: Should show exposure, stability
3. Portfolio Panel: Should show positions
4. Portfolio Risk Panel: Should show risk metrics
5. Meta Panel: Click "Generate Diagnostics"

## Common Issues

### Q: UI shows "no data"
**A**: Run a backtest first to populate database.

### Q: Portfolio Panel shows empty positions
**A**: Check `positions_snapshots` table has data with your portfolio_id.

### Q: Risk metrics all zero
**A**: Check `portfolio_risk_reports` table exists and has recent data.

### Q: Can't submit backtest via Terminal
**A**: Check backend is running (http://localhost:8000/docs). Job orchestration not yet implemented, jobs will stay PENDING.

### Q: Meta diagnostics return empty
**A**: Need at least one backtest run with `strategy_id` matching your query.

## Future Enhancements

### Real-Time Updates
- WebSocket connection for live updates
- Push notifications when backtest completes
- Live streaming of equity curve during backtest

### Job Orchestration
- Airflow/Prefect integration
- Actual backtest execution from UI
- Progress tracking (%)
- Cancel/pause functionality

### Live/Paper Trading
- Connect PaperBroker to IBKR Paper API
- Same database schema, `mode='PAPER'`
- Real-time fills
- UI shows live positions

### Historical Analysis
- Time-travel UI to view past states
- Replay backtests
- Compare multiple runs side-by-side

---

**Summary**: The backtest engine uses BacktestBroker (a mock broker) to simulate execution using historical data. All orders, fills, and positions are written to the PostgreSQL runtime database. The monitoring UI reads from these same tables via REST APIs. The broker is not a separate process - it's a Python class that runs in the backtest process. The database is the bridge between backtest execution and UI monitoring.
