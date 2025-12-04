# Joint Space: Meta Config+Env – num-config-core-v1 + num-env-core-v1 + num-outcome-core-v1

This document describes a planned v0 joint space for **Meta-Orchestrator
config + environment + outcome** points, built from:

- `num-config-core-v1` – numeric encoder for engine/backtest
  configuration parameters.
- `num-env-core-v1` – numeric encoder for environment descriptors
  (regime mix, stability context, universe characteristics, etc.).
- `num-outcome-core-v1` – numeric encoder for outcome summaries
  (Sharpe, drawdown, turnover, robustness metrics, etc.).

The folder name encodes the ingredients of the space:

- `meta_num-config-core-v1__num-env-core-v1__num-outcome-core-v1`

## 1. Goals

The Meta Config+Env joint space aims to represent each "experiment" or
backtest/meta run as a point in `R^384` that captures:

- **What was tried** (configuration).
- **Where it was tried** (market/regime/universe environment).
- **How it behaved** (outcomes and robustness).

This supports tasks like:

- Finding past configs that worked in similar environments.
- Clustering configs by behaviour, not just raw hyperparameters.
- Suggesting candidate configs by nearest-neighbour search in this
  space (to be revalidated via backtests).

## 2. Branches

### 2.1 Config branch – num-config-core-v1

- Input: numeric representation of configuration parameters, e.g.:
  - engine hyperparameters,
  - risk/portfolio settings,
  - universe/assessment choices.
- Output: `z_config(run_id) ∈ R^384`.

### 2.2 Environment branch – num-env-core-v1

- Input: numeric descriptors of the environment during the run, e.g.:
  - distribution of regimes and volatility levels,
  - stability/fragility statistics,
  - universe composition metrics.
- Output: `z_env(run_id) ∈ R^384`.

### 2.3 Outcome branch – num-outcome-core-v1

- Input: numeric summary of outcomes, e.g.:
  - Sharpe, CAGR, max drawdown,
  - turnover, hit rate,
  - robustness metrics across scenarios.
- Output: `z_outcome(run_id) ∈ R^384`.

## 3. Joint model – joint-meta-config-env-v1

The joint model `joint-meta-config-env-v1` combines the three branches
into a single meta embedding:

```text
z_meta = f( z_config, z_env, z_outcome ) ∈ R^384
```

For v0, this may be implemented as:

- Concatenation of the three vectors followed by a linear projection
  back to `R^384`, or
- A weighted average in `R^384` when using simpler encoders.

## 4. Persistence in `joint_embeddings`

Meta Config+Env embeddings can be stored in `historical_db.joint_embeddings` with:

- `joint_type = 'META_CONFIG_ENV_V0'` (proposed label).
- `as_of_date` – date of the run or summary.
- `entity_scope` – JSON describing the run, e.g.:

  ```json
  {
    "run_id": "BT_RUN_12345",
    "config_id": "CFG_CORE_LONG_EQ_V3",
    "strategy_id": "US_EQ_CORE_LONG_EQ",
    "source": "meta-config-env"
  }
  ```

- `model_id = 'joint-meta-config-env-v1'`.
- `vector` – `z_meta ∈ R^384` as float32 bytes.

## 5. Use in Meta-Orchestrator

The Meta-Orchestrator can use this joint space to:

- Retrieve similar past runs/configs given a target environment.
- Visualise the landscape of configs and their behaviours.
- Drive smarter search over config space (e.g. Bayesian optimisation or
  k-NN suggestions) while keeping everything traceable and numeric.

## 6. Future work

- Implement numeric encoders `num-config-core-v1`, `num-env-core-v1`,
  and `num-outcome-core-v1` based on existing schemas for configs,
  environments, and outcomes.
- Add a backfill script that constructs Meta Config+Env embeddings from
  historical runs and stores them in `joint_embeddings`.
- Integrate this space into Meta-Orchestrator search and analytics
  workflows.
