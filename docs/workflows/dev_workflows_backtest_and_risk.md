# Dev Workflow – Backtest Campaigns with Risk On/Off

This document describes a practical workflow for comparing sleeve backtests
with and without the Risk Management Service and inspecting `risk_actions`
for debugging.

## 1. Run a campaign with Risk ON (default)

Run the backtest campaign CLI with your chosen sleeves. Example:

```bash
python -m prometheus.scripts.run_backtest_campaign \
  --market-id US_EQ \
  --start 2024-01-01 \
  --end 2024-03-31 \
  --sleeve US_EQ_CORE_21D:US_EQ_CORE_LONG_EQ:US_EQ:US_EQ_CORE_UNIVERSE:US_EQ_CORE_PORT:US_EQ_CORE_ASSESS:21 \
  --initial-cash 1000000 \
  > campaign_risk_on.csv
```

Notes:
- `--sleeve` format: `sleeve_id:strategy_id:market_id:universe_id:portfolio_id:assessment_strategy_id:assessment_horizon_days`.
- Risk is **enabled by default** (`apply_risk=True` inside the sleeve pipeline).
- The CSV output header is:
  - `run_id,sleeve_id,strategy_id,cumulative_return,annualised_sharpe,max_drawdown`.

## 2. Run the same campaign with Risk OFF

Use identical arguments plus `--disable-risk` and write to a different file:

```bash
python -m prometheus.scripts.run_backtest_campaign \
  --market-id US_EQ \
  --start 2024-01-01 \
  --end 2024-03-31 \
  --sleeve US_EQ_CORE_21D:US_EQ_CORE_LONG_EQ:US_EQ:US_EQ_CORE_UNIVERSE:US_EQ_CORE_PORT:US_EQ_CORE_ASSESS:21 \
  --initial-cash 1000000 \
  --disable-risk \
  > campaign_risk_off.csv
```

In this run:
- The sleeve pipeline uses `apply_risk=False`.
- Portfolio weights from `PortfolioEngine` go directly to target positions.
- No new rows are written into `risk_actions` for this run.

## 3. Compare the summaries

Use a simple diff on the two CSV files:

```bash
diff campaign_risk_on.csv campaign_risk_off.csv
```

Look for changes in:
- `cumulative_return`
- `annualised_sharpe`
- `max_drawdown`

For multiple sleeves (multiple `--sleeve` arguments), both files will contain
multiple rows; `diff` highlights per-sleeve differences.

## 4. Inspect `risk_actions` for a strategy

To see how the Risk Management Service modified weights in the **risk-on**
run, use the `show_risk_actions` CLI:

```bash
python -m prometheus.scripts.show_risk_actions \
  --strategy-id US_EQ_CORE_LONG_EQ \
  --limit 50
```

This prints CSV rows like:

```text
created_at,instrument_id,decision_id,action_type,original_weight,adjusted_weight,reason
2025-11-26T12:34:56.123456,AAA.US,,CAPPED,0.080000,0.050000,CAPPED_PER_NAME
2025-11-26T12:34:56.123789,BBB.US,,OK,0.020000,0.020000,OK: within per-name risk limits
```

Interpretation:
- `action_type`:
  - `CAPPED` – weight exceeded the per-name cap and was clipped.
  - `OK` – within limits, unchanged.
  - `REJECTED` – fully zeroed (if caps are effectively zero for a strategy).
- `original_weight` and `adjusted_weight` show the exact numeric
  intervention.
- `reason` is a short code/summary from the Risk Engine.

You can re-run `show_risk_actions` after a risk-off run to confirm no new
rows have been written for that `strategy_id`.

## 5. Using campaigns + Meta-Orchestrator with risk toggles

For a full campaign + meta decision:

```bash
python -m prometheus.scripts.run_campaign_and_meta \
  --strategy-id US_EQ_CORE_LONG_EQ \
  --market-id US_EQ \
  --start 2024-01-01 \
  --end 2024-03-31 \
  --top-k 3
```

- Runs the canonical core sleeves with **risk enabled**.
- Records a sleeve-selection decision into `engine_decisions`.

To run the same workflow with Risk disabled in the sleeve pipeline:

```bash
python -m prometheus.scripts.run_campaign_and_meta \
  --strategy-id US_EQ_CORE_LONG_EQ \
  --market-id US_EQ \
  --start 2024-01-01 \
  --end 2024-03-31 \
  --top-k 3 \
  --disable-risk
```

This yields a risk-off baseline for Meta-Orchestrator analysis while keeping
all code paths numeric and deterministic.
