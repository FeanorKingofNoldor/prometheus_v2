# Dev workflow: v0 training / historical backfills (Regime, STAB, Universe, λ, Scenarios)

This workflow describes how to run a **v0 historical training / backfill
campaign** over a date range for a core equity strategy, using the
existing CLIs and engines. The goal is to produce a coherent set of
artifacts that can be used for research, Meta, and later model training:

- Regime history and regime state-change risk series.
- STAB / soft-target state-change risk series.
- Baseline universes and λ-aware universes.
- λ_t(x) baseline panels and λ̂ experiments.
- Synthetic scenarios and scenario-based portfolio risk.
- Backtests and Meta evaluations that see all of the above context.

The steps below assume a US equity core strategy, but the pattern is the
same for other regions.


## 0. Global prerequisites

Before running this workflow, ensure that:

1. **Migrations are up to date**

   - Alembic has been run through at least `0014_synthetic_scenarios` so
     that `scenario_sets` and `scenario_paths` exist in the runtime DB.

2. **Historical prices are populated**

   - For US equities, you can use the existing price backfill script,
     e.g.:

     ```bash
     python -m prometheus.scripts.backfill_eodhd_us_eq \
       --start 2020-01-01 --end 2024-12-31
     ```

3. **Core IDs & date window**

   Decide on the canonical IDs and window you will use for v0 training.
   For example:

   - `REGION=US`
   - `MARKET_ID=US_EQ`
   - `STRATEGY_ID=US_EQ_CORE_LONG_EQ`
   - `UNIVERSE_ID=US_EQ_CORE_UNIVERSE` (or `CORE_EQ_US` for the generic
     universe backfills)
   - `PORTFOLIO_ID=US_EQ_CORE_PORT`
   - `ASSESSMENT_STRATEGY_ID=US_EQ_CORE_ASSESS`
   - `START=2020-01-01`, `END=2024-12-31`

4. **Universe / portfolio configs exist**

   - `MARKETS_BY_REGION` in `prometheus/pipeline/tasks.py` maps `US`
     to `["US_EQ"]`.
   - There are sleeves / configs for `STRATEGY_ID` you intend to
     backtest.

This workflow is deliberately **offline / research** focused; live
pipelines can continue to run independently.


## 1. Regime history and regime state-change risk

### 1.1 Populate regime history (if not already present)

If you do **not** already have `regimes` populated for the region/date
window, you can run the numeric regime engine in a loop or via a small
Python helper. For a quick v0 pass, a single proxy instrument per region
is sufficient (see `run_numeric_regime.py`).

Minimal example (shell loop pseudocode):

```bash
for d in $(seq 0 1825); do  # ~5 years
  ASOF=$(date -d "2020-01-01 +$d day" +%Y-%m-%d)
  python -m prometheus.scripts.run_numeric_regime \
    --region US \
    --instrument-id SPY.US \
    --as-of "$ASOF" \
    --window-days 63 \
    --model-id num-regime-core-v1 || true
done
```

In practice you may prefer a small Python script/notebook that drives the
loop using the trading calendar; the key is that `regimes` and
`regime_transitions` are populated for `[START, END]`.

### 1.2 Backfill regime state-change risk (CSV)

Once regime history exists, backfill the **regime state-change risk
series** using `backfill_regime_change_risk.py`. This produces a CSV with
horizon-step probabilities and a scalar `regime_risk_score` that can be
used as a feature in λ̂ experiments and diagnostics.

Example:

```bash
python -m prometheus.scripts.backfill_regime_change_risk \
  --region US \
  --start 2020-01-01 \
  --end 2024-12-31 \
  --horizon-steps 1 \
  --output data/regime_risk_US_20200101_20241231.csv
```

You can later pass this file into
`run_opportunity_density_experiment.py --regime-risk-csv` to expose
`regime_risk_score` as a feature.


## 2. STAB / soft-target state-change risk

