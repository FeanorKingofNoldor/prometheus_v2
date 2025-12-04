# Dev workflow: joint regime+macro context (joint-regime-core-v1)

This document describes how to build and inspect **joint regime+macro
context embeddings** that combine numeric regime embeddings
(`num-regime-core-v1`) with MACRO text embeddings (`text-macro-v1`) into
`R^384` via `joint-regime-core-v1`.

The workflow uses:

- `run_numeric_regime` – to produce numeric regime embeddings.
- `backfill_macro_text_embeddings` – to embed MACRO text.
- `backfill_joint_regime_macro_context` – to combine numeric + text into
  joint regime+macro embeddings (`REGIME_MACRO_V0`).
- `show_joint_regime_macro_context` – to inspect the resulting joint
  vectors.

## 1. Prerequisites

- Database migrations applied (including `regimes`, `text_embeddings`,
  `macro_events`, and `joint_embeddings`).
- Historical price data and regime state for the chosen regions/dates.
- Macro events populated in `macro_events` and MACRO text embeddings
  available via `backfill_macro_text_embeddings`.

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

This will populate `regimes` with `regime_embedding ∈ R^384` for
`region='US'` and `as_of_date='2025-01-31'`.

## 3. Step 2 – Backfill MACRO text embeddings

Embed MACRO events over a date range using `text-macro-v1`:

```bash
python -m prometheus.scripts.backfill_macro_text_embeddings \
  --date-range 2025-01-01 2025-01-31 \
  --model-id text-macro-v1 \
  --hf-model-name sentence-transformers/all-MiniLM-L6-v2
```

This will:

- Select rows from `macro_events` where `DATE(timestamp)` is in the
  range.
- Embed their text using `text-macro-v1`.
- Store 384-dim vectors in `text_embeddings` with
  `source_type = 'MACRO', model_id = 'text-macro-v1'`.

## 4. Step 3 – Build joint regime+macro context embeddings

Combine numeric regime embeddings with aggregated MACRO text embeddings
into joint regime+macro context embeddings:

```bash
python -m prometheus.scripts.backfill_joint_regime_macro_context \
  --region US \
  --date-range 2025-01-01 2025-01-31 \
  --text-model-id text-macro-v1 \
  --joint-model-id joint-regime-core-v1 \
  --country US
```

This will:

- Load `regime_embedding` for `(region='US', as_of_date in range)` from
  `regimes`.
- Aggregate all MACRO embeddings from `text_embeddings` joined with
  `macro_events` for `DATE(timestamp) = as_of_date` and the given
  filters.
- Use `SimpleAverageJointModel` to compute a joint 384-dim vector
  `z_regime_macro ∈ R^384`.
- Insert rows into `joint_embeddings` with:
  - `joint_type = 'REGIME_MACRO_V0'`.
  - `model_id = 'joint-regime-core-v1'`.
  - `entity_scope` including `region`, `source="regime+macro"`, and
    optional macro filters.

## 5. Step 4 – Inspect joint regime+macro context embeddings

Use the inspection CLI to list joint regime+macro context embeddings for
a region and date range:

```bash
python -m prometheus.scripts.show_joint_regime_macro_context \
  --region US \
  --start 2025-01-01 \
  --end 2025-01-31 \
  --model-id joint-regime-core-v1 \
  --limit 200
```

Typical output:

```text
as_of_date,region,model_id,dim,l2_norm
2025-01-31,US,joint-regime-core-v1,384,12.345678
...
```

## 6. Notes

- The corresponding joint space is documented in:

  - `docs/joint_spaces/regime_num-regime-core-v1__text-macro-v1/README.md`.

- This workflow is a sibling of `dev_workflows_joint_regime_context.md`;
  the difference is that it uses MACRO text (`text-macro-v1` and
  `macro_events`) instead of NEWS text (`text-fin-general-v1` and
  `news_articles`).