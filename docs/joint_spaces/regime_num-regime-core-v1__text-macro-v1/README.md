# Joint Space: Regime – num-regime-core-v1 + text-macro-v1

This document describes a planned v0 joint space used for **regime
context with macro text**, built from:

- Numeric encoder: `num-regime-core-v1` (384-dim regime numeric
  embeddings).
- Text encoder: `text-macro-v1` (384-dim macro/policy/news text
  embeddings).
- Joint model: `joint-regime-core-v1` (same family as the
  NEWS-based regime context, typically implemented via a small projection
  head or a simple weighted average as in `SimpleAverageJointModel`).

The folder name encodes the ingredients of the space:

- `regime_num-regime-core-v1__text-macro-v1`
  - `regime` – use case / space type.
  - `num-regime-core-v1` – numeric branch model_id.
  - `text-macro-v1` – text branch model_id for macro events.

## 1. Construction

### 1.1 Numeric branch: Regime embeddings

- Source table: `runtime_db.regimes`.
- Field: `regime_embedding` (stored as float32 bytes).
- Typical producer:
  - `NumericRegimeModel` using `NumericWindowEncoder` with
    `num-regime-core-v1` (384-dim) under the hood.
  - CLI: `run_numeric_regime` with `--model-id num-regime-core-v1`.

Each `(region, as_of_date)` where a regime row exists provides a single
numeric embedding `z_num ∈ R^384`.

### 1.2 Text branch: Aggregated MACRO embeddings

- Base tables:
  - `historical_db.text_embeddings` with `source_type = 'MACRO'` and
    `model_id = 'text-macro-v1'`.
  - `historical_db.macro_events` for `timestamp`, `country`, and
    metadata.
- For a given `as_of_date` and optional `country` filter:

  1. Join `text_embeddings` and `macro_events` on
     `source_id = event_id::text`.
  2. Filter `DATE(timestamp) = as_of_date`.
  3. Optionally filter `country` and/or `event_type`.
  4. Collect all matching vectors `v_i ∈ R^384`.
  5. Compute their mean:

     ```text
     z_text_macro = mean_i v_i  ∈ R^384
     ```

If no such vectors exist for a date, that date is skipped.

### 1.3 Joint model: joint-regime-core-v1

- Model id: `joint-regime-core-v1` shared with the NEWS-based regime
  context space.
- For each example with numeric embedding `z_num` and macro text
  embedding `z_text_macro` (same shape):

  ```text
  z_joint = (w_num * z_num + w_text * z_text_macro) / (w_num + w_text)
  ```

- Output dimension:
  - Same as inputs (384-dim), i.e. the joint space is `R^384`.

## 2. Persistence in `joint_embeddings`

- Target table: `historical_db.joint_embeddings`.
- Proposed v0 labelling:
  - `joint_type = 'REGIME_MACRO_V0'`.
  - `as_of_date` = regime date.
  - `entity_scope` JSON, e.g.:

    ```json
    {
      "region": "US",
      "source": "regime+macro",
      "macro_filters": {
        "country": "US"
      }
    }
    ```

  - `model_id = 'joint-regime-core-v1'`.
  - `vector` = `z_joint` as float32 bytes.

## 3. Backfill workflow

A dedicated backfill script (not yet implemented) would:

- Load regime embeddings from `regimes` for chosen regions/dates.
- Load and aggregate MACRO text embeddings for `text-macro-v1` from
  `text_embeddings` joined to `macro_events`.
- Construct `JointExample`s with `joint_type = 'REGIME_MACRO_V0'` and
  appropriate `entity_scope`.
- Use `JointEmbeddingService` with `joint-regime-core-v1` to write
  vectors into `joint_embeddings`.

CLI sketches (subject to implementation):

```bash
python -m prometheus.scripts.backfill_joint_regime_macro_context \
  --region US \
  --date-range 2025-01-01 2025-01-31 \
  --text-model-id text-macro-v1 \
  --joint-model-id joint-regime-core-v1
```

## 4. Relationship to NEWS-based regime context

This macro joint space is a sibling of the NEWS-based regime context
space defined in:

- `docs/joint_spaces/regime_num-regime-core-v1__text-fin-general-v1/README.md`.

Both share the same numeric branch and joint model id, but differ in
which text encoder and source they use (`NEWS` vs `MACRO`).

In practice you can:

- Maintain both spaces in parallel.
- Compare distances/similarities in each space separately.
- Optionally combine them in a higher-level joint context space if
  needed for downstream models.