This step assumes that `soft_target_classes` are already being written by
StabilityEngine (either from daily pipelines or previous research
backfills). If you do not yet have soft-target states, run the relevant
STAB scoring tasks first (e.g. via the full-day pipeline workflow).

### 2.1 Backfill STAB state-change risk (CSV)

Use `backfill_stability_change_risk.py` to turn the empirical
soft-target transition matrix into multi-step **STAB state-change risk
metrics**.

Example (per-instrument INSTRUMENT entity_type):

```bash
python -m prometheus.scripts.backfill_stability_change_risk \
  --entity-type INSTRUMENT \
  --start 2020-01-01 \
  --end 2024-12-31 \
  --horizon-steps 1 \
  --output data/stab_risk_INSTRUMENT_20200101_20241231.csv
```

You can:

- Use this CSV directly for research, and/or
- Join `stability_risk_score` / `p_worsen_any` / `p_to_targetable_or_breaker`
  into λ̂ training data by date/instrument or by aggregating per
  (market, sector, soft_target_class) cluster.

Note that the **live** Universe and backtest pipelines already consume
STAB risk via `StabilityStateChangeForecaster`; this offline CSV is for
λ̂ training and diagnostics.


## 3. Baseline universe backfill (no λ̂)

Backfill basic universes so that `universe_members` has historical
coverage over `[START, END]` independent of any one pipeline run.

Use `backfill_universes_basic.py` to build `CORE_EQ_<REGION>` universes.

Example for US:

```bash
python -m prometheus.scripts.backfill_universes_basic \
  --region US \
  --start 2020-01-01 \
  --end 2024-12-31 \
  --max-universe-size 200 \
  --min-liquidity-adv 100000 \
  --min-price 1.0
```

This populates `universe_members` for `universe_id = CORE_EQ_US` using
the same BasicUniverseModel configuration as the pipeline’s
`run_universes_for_run` task (Assessment on, STAB filters on, no λ̂
component).

These baseline universes are useful for:

- Simple backtests that do not use λ̂.
- Comparing λ̂-aware universes against a stable reference.


## 4. λ_t(x) baseline backfill

Next, compute **realised opportunity density** λ_t(x) per cluster using
`backfill_opportunity_density.py`. This is a pure research CSV pipeline
that uses `prices_daily` and current STAB class to define clusters:

- Cluster = (market_id, sector, soft_target_class).
- λ_t(x) uses cross-sectional return dispersion and realised volatility
  in each cluster.

Example for US_EQ:

```bash
python -m prometheus.scripts.backfill_opportunity_density \
  --start 2020-01-01 \
  --end 2024-12-31 \
  --market US_EQ \
  --lookback-days 20 \
  --min-cluster-size 5 \
  --output data/lambda_US_EQ_20200101_20241231.csv
```

This produces a CSV with columns like:

- `as_of_date,market_id,sector,soft_target_class,num_instruments,dispersion,avg_vol_window,lambda_value`.


## 5. λ̂ experiments (opportunity-density models)

With λ_t(x) and regime risk CSVs in place, run λ̂ experiments using
`run_opportunity_density_experiment.py`. This trains simple models
(persistence, cluster_mean, global_ar1, global_linear_full) and writes
both:

- A **results CSV** with per-experiment metrics.
- An optional **predictions CSV** with per-cluster λ̂ values, which can
  be consumed by universes.

### 5.1 Train/test experiment with regime risk features

Example: global linear model using `regime_risk_score` as an additional
feature, with λ̂ predictions written out for all test rows.

```bash
python -m prometheus.scripts.run_opportunity_density_experiment \
  --input data/lambda_US_EQ_20200101_20241231.csv \
  --output data/lambda_experiments_US_EQ.csv \
  --experiment-id US_EQ_GL_FULL_V0 \
  --model global_linear_full \
  --train-start 2020-01-01 --train-end 2022-12-31 \
  --test-start 2023-01-01 --test-end 2024-12-31 \
  --top-quantile 0.2 \
  --predictions-output data/lambda_predictions_US_EQ.csv \
  --regime-risk-csv data/regime_risk_US_20200101_20241231.csv
```

