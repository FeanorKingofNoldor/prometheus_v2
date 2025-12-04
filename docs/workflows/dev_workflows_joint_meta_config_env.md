# Dev workflow: meta config+env embeddings (joint-meta-config-env-v1)

This document describes how to backfill and inspect **Meta Config+Env
embeddings** that represent "config + environment + outcome" points in
`R^384` via `joint-meta-config-env-v1`.

The underlying joint space is specified in:

- `docs/joint_spaces/meta_num-config-core-v1__num-env-core-v1__num-outcome-core-v1/README.md`.

## 1. Prerequisites

Before building meta config+env embeddings, you should have:

- Backtest runs recorded in `runtime_db.backtest_runs` with
  `config_json` and `metrics_json` populated.
- Alembic migrations applied including the Meta-Orchestrator core tables
  (engine_decisions, decision_outcomes) for future extensions.

At v0, we derive numeric encoders directly from `config_json` and
`metrics_json` inside the backfill script as simple hand-engineered
feature extractors (flatten + hash for categoricals, numeric values
passed through).

## 2. Backfill Meta Config+Env embeddings

Use the dedicated CLI script `backfill_joint_meta_config_env.py` to
construct Meta Config+Env embeddings from `backtest_runs`.

Example: backfill for a given strategy

```bash
python -m prometheus.scripts.backfill_joint_meta_config_env \
  --strategy-id US_EQ_CORE_LONG_EQ \
  --start 2025-01-01 --end 2025-12-31 \
  --limit 200 \
  --w-config 1.0 --w-env 1.0 --w-outcome 1.0 \
  --joint-model-id joint-meta-config-env-v1
```

This will:

1. Query `backtest_runs` for rows with non-null `metrics_json` matching
   the given `strategy_id` and `end_date` range.
2. For each run:
   - Build `z_config(run_id) ∈ R^384` from `config_json` using a
     flatten+hash encoder (numeric and boolean fields kept as-is, string
     fields hashed deterministically into floats).
   - Build `z_env(run_id) ∈ R^384` from environment-oriented config
     fields (e.g. `market_id`, `universe_id`, `assessment_*`).
   - Build `z_outcome(run_id) ∈ R^384` from `metrics_json` by collecting
     numeric summary metrics (Sharpe, drawdown, etc.).
3. Combine available branches into `z_meta ∈ R^384` via a weighted
   average using `--w-config`, `--w-env`, and `--w-outcome`.
4. Insert rows into `joint_embeddings` with:
   - `joint_type = 'META_CONFIG_ENV_V0'`.
   - `model_id = 'joint-meta-config-env-v1'` (or the value passed via
     `--joint-model-id`).
   - `entity_scope` describing `run_id`, `strategy_id`, `universe_id`,
     and a `source` tag indicating which branches were used.

## 3. Inspect Meta Config+Env embeddings

Use the inspection CLI to view Meta Config+Env embeddings and basic
vector diagnostics:

```bash
python -m prometheus.scripts.show_joint_meta_config_env \
  --model-id joint-meta-config-env-v1 \
  --limit 200
```

You can also filter by strategy, universe, run_id, or date range, e.g.:

```bash
python -m prometheus.scripts.show_joint_meta_config_env \
  --strategy-id US_EQ_CORE_LONG_EQ \
  --start 2025-01-01 --end 2025-12-31 \
  --model-id joint-meta-config-env-v1
```

Typical output:

```text
as_of_date,run_id,strategy_id,universe_id,model_id,dim,l2_norm
2025-06-30,BT_RUN_123,US_EQ_CORE_LONG_EQ,US_EQ_UNIVERSE_A,joint-meta-config-env-v1,384,10.987654
...
```

## 4. Using Meta Config+Env with Meta-Orchestrator

Once `META_CONFIG_ENV_V0` embeddings have been backfilled, they can be
used alongside the Meta-Orchestrator in a typical workflow:

1. Run a sleeve backtest campaign and record a Meta-Orchestrator
   decision, e.g. via:

   ```bash
   python -m prometheus.scripts.run_campaign_and_meta \
     --strategy-id US_EQ_CORE_LONG_EQ \
     --market-id US_EQ \
     --start 2024-01-01 --end 2024-03-31 \
     --top-k 3
   ```

2. Backfill `META_CONFIG_ENV_V0` embeddings for the same strategy and
   date range (if not already done):

   ```bash
   python -m prometheus.scripts.backfill_joint_meta_config_env \
     --strategy-id US_EQ_CORE_LONG_EQ \
     --start 2024-01-01 --end 2024-12-31 \
     --limit 500 \
     --joint-model-id joint-meta-config-env-v1
   ```

3. When you later call `run_meta_for_strategy` or
   `run_campaign_and_meta_for_strategy`, the Meta-Orchestrator will
   automatically annotate each `SleeveEvaluation.metrics` dict with a
   `meta_ctx_norm` field when a corresponding `META_CONFIG_ENV_V0`
   embedding exists for the run. This provides a quick scalar diagnostic
   of how "large" the config+env+outcome vector is for each sleeve.

You can still inspect and search the full joint space directly:

- The v0 encoders for `num-config-core-v1`, `num-env-core-v1`, and
  `num-outcome-core-v1` are implemented inline in the backfill script as
  simple flatten+pad models producing 384-dim vectors.
- The implementation follows the patterns used in other joint backfills:
  - `backfill_joint_regime_context`.
  - `backfill_joint_episodes`.
  - `backfill_joint_profiles`.
  - `backfill_joint_stab_fragility_states`.
  - `backfill_joint_assessment_context`.
- To search for similar runs in Meta Config+Env space, you can use:

  ```bash
  python -m prometheus.scripts.find_similar_meta_runs \
    --run-id BT_RUN_123 \
    --strategy-id US_EQ_CORE_LONG_EQ \
    --model-id joint-meta-config-env-v1 \
    --top-k 20
  ```

- Once the meta space is populated, it can be used by the
  Meta-Orchestrator to:
  - Retrieve similar past runs/configs.
  - Visualise the landscape of configs and their behaviours.
  - Drive smarter search over config space while keeping everything
    numeric and backtestable.
