# Dev Workflow – IBKR Execution with Software Risk Wrapper

This workflow shows how to run IBKR PAPER/LIVE execution through the
software `RiskCheckingBroker` wrapper, using environment-driven limits
and the `show_execution_risk` CLI.

It is safe to follow in a dev/test environment when pointed at the IBKR
paper account.

## 1. Pre-requisites

- IBKR Gateway/TWS running (PAPER for dev).
- `ib_insync` installed in your virtualenv.
- Migrations applied up to at least:
  - `0020_execution_core` (orders, fills, positions_snapshots).
- A working runtime DB and historical DB.
- Optional but recommended: the dummy targets script for quick tests:

  ```bash
  python -m prometheus.scripts.create_dummy_ibkr_targets \
    --portfolio-id US_CORE_LONG_EQ \
    --as-of 2025-12-02
  ```

## 2. Configure IBKR PAPER environment

For paper trading (recommended for this workflow), set the IBKR env vars
as described in `docs/IBKR_QUICK_START.md`. For example:

```bash
export IBKR_PAPER_USERNAME="xubtmn245"
export IBKR_PAPER_PASSWORD="..."      # your paper password
export IBKR_PAPER_ACCOUNT="DUN807925"
```

Then start IBKR Gateway/TWS in PAPER mode and confirm the API port
matches the defaults in `prometheus/execution/ibkr_config.py`.

## 3. Configure execution risk limits via env

Execution risk limits are controlled by these environment variables:

- `EXEC_RISK_ENABLED` – master switch for the risk wrapper (default: `false`).
- `EXEC_RISK_MAX_ORDER_NOTIONAL` – max notional per order (account currency).
- `EXEC_RISK_MAX_POSITION_NOTIONAL` – max notional per instrument position.
- `EXEC_RISK_MAX_LEVERAGE` – max gross exposure divided by equity.

A value of `0` for a numeric limit disables that individual check.

Example conservative PAPER settings:

```bash
export EXEC_RISK_ENABLED=true
export EXEC_RISK_MAX_ORDER_NOTIONAL=5000
export EXEC_RISK_MAX_POSITION_NOTIONAL=15000
export EXEC_RISK_MAX_LEVERAGE=1.5
```

## 4. Inspect active limits with `show_execution_risk`

Use the CLI to see what Prometheus actually loaded:

```bash
python -m prometheus.scripts.show_execution_risk
```

You should see a block like:

```text
# Execution risk config (PrometheusConfig.execution_risk)
enabled=true
max_order_notional=5000.0
max_position_notional=15000.0
max_leverage=1.5

# Raw environment variables (empty means not set)
EXEC_RISK_ENABLED=true
EXEC_RISK_MAX_ORDER_NOTIONAL=5000
EXEC_RISK_MAX_POSITION_NOTIONAL=15000
EXEC_RISK_MAX_LEVERAGE=1.5
```

If `enabled=false`, the brokers created by `broker_factory` will *not* be
wrapped and no execution risk checks will run.

## 5. Run IBKR PAPER execution with risk wrapper

With IBKR Gateway running and env configured, you can drive execution
from a target portfolio using the existing CLI:

```bash
python -m prometheus.scripts.run_execution_for_portfolio \
  --portfolio-id US_CORE_LONG_EQ \
  --mode PAPER \
  --notional 10000 \
  --as-of 2025-12-02
```

Internally this will:

1. Load `target_portfolios` for `US_CORE_LONG_EQ`.
2. Infer prices (from `prices_daily` or synthetic) and compute target
   share quantities.
3. Create a `PaperBroker` via `create_paper_broker`, which will be
   wrapped by `RiskCheckingBroker` if `EXEC_RISK_ENABLED=true`.
4. Plan order deltas and submit them to IBKR via `IbkrClientImpl`.

If an order violates a configured limit, `RiskCheckingBroker` will:

- Log an error with the reason.
- Raise a `RiskLimitExceeded` exception before the order reaches IBKR.

This will cause the CLI to exit with a stack trace that includes the
reason string (e.g. max order notional exceeded).

## 6. Adjusting limits and kill-style behaviour

To *tighten* or *loosen* limits, change the env vars and restart the
process managing execution (e.g. systemd service or your dev shell):

```bash
export EXEC_RISK_MAX_ORDER_NOTIONAL=2000   # tighter per-order cap
export EXEC_RISK_MAX_POSITION_NOTIONAL=8000
export EXEC_RISK_MAX_LEVERAGE=1.2

# restart whatever process runs Prometheus execution
```

To effectively **turn off** the execution risk wrapper for dev
experiments, set:

```bash
export EXEC_RISK_ENABLED=false
```

New brokers created via `create_live_broker` / `create_paper_broker`
will then talk directly to IBKR without software limits.

For production you should keep `EXEC_RISK_ENABLED=true` and choose
limits appropriate to your account size and strategy turnover.

## 7. Operator CLI cheatsheet

For day-to-day inspection and debugging, the following CLIs are useful:

- Recent orders for a portfolio:

  ```bash
  python -m prometheus.scripts.show_orders \
    --portfolio-id US_CORE_LONG_EQ \
    --mode PAPER \
    --limit 50
  ```

- Recent fills for a portfolio (joins via orders):

  ```bash
  python -m prometheus.scripts.show_fills \
    --portfolio-id US_CORE_LONG_EQ \
    --mode PAPER \
    --limit 50
  ```

- Latest positions snapshots written by the execution bridge:

  ```bash
  python -m prometheus.scripts.show_positions_snapshots \
    --portfolio-id US_CORE_LONG_EQ \
    --mode PAPER \
    --limit 100
  ```

- Combined execution status (orders + fills + latest positions):

  ```bash
  python -m prometheus.scripts.show_execution_status \
    --portfolio-id US_CORE_LONG_EQ \
    --mode PAPER \
    --limit-orders 25 \
    --limit-fills 25
  ```

- Recent risk actions from the Risk Management Service:

  ```bash
  python -m prometheus.scripts.show_risk_actions \
    --strategy-id US_CORE_LONG_EQ \
    --limit 50
  ```

- Current execution risk limits (software risk wrapper):

  ```bash
  python -m prometheus.scripts.show_execution_risk
  ```

These scripts are safe to run in production; they are read-only and only
query the runtime DB or configuration.

## 8. Quick checklist before running LIVE

Before switching `--mode LIVE` in any execution CLI:

1. Confirm IBKR LIVE credentials and connection via the existing
   IBKR test script.
2. Set and verify execution risk env vars:

   ```bash
   python -m prometheus.scripts.show_execution_risk
   ```

3. Run at least one PAPER dry run on the same portfolio and notional.
4. Only then switch to LIVE with `readonly=False` in your deployment
   configuration.

Keeping this workflow nearby ensures you do not forget to
(1) enable the risk wrapper and (2) verify its limits before any
live-capable run.