Key points:

- The predictions CSV will contain one row per (as_of_date, cluster) in
  the test window, with columns including `lambda_hat` and
  `experiment_id`.
- The model automatically uses optional columns like `regime_risk_score`
  and `stab_risk_score` when they are present in the input CSV.


## 6. λ̂-aware universe backfill

Now use `backfill_universes_with_lambda.py` to build **lambda-aware
universes** by feeding the λ̂ predictions into `BasicUniverseModel` via
`CsvLambdaClusterScoreProvider`.

Example:

```bash
python -m prometheus.scripts.backfill_universes_with_lambda \
  --region US \
  --start 2023-01-01 \
  --end 2024-12-31 \
  --max-universe-size 200 \
  --min-liquidity-adv 100000 \
  --min-price 1.0 \
  --lambda-predictions data/lambda_predictions_US_EQ.csv \
  --experiment-id US_EQ_GL_FULL_V0 \
  --lambda-weight 10.0
```

This:

- Uses the same structural filters as `backfill_universes_basic`, but
  adds `lambda_score_weight * lambda_score` into the ranking.
- Writes `lambda_score`, `lambda_score_weight`, and metadata like
  `lambda_experiment_id` into `universe_members.reasons`.

You now have both **baseline** and **λ̂-aware** universes over the
historical window.


## 7. Synthetic scenarios and scenario-based risk

The Synthetic Scenario Engine is already implemented under
`prometheus.synthetic`. For v0 training you typically want at least one
**historical-window scenario set** per market.

### 7.1 Generate a historical scenario set

Use a small Python snippet to call `SyntheticScenarioEngine` and create a
ScenarioSet in the runtime DB.

Example:

```bash
python - << 'EOF'
from datetime import date

from prometheus.core.database import get_db_manager
from prometheus.data.reader import DataReader
from prometheus.synthetic import ScenarioRequest, SyntheticScenarioEngine

START = date(2020, 1, 1)
END = date(2024, 12, 31)

db = get_db_manager()
reader = DataReader(db_manager=db)
engine = SyntheticScenarioEngine(db_manager=db, data_reader=reader)

request = ScenarioRequest(
    name="US_EQ_HIST_20D_2020ON",
    description="20d historical windows for US_EQ from 2020 onwards",
    category="HISTORICAL",
    horizon_days=20,
    num_paths=500,
    markets=["US_EQ"],
    base_date_start=START,
    base_date_end=END,
)

set_ref = engine.generate_scenario_set(request)
print("created scenario_set_id=", set_ref.scenario_set_id)
EOF
```

This populates `scenario_sets` and `scenario_paths` with 20-day return
paths for instruments in `US_EQ`.

### 7.2 Compute scenario-based portfolio risk (research backfill)

You can either:

- Use **in-model** scenario risk via `PortfolioConfig.scenario_risk_scenario_set_ids`
  and `BasicLongOnlyPortfolioModel.build_risk_report`, or
- Use the **standalone CLI** `run_portfolio_scenario_risk.py` to backfill
  `portfolio_risk_reports` after the fact.

Example CLI for a single portfolio:

```bash
python -m prometheus.scripts.run_portfolio_scenario_risk \
  --portfolio-id US_EQ_CORE_PORT \
  --scenario-set-id US_EQ_HIST_20D_2020ON \
  --start 2023-01-01 --end 2024-12-31
```

This will, for each `(portfolio_id, as_of_date)` row in
`portfolio_risk_reports` in the window:

- Load target weights from `target_portfolios`.
- Compute per-scenario P&L via
  `compute_portfolio_scenario_pnl`.
- Write `scenario_pnl` and summary metrics like:
  - `US_EQ_HIST_20D_2020ON:scenario_pnl_mean`
  - `US_EQ_HIST_20D_2020ON:scenario_var_95`
  - `US_EQ_HIST_20D_2020ON:scenario_es_95`
  into `risk_metrics`.


