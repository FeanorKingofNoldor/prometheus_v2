# Dev workflow: portfolio STAB-scenario diagnostics
+
+This document describes how to analyse **portfolio-level exposure to
+stability/fragility scenarios** using joint STAB embeddings
+(`STAB_FRAGILITY_V0`).
+
+The workflow combines:
+
+- Instrument-level STAB embeddings and joint STAB states.
+- Scenario-level STAB embeddings for a scenario set.
+- Portfolio targets and risk reports.
+
+## 1. Prerequisites
+
+Before running portfolio STAB-scenario diagnostics, you should have:
+
+- Numeric STAB embeddings (`num-stab-core-v1`) backfilled into
+  `numeric_window_embeddings`.
+- Joint STAB states for instruments (`STAB_FRAGILITY_V0`) populated via
+  `backfill_joint_stab_fragility_states`.
+- Scenario-level STAB embeddings for one or more scenario sets
+  (`STAB_FRAGILITY_V0`, entity_type = `SCENARIO`) populated via
+  `backfill_joint_stab_fragility_scenarios`.
+- Target portfolios and portfolio risk reports produced by the
+  Portfolio & Risk Engine, i.e. rows in `target_portfolios` and
+  `portfolio_risk_reports` for the portfolios/dates of interest.
+
+## 2. Build instrument and scenario STAB embeddings
+
+If not already done, backfill instrument-level and scenario-level joint
+STAB embeddings as described in `docs/dev_workflows_joint_stab_fragility.md`.
+
+Example (instrument STAB states for US_EQ on a date):
+
+```bash
+python -m prometheus.scripts.backfill_joint_stab_fragility_states \
+  --as-of 2025-01-31 \
+  --market-id US_EQ \
+  --stab-model-id num-stab-core-v1 \
+  --joint-model-id joint-stab-fragility-v1
+```
+
+Example (scenario-level STAB embeddings for a scenario set):
+
+```bash
+python -m prometheus.scripts.backfill_joint_stab_fragility_scenarios \
+  --scenario-set-id STAB_EQ_CRASH_SET_V0 \
+  --scenario-model-id num-scenario-core-v1 \
+  --joint-model-id joint-stab-fragility-v1
+```
+
+## 3. Run Portfolio & Risk Engine to produce targets and risk reports
+
+Use the existing portfolio workflows (backtests or daily engine runs) to
+produce:
+
+- `target_portfolios` rows with `target_positions["weights"]` for each
+  `(portfolio_id, as_of_date)`.
+- `portfolio_risk_reports` rows with basic risk metrics for the same
+  `(portfolio_id, as_of_date)`.
+
+See `docs/dev_workflows_backtest_and_risk.md` for examples using
+`run_backtest_campaign` and `run_campaign_and_meta`.
+
+## 4. Inspect portfolio STAB-scenario exposure on a single date
+
+To see which scenarios are closest to a portfolio's current STAB state
+on a given date, use the `show_portfolio_stab_scenario_exposure` CLI:
+
+```bash
+python -m prometheus.scripts.show_portfolio_stab_scenario_exposure \
+  --portfolio-id PORTFOLIO_CORE_US_EQ_001 \
+  --as-of 2025-01-31 \
+  --scenario-set-id STAB_EQ_CRASH_SET_V0 \
+  --stab-model-id joint-stab-fragility-v1 \
+  --top-k 20
+```
+
+Typical output:
+
+```text
+cosine,euclidean,scenario_set_id,scenario_id,scenario_as_of,portfolio_id,portfolio_ctx_norm,num_instruments_used
+0.987654,0.432100,STAB_EQ_CRASH_SET_V0,SCN_001,2020-03-23,PORTFOLIO_CORE_US_EQ_001,11.123456,157
+...
+```
+
+- `cosine` – alignment between the portfolio STAB vector and the
+  scenario STAB vector (higher = more similar).
+- `euclidean` – distance in STAB joint space (lower = closer).
+- `portfolio_ctx_norm` – L2 norm of the portfolio STAB vector.
+- `num_instruments_used` – number of instruments in the portfolio with
+  available STAB embeddings.
+
+## 5. Backfill scenario-aware metrics into portfolio_risk_reports
+
+To store summary scenario metrics directly into
+`portfolio_risk_reports.risk_metrics`, use the
+`backfill_portfolio_stab_scenario_metrics` CLI:
+
+```bash
+python -m prometheus.scripts.backfill_portfolio_stab_scenario_metrics \
+  --portfolio-id PORTFOLIO_CORE_US_EQ_001 \
+  --scenario-set-id STAB_EQ_CRASH_SET_V0 \
+  --stab-model-id joint-stab-fragility-v1 \
+  --start 2025-01-01 --end 2025-12-31
+```
+
+For each matching row in `portfolio_risk_reports`, this will:
+
+- Load the corresponding target weights from `target_portfolios`.
+- Compute a portfolio STAB vector and its norm.
+- Compare it to all scenarios in `STAB_EQ_CRASH_SET_V0`.
+- Identify the closest scenario and compute summary statistics.
+- Overwrite/add the following keys in `risk_metrics`:
+  - `stab_scenario_set_id`
+  - `stab_closest_scenario_id`
+  - `stab_closest_scenario_cosine`
+  - `stab_closest_scenario_distance`
+  - `stab_portfolio_ctx_norm`
+  - `stab_top3_scenario_cosine_mean`
+
## 6. Summarise STAB-scenario exposure for backtests
+
+Once you have:
+
+- Run backtests that produce `backtest_runs` and `portfolio_risk_reports`
+  rows (e.g. via `run_backtest_campaign` or `run_campaign_and_meta`).
+- Populated per-date portfolio STAB-scenario metrics into
+  `portfolio_risk_reports.risk_metrics` using
+  `backfill_portfolio_stab_scenario_metrics`.
+
+you can backfill simple run-level STAB-scenario summary metrics into
+`backtest_runs.metrics_json` using the
+`backfill_backtest_stab_scenario_metrics` CLI.
+
+Example: summarise all runs for a given strategy:
+
+```bash
+python -m prometheus.scripts.backfill_backtest_stab_scenario_metrics \
+  --strategy-id US_CORE_LONG_EQ
+```
+
+Or restrict to a single run:
+
+```bash
+python -m prometheus.scripts.backfill_backtest_stab_scenario_metrics \
+  --run-id 123e4567-e89b-12d3-a456-426614174000
+```
+
+For each run, this will:
+
+- Look up the `portfolio_id` from `backtest_runs.config_json`.
+- Load `portfolio_risk_reports` rows for that `portfolio_id` over the
+  run's `[start_date, end_date]`.
+- Aggregate STAB metrics across days, writing into
+  `backtest_runs.metrics_json` keys such as:
+  - `stab_scenario_set_id` (most common scenario set across the run)
+  - `stab_closest_scenario_cosine_mean`
+  - `stab_closest_scenario_cosine_min`
+  - `stab_closest_scenario_cosine_max`
+  - `stab_portfolio_ctx_norm_mean`
+  - `stab_portfolio_ctx_norm_max`
+  - `stab_num_days`
+
+These metrics then appear alongside `cumulative_return`,
+`annualised_sharpe`, etc. in `backtest_runs.metrics_json`, and can be
+used by downstream tools (e.g. Meta-Orchestrator, notebooks, dashboards)
+to analyse which sleeves/strategies tended to sit close to or far from
+particular STAB scenarios.
+
+## 7. Notes
+
+- This is a v0 diagnostic workflow intended for research and offline
+  risk analysis. It does not currently influence optimisation directly.
+- The same STAB joint space (`STAB_FRAGILITY_V0`,
+  `joint-stab-fragility-v1`) is used for instruments and scenarios,
+  ensuring that cosine/distance comparisons are meaningful.
+- You can define multiple scenario sets (e.g., equity crashes,
+  sovereign crises) and run this workflow for each to build a richer
+  picture of portfolio fragility.
+