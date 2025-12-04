# Dev workflow: joint regime context embeddings

This document describes how to build and inspect **joint regime context
embeddings** that combine numeric regime embeddings
(`num-regime-core-v1`) with NEWS text embeddings (`text-fin-general-v1`)
into a shared `R^384` space via `joint-regime-core-v1`.

The workflow uses:

- `run_numeric_regime` – to produce numeric regime embeddings.
- `backfill_text_embeddings` – to embed NEWS text.
- `backfill_joint_regime_context` – to combine numeric + text into joint
  embeddings in `joint_embeddings`.
- `show_joint_regime_context` – to inspect the resulting joint vectors.

## 1. Prerequisites

- Database migrations applied (including `regimes`, `numeric_window_embeddings`,
  `text_embeddings`, and `joint_embeddings`).
- Historical price data written into `prices_daily` for the chosen
  instrument.
- `news_articles` populated for the chosen dates and `language`.
- Text embeddings backfill script dependencies installed
  (`transformers`, `torch`).

## 2. Step 1 – Run numeric regime for a region/date

From the project root (`prometheus_v2`), run a numeric regime pass for a
region using a representative instrument and the 384-dim numeric encoder
`num-regime-core-v1`:

```bash
python -m prometheus.scripts.run_numeric_regime \
  --region US \
  --instrument-id AAPL.US \
  --as-of 2025-01-31 \
  --window-days 63 \
  --model-id num-regime-core-v1
```

This will:

- Build a 63-day numeric window for `AAPL.US` with (close, volume,
  log-return) features.
- Encode the window with `num-regime-core-v1` (via
  `PadToDimNumericEmbeddingModel`) into a 384-dim vector.
- Persist the embedding into `numeric_window_embeddings`.
- Persist a regime row into `regimes` with `regime_embedding ∈ R^384`.

## 3. Step 2 – Backfill NEWS text embeddings for that date

Embed NEWS articles for the same date using `text-fin-general-v1`:

```bash
python -m prometheus.scripts.backfill_text_embeddings \
  --as-of 2025-01-31 \
  --language EN \
  --limit 10000 \
  --model-id text-fin-general-v1
```

This will:

- Select `news_articles` with `DATE(published_at) = '2025-01-31'` and
  `language = 'EN'`.
- Embed their text with the HF model configured in
  `backfill_text_embeddings.py`.
- Store vectors in `text_embeddings` with
  `source_type = 'NEWS', model_id = 'text-fin-general-v1'`.

## 4. Step 3 – Build joint regime context embeddings

Combine numeric regime embeddings with aggregated NEWS text embeddings
for the region/date into joint regime context embeddings:

```bash
python -m prometheus.scripts.backfill_joint_regime_context \
  --region US \
  --as-of 2025-01-31 \
  --text-model-id text-fin-general-v1 \
  --joint-model-id joint-regime-core-v1
```

This will:

- Load `regime_embedding` for `(region='US', as_of_date='2025-01-31')`.
- Aggregate all `NEWS` embeddings for the same date and `text-model-id`
  into a single 384-dim vector.
- Use `SimpleAverageJointModel` to compute a joint 384-dim vector in
  `R^384`.
- Insert a row into `joint_embeddings` with:
  - `joint_type = 'REGIME_CONTEXT_V0'`.
  - `model_id = 'joint-regime-core-v1'`.
  - `entity_scope` including the region and source information.

## 5. Step 4 – Inspect joint regime context embeddings

Use the inspection CLI to list joint regime context embeddings for a
region and date range:

```bash
python -m prometheus.scripts.show_joint_regime_context \
  --region US \
  --start 2025-01-01 \
  --end 2025-01-31 \
  --model-id joint-regime-core-v1 \
  --limit 200
```

Typical output:

```text
as_of_date,region,episode_id,model_id,dim,l2_norm
2025-01-31,US,,joint-regime-core-v1,384,12.345678
...
```

You can verify that:

- `dim` is always `384` (matching the joint space `R^384`).
- `l2_norm` values are in a reasonable range and stable over time.

## 6. Notes

- This workflow is **dev-facing** and can be iterated on as the joint
  regime model evolves (e.g. replacing the simple average with a trained
  projection while keeping the same model_id and joint space folder).
- The corresponding joint space is documented in:

  - `docs/joint_spaces/regime_num-regime-core-v1__text-fin-general-v1/README.md`.

- For larger ranges and multiple regions, consider redirecting output to
  a CSV file for offline analysis:

  ```bash
  python -m prometheus.scripts.show_joint_regime_context \
    --region US \
    --start 2025-01-01 \
    --end 2025-03-31 \
    > joint_regime_context_US_Q1_2025.csv
  ```