## 8. Backtests + Meta with λ̂/state/scenario context

At this point you have:

- Regime history and regime risk series.
- STAB history and STAB state-change risk series.
- Baseline and λ̂-aware universes.
- λ_t(x) and λ̂ experiments.
- Synthetic scenario sets and portfolio scenario risk.

You can now run **full sleeve backtests** and Meta selection using the
existing backtest + Meta CLIs.

### 8.1 Run backtest campaigns (risk on/off)

See `docs/workflows/dev_workflows_backtest_and_risk.md` for detailed
usage. Typical pattern:

```bash
# Risk ON (sleeve pipeline uses Risk Management Service)
python -m prometheus.scripts.run_backtest_campaign \
  --market-id US_EQ \
  --start 2023-01-01 --end 2024-12-31 \
  --sleeve US_EQ_CORE_21D:US_EQ_CORE_LONG_EQ:US_EQ:US_EQ_CORE_UNIVERSE:US_EQ_CORE_PORT:US_EQ_CORE_ASSESS:21 \
  --initial-cash 1000000 \
  > campaign_risk_on.csv

# Risk OFF baseline
python -m prometheus.scripts.run_backtest_campaign \
  --market-id US_EQ \
  --start 2023-01-01 --end 2024-12-31 \
  --sleeve US_EQ_CORE_21D:US_EQ_CORE_LONG_EQ:US_EQ:US_EQ_CORE_UNIVERSE:US_EQ_CORE_PORT:US_EQ_CORE_ASSESS:21 \
  --initial-cash 1000000 \
  --disable-risk \
  > campaign_risk_off.csv
```

Because `BacktestRunner` now records λ̂/STAB/Regime exposure metrics
per-day and aggregates them into `backtest_runs.metrics_json`, these
campaigns become λ̂/state-aware by construction.

### 8.2 Run campaign + Meta selection

To run a canonical campaign and record a Meta decision:

```bash
python -m prometheus.scripts.run_campaign_and_meta \
  --strategy-id US_EQ_CORE_LONG_EQ \
  --market-id US_EQ \
  --start 2023-01-01 --end 2024-12-31 \
  --top-k 3 \
  --initial-cash 1000000
```

This:

- Runs the canonical sleeves for `STRATEGY_ID`.
- Writes `backtest_runs` with λ̂/state/scenario metrics in
  `metrics_json` (if you’ve run the scenario/STAB backfills).
- Uses `MetaOrchestrator` to select top sleeves by Sharpe.

You can then use the additional Meta helpers (from `MetaOrchestrator`):

- `select_top_sleeves_lambda_uplift(strategy_id, k)` – sleeves that
  **benefit most from high-λ̂ periods**.
- `select_top_sleeves_lambda_robust(strategy_id, k)` – sleeves that
  are **most stable across λ̂ regimes**.

These consume the λ̂ bucket metrics computed in
`BacktestRunner._compute_exposure_aggregates` and any additional
scenario/STAB metrics you have backfilled into `backtest_runs.metrics_json`.


## 9. Optional: Embeddings and joint spaces

Once the numeric v0 backfills are in place, you can optionally run the
existing embedding workflows to build joint spaces used by Meta and
scenario/STAB diagnostics:

- `backfill_joint_meta_config_env.py` – Meta Config+Env embeddings.
- `backfill_numeric_scenario_embeddings.py` – numeric scenario
  embeddings (`num-scenario-core-v1`).
- `backfill_joint_stab_fragility_states.py` and
  `backfill_joint_stab_fragility_scenarios.py` – joint STAB
  embeddings for instruments and scenarios.

See:

- `docs/workflows/dev_workflows_joint_meta_config_env.md`.
- `docs/workflows/dev_workflows_numeric_scenario_embeddings.md`.
- `docs/workflows/dev_workflows_joint_stab_fragility.md`.

These are not required for v0 numeric backfills but are the natural next
step once Regime/STAB/λ̂/scenario pipelines are in place.
