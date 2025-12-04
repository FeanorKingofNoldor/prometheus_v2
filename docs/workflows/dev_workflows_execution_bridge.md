# Dev Workflow – Execution Bridge and Backtest Orders/Fills

This workflow shows how to run a simple sleeve-level backtest that routes
through the unified execution bridge and persists orders, fills, and
positions snapshots in BACKTEST mode.

The goal is to make sure the same `apply_execution_plan` helper can be
used later for PAPER and LIVE execution with different broker
implementations while keeping the Portfolio & Risk logic unchanged.

## 1. Pre-requisites

- Migrations applied up to at least revision `0020` so that the runtime
  DB has the following tables:
  - `orders`
  - `fills`
  - `positions_snapshots`
- The historical DB populated with prices for the instruments you plan
  to backtest.

## 2. Run a sleeve-level backtest

Use the existing integration-style workflow from
`tests/integration/test_iter_sleeve_backtest_engine.py` as a reference.
In a dev environment you can run it directly (note that it is marked as
an integration test and may be deselected by default):

```bash
pytest tests/integration/test_iter_sleeve_backtest_engine.py -m integration
```

This test:

- Writes synthetic prices for two instruments into `prices_daily`.
- Constructs a `TimeMachine`, `MarketSimulator`, and `BacktestBroker`.
- Builds a simple constant target positions function.
- Runs `BacktestRunner.run_sleeve(...)` over a short window of dates.

Under the hood, `BacktestRunner` now calls
`prometheus.execution.api.apply_execution_plan` on each backtest date.

## 3. What the execution bridge does

The core helper is `apply_execution_plan`:

- Computes required orders from current vs target positions using
  `order_planner.plan_orders`.
- Submits those orders to the provided `BrokerInterface` implementation.
- In BACKTEST mode with a `BacktestBroker`, calls
  `BacktestBroker.process_fills(as_of_date)` to generate simulated fills.
- Persists orders and fills into the runtime DB via
  `prometheus.execution.storage.record_orders` and
  `prometheus.execution.storage.record_fills`.
- Optionally writes a positions snapshot into `positions_snapshots` via
  `record_positions_snapshot`.

This flow is intentionally mode-agnostic. To move from BACKTEST to PAPER
or LIVE, you inject a different `BrokerInterface` implementation and
pass the appropriate execution `mode` while keeping the rest of the
pipeline identical.

## 4. Inspecting orders, fills, and positions snapshots

After running a sleeve backtest you can inspect the execution tables in
psql or any SQL client connected to the runtime DB. For example:

- Show recent orders:

  ```sql
  SELECT timestamp,
         portfolio_id,
         instrument_id,
         side,
         order_type,
         quantity,
         status,
         mode
  FROM orders
  ORDER BY timestamp DESC
  LIMIT 50;
  ```

- Show recent fills:

  ```sql
  SELECT timestamp,
         instrument_id,
         side,
         quantity,
         price,
         mode
  FROM fills
  ORDER BY timestamp DESC
  LIMIT 50;
  ```

- Show latest positions snapshots for a portfolio:

  ```sql
  SELECT portfolio_id,
         as_of_date,
         instrument_id,
         quantity,
         avg_cost,
         market_value,
         unrealized_pnl,
         mode
  FROM positions_snapshots
  WHERE portfolio_id = 'TEST_PORTFOLIO'
  ORDER BY timestamp DESC,
           instrument_id
  LIMIT 100;
  ```

In early development it is useful to wrap these queries into small
helper scripts (e.g. `scripts/show_orders.py`) but the raw SQL above is
sufficient to validate that the execution bridge is wiring through as
expected.

## 5. Next steps

Once the BACKTEST execution flow is stable, the next incremental steps
are:

1. Implement a `PaperBroker` that talks to the broker's paper-trading
   endpoint but still uses `apply_execution_plan`.
2. Implement a `LiveBroker` that connects to the live account, reusing
   the same interface.
3. Extend the Meta-Orchestrator to read from `orders`, `fills`, and
   `positions_snapshots` (or from a derived `executed_actions` view) to
   evaluate strategy execution quality across modes.
