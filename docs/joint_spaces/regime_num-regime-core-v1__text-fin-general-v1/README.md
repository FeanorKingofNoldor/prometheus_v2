# Joint Space: Regime – num-regime-core-v1 + text-fin-general-v1

This document describes the current v0 joint space used for **regime
context**, built from:

- Numeric encoder: `num-regime-core-v1` (384-dim regime numeric
  embeddings).
- Text encoder: `text-fin-general-v1` (384-dim financial/news text
  embeddings).
- Joint model: `joint-regime-core-v1` (currently implemented as a simple
  weighted average of the two branches via `SimpleAverageJointModel`).

The folder name encodes the ingredients of the space:

- `regime_num-regime-core-v1__text-fin-general-v1`
  - `regime` – use case / space type.
  - `num-regime-core-v1` – numeric branch model_id.
  - `text-fin-general-v1` – text branch model_id.

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

### 1.2 Text branch: Aggregated NEWS embeddings

- Base tables:
  - `historical_db.text_embeddings` with `source_type = 'NEWS'` and
    `model_id = 'text-fin-general-v1'`.
  - `historical_db.news_articles` for `published_at` and `language`.
- For a given `as_of_date` and optional `language` filter:
  1. Join `text_embeddings` and `news_articles` on
     `source_id = article_id::text`.
  2. Filter `DATE(published_at) = as_of_date`.
  3. Collect all matching vectors `v_i ∈ R^384`.
  4. Compute their mean:

     ```text
     z_text = mean_i v_i  ∈ R^384
     ```

If no such vectors exist for a date, that date is skipped.

### 1.3 Joint model: SimpleAverageJointModel

- Implementation:
  - Module: `prometheus/encoders/models_joint_simple.py`.
  - Class: `SimpleAverageJointModel`.
- For each example with numeric embedding `z_num` and text embedding
  `z_text` (same shape):

  ```text
  z_joint = (w_num * z_num + w_text * z_text) / (w_num + w_text)
  ```

- Current default weights:
  - `numeric_weight = 0.5`.
  - `text_weight = 0.5`.
- Output dimension:
  - Same as inputs (384-dim), i.e. the joint space is `R^384`.

### 1.4 Persistence

- Target table: `historical_db.joint_embeddings`.
- Fields set by `JointEmbeddingStore.save_embeddings`:
  - `joint_type = 'REGIME_CONTEXT_V0'`.
  - `as_of_date` = regime date.
  - `entity_scope` JSON, currently:

    ```json
    {"region": <region>, "source": "regime+news"}
    ```

  - `model_id = 'joint-regime-core-v1'`.
  - `vector` = `z_joint` as float32 bytes.
  - `vector_ref = NULL` (for now).


## 2. Backfill workflow

CLI: `prometheus.scripts.backfill_joint_regime_context`.

Examples:

```bash
# Single date, single region
python -m prometheus.scripts.backfill_joint_regime_context \
  --region US \
  --as-of 2025-01-31 \
  --text-model-id text-fin-general-v1 \
  --joint-model-id joint-regime-core-v1

# Date range, multiple regions
python -m prometheus.scripts.backfill_joint_regime_context \
  --region US \
  --region EU \
  --date-range 2025-01-01 2025-01-31 \
  --text-model-id text-fin-general-v1 \
  --joint-model-id joint-regime-core-v1
```

Prerequisites:

- Regime embeddings present in `regimes` for the chosen regions/dates.
- Text embeddings present in `text_embeddings` for `source_type = 'NEWS'`
  and `model_id = 'text-fin-general-v1'` on those dates.
- (Optional) `language` filter matching `news_articles.language`.

## 3. Future evolution

This v0 joint space is intentionally simple and transparent. Future
iterations may:

- Replace `SimpleAverageJointModel` with a trained projection head while
  keeping:
  - The same model_id (`joint-regime-core-v1`).
  - The same folder name and concept (regime + specific numeric/text
    encoders).
- Add alternative branches (e.g. `text-macro-v1`) in a new space with a
  distinct folder name encoding the new ingredients, e.g.:

  - `regime_num-regime-core-v1__text-macro-v1`.

The goal is that from the folder name alone you can see **which
encoders/metrics feed this joint space**, and from this README you can
see exactly how the joint embedding is constructed.
