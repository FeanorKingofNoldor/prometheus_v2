# Backtesting Engine – Detailed Plan

## 1. Purpose & Scope

Simulate trading strategies over historical or synthetic data, using the same interfaces as the live system (regime, profiles, universe, assessment, risk, execution), to evaluate performance and stress-test behaviors.


## 2. High-Level Architecture

Modules under `backtesting/`:

- `time_machine/` – trading calendar, iteration over days.
- `market_simulator/` – provides price/volume data and executes simulated orders.
- `portfolio/` – tracks positions, PnL, risk metrics.
- `engine/` – orchestrates backtest runs, wiring all services.
- `storage/` – writes `backtest_runs`, `backtest_trades`, `backtest_daily_equity`.


## 3. Data Contracts

### 3.1 Inputs

- Historical/Training DB:
  - `equity_prices_daily`
  - `corporate_actions`
  - `regime_history`
  - Universe definitions (`universe_snapshots`, `universe_members`).
  - Profiles (via Profile Service API as-of each simulated date).
- Strategy config:
  - Which strategy to simulate, parameter set, risk config.

### 3.2 Outputs – Tables

- `backtest_runs`
  - `run_id` (PK)
  - `strategy_id`
  - `config_json`
  - `start_date`, `end_date`
  - `universe_id` (if relevant)
  - `metrics_json` (final performance summary)

- `backtest_trades`
  - `run_id`, `trade_id`
  - `date`, `ticker`
  - `direction`, `size`, `price`
  - `regime_id`, `universe_id`
  - `profile_version_id`
  - `decision_metadata_json`

- `backtest_daily_equity`
  - `run_id`, `date`
  - `equity_curve_value`
  - `drawdown`, `exposure_metrics_json`


## 4. Backtest Execution Flow

1. Initialize run:
   - Load config and set up DB connections and services (Profile, Macro Regime, Universe Selection, Assessment v2, Risk, Execution simulation).
   - Generate or select `universe_snapshots` for the run.
2. Iterate over trading days:
   - Use `time_machine` to get next trading date.
   - Get regime from `regime_history`.
   - For each relevant `universe_id` on that date:
     - For each ticker in the universe:
       - Fetch company/sector profiles as-of date.
       - Fetch technicals from `equity_prices_daily`.
     - Call Assessment Engine v2 with this context to get proposed decisions.
     - Pass decisions to Risk Management, get target positions.
     - Pass target positions to `market_simulator` acting as Execution Service.
   - Update portfolio state and log trades.
3. At end of run:
   - Compute performance metrics (returns, Sharpe, drawdowns, etc.).
   - Write summaries into `backtest_runs` and equity/trade details into their tables.


## 5. Interactions with Other Players

- Uses **same API contracts** as live system:
  - `get_company_profile`, `get_sector_profile`.
  - `get_regime`.
  - `build_universe` / `get_universe`.
  - Assessment Engine v2 decisions.
  - Risk Management logic.
- Execution in backtest mode uses `market_simulator` instead of real broker.


## 6. Failure Modes & Safeguards

- If data gaps occur:
  - Alert and optionally skip those dates or names; mark in `decision_metadata_json`.
- If Assessment/Risk config is inconsistent:
  - Fail fast and mark backtest as invalid.


## 7. Current Implementation Status (Phase 6 core)

- Implemented modules under `prometheus/backtesting/`:
  - `time_machine.py` – weekday-only trading calendar between start/end dates.
  - `market_simulator.py` – loads daily close prices from `equity_prices_daily` and
    exposes a simple slippage helper for execution price adjustments.
  - `portfolio.py` – minimal long-only cash + positions model with mark-to-market
    valuation.
  - `storage.py` – helpers for inserting and fetching `backtest_runs`,
    `backtest_trades`, and `backtest_daily_equity` (JSON-like fields stored as
    JSON strings for portability).
  - `engine.py` – plugin-based engine with:
    - `EQUAL_WEIGHT_BUY_AND_HOLD` strategy (original Phase 6 core behaviour).
    - `ASSESSMENT_RISK_DAILY_REBAL` strategy that wires Assessment Engine v2
      and Risk Management for daily rebalancing.
  - `api.py` – public functions `run_backtest(config)` and
    `get_backtest_results(run_id)`.
  - `scripts/run_backtest.py` – simple CLI entrypoint using the public API.
- Tests:
  - `tests/unit/test_backtesting_imports.py` – smoke tests for public API.
  - `tests/unit/test_backtesting_storage.py` – in-memory SQLite tests covering
    storage round-trips for runs, trades, and equity rows.
- Dev workflows:
  - `dev_workflows/PHASE6_BACKTESTING.md` documents how to run backtests
    (both buy-and-hold and assessment+risk) and inspect results via the API,
    CLI, and raw SQL.


## 8. Deferred Enhancements / TODOs (later passes)

The following items are intentionally **not** part of the Phase 6 core and
should be implemented in later passes, primarily once richer historical data
and factor/attribution inputs are available:

- Execution modelling
  - Extend `market_simulator` to handle intraday bars, more detailed
    transaction cost models, and partial fills beyond the current
    close-plus-slippage assumption.
- Analytics & attribution
  - Extend `metrics_json` with deeper analytics that depend on factor data
    (e.g. beta, factor attribution, sector/decision-level attribution,
    turnover decomposition over long horizons).
  - Optionally add separate tables for factor/sector/decision-level
    attribution.
- **Scenario and tail-based diagnostics (v3/v4)**
  - Integrate Synthetic Scenario Engine (170) outputs into standard
    backtest reports so each strategy/config can be evaluated not only
    on realized history but also on scenario-based drawdown and tail
    behavior.
  - Add simple extreme-value-style summaries (e.g. empirical tail
    indices, large-deviation-style decay rates) over backtest equity
    curves to characterise how vulnerable each config is to rare but
    severe underperformance.

The following items are intentionally **not** part of the Phase 6 core and
should be implemented in later passes, primarily once richer historical data
and factor/attribution inputs are available:

- Execution modelling
  - Extend `market_simulator` to handle intraday bars, more detailed
    transaction cost models, and partial fills beyond the current
    close-plus-slippage assumption.
- Analytics & attribution
  - Extend `metrics_json` with deeper analytics that depend on factor data
    (e.g. beta, factor attribution, sector/decision-level attribution,
    turnover decomposition over long horizons).
  - Optionally add separate tables for factor/sector/decision-level
    attribution.

## Future: Episode and portfolio embedding spaces

Backtesting and analytics will later use joint embeddings for episodes
(historical crises and stress windows) and for whole portfolios, as outlined
in `docs/new_project_plan/joint_embedding_shared_spaces_plan.md`. These
spaces will support scenario selection, coverage analysis, and "distance to
historical bad states" diagnostics, while keeping execution and PnL
simulation fully numeric.
