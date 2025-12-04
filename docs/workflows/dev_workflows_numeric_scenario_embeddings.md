# Dev workflow: numeric scenario embeddings (num-scenario-core-v1)

This document describes a planned workflow for backfilling **numeric
scenario embeddings** using the `num-scenario-core-v1` encoder model.

The goal is to represent synthetic and historical scenarios as
384-dimensional vectors in `R^384` based on shock patterns and path
shapes.

## 1. Prerequisites

- A table or view containing scenario definitions and shock data, e.g.
  `scenarios` and `scenario_shocks`, with at least:
  - `scenario_id` (string).
  - `as_of_date` or a canonical `scenario_date`.
  - Shock vectors or paths (e.g. per-instrument/per-bucket returns,
    spreads, vols) over a fixed horizon.
- A target embeddings table, e.g. `numeric_scenario_embeddings` or
  reuse of `numeric_window_embeddings` with
  `entity_type = 'SCENARIO'`.

## 2. v0 encoder behaviour

`num-scenario-core-v1` is defined as a 384-dim numeric encoder that:

- Takes a normalised scenario shock vector or aggregated path features
  as input.
- Applies a deterministic mapping (e.g. linear layer or small MLP) to
  produce `z_scenario(scenario_id) ∈ R^384`.

For now, it is sufficient to treat it as:

- A simple flattening + padding encoder over a fixed-length shock
  vector, or
- A deterministic projection implemented in a dedicated script.

## 3. Run a numeric scenario backfill using num-scenario-core-v1

Use the dedicated backfill script `backfill_numeric_scenario_embeddings.py`:

```bash
python -m prometheus.scripts.backfill_numeric_scenario_embeddings \
  --scenario-set-id SET_ABC123 \
  --model-id num-scenario-core-v1 \
  --limit 100
```

This will:

- Select up to 100 distinct `scenario_id` values from `scenario_paths`
  for the given `scenario_set_id`.
- Build scenario return panels of shape `(horizon_days, num_instruments)`
  from `scenario_paths`.
- Encode them into 384-dim embeddings with `num-scenario-core-v1`
  (via `PadToDimNumericEmbeddingModel`).
- Store results into `numeric_window_embeddings` with
  `entity_type = 'SCENARIO'` and `model_id = 'num-scenario-core-v1'`.

## 4. Notes

- The primary consumer joint space for these embeddings is the
  stability/fragility space documented in:

  - `docs/joint_spaces/stab_num-stab-core-v1__num-scenario-core-v1__joint-profile-core-v1/README.md`.

- This workflow is a placeholder; it should be updated once the scenario
  schema and encoder implementation are in place.
