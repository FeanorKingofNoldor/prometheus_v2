# Execution Service – Detailed Plan

## 1. Purpose & Scope

Translate target positions from Risk Management into concrete orders, then send them either to:
- Real brokers (e.g. IBKR) in PRODUCTION mode.
- Market simulator (Backtesting Engine) in TRAINING mode.

Track order lifecycle and trade fills.


## 2. High-Level Architecture

Modules under `execution/`:

- `order_planner/` – compute order lists from target vs current positions.
- `broker_adapters/` – broker-specific clients (IBKR, others).
- `simulated_execution/` – backtest execution adapter.
- `router/` – routes orders to appropriate adapter based on mode.
- `storage/` – writes `trades` and execution logs.


## 3. Data Contracts

### 3.1 Inputs

- Final target positions from Risk Management.
- Current positions from runtime DB.
- Broker configuration:
  - Account identifiers, host/port, allowed order types.
- Market data (for backtest / slippage models):
  - Price/volume data from historical DB.

### 3.2 Outputs – Tables

- `trades` (runtime DB):
  - `trade_id` (PK)
  - `timestamp`
  - `ticker`
  - `direction` (BUY/SELL)
  - `size`
  - `price`
  - `order_id`
  - `strategy_id`
  - `profile_version_id`
  - `regime_id`
  - `universe_id`
  - `decision_id` (FK to pipeline_decisions)

- Order/execution logs (table or log stream for debugging).


## 4. Order Planning & Routing Flow

1. Load current positions for all tickers.
2. For each ticker:
   - Compute `delta_position = target_position - current_position`.
   - Translate into one or more orders (consider minimal order size, rounding, etc.).
3. In PRODUCTION mode:
   - Use `broker_adapters` (e.g. IBKR) to submit/modify/cancel orders.
   - Track order status updates.
   - On fills, create `trades` records.
4. In TRAINING mode:
   - Use `simulated_execution` to generate fills based on historical prices and slippage models.
   - Write `trades` records into training or runtime DB as appropriate.


## 5. Interactions with Other Players

- **Risk Management**:
  - Receives target positions.
- **Backtesting Engine**:
  - Execution Service in TRAINING mode calls into `market_simulator`.
- **Meta Orchestrator**:
  - Uses trades and execution stats for performance analysis.
- **Black Swan Engine**:
  - May instruct Execution to adjust order aggressiveness under EMERGENCY.


## 6. Failure Modes & Safeguards

- Broker down or connection errors:
  - Stop sending new orders.
  - Alert and log.
- Partial failures (some orders rejected):
  - Mark affected trades and notify Risk & Assessment.


## 7. Current Implementation Status (Execution core)

- Implemented modules under `prometheus/execution/`:
  - `order_planner.py` – maps target weights to high-level `PlannedOrder`
    objects (`OPEN_LONG`, `OPEN_SHORT`, `CLOSE`).
  - `router.py` – routes planned orders to either simulated execution
    (TRAINING) or the IBKR adapter (PRODUCTION).
  - `simulated_execution.py` – placeholder for TRAINING-mode execution (no
    side effects yet).
  - `broker_adapters/ibkr_adapter.py` – scaffolding for IBKR connectivity;
    currently raises `NotImplementedError`.
  - `storage.py` – helper to insert trades into the runtime `trades` table.
  - `api.py` – exposes `apply_execution_plan(target_positions, mode)` to plan
    and route orders.
- Tests:
  - `tests/unit/test_execution_imports.py` – smoke test for the execution API.
  - `tests/unit/test_execution_storage_and_planner.py` – in-memory SQLite
    tests for `plan_orders_from_targets` and `record_trades`.
- Dev workflows:
  - `dev_workflows/PHASE9_EXECUTION.md` documents how to plan orders from
    targets and how to record trades.


## 8. Deferred Enhancements / TODOs (later passes)

The following items are intentionally **not** part of the current execution
core and should be implemented in later passes:

- Real broker integrations
  - Implement robust adapters for IBKR and other brokers, including
    connectivity management, error handling, and reconciling order states.
- Simulated execution & backtesting integration
  - Integrate `simulated_execution` with the Backtesting Engine's
    `market_simulator` to generate realistic fills, slippage, and partial
    executions.
- Positions and cash handling
  - Update the `positions` table and cash balances as trades occur, ensuring
    consistency with backtesting portfolio models.
- Detailed order modelling
  - Support limit/stop orders, time-in-force policies, and routing
    preferences.
- Observability and monitoring
  - Add structured logs and metrics around order submission, latency,
    rejection rates, and fill quality.
