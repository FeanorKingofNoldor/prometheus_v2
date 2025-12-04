# Dev workflow: numeric stability embeddings (num-stab-core-v1)

This document describes how to backfill **numeric stability embeddings**
using the `num-stab-core-v1` encoder model via the generic numeric
backfill script.

For v0, `num-stab-core-v1` shares the same numeric window construction
as `num-regime-core-v1` (windows of (close, volume, log-return) over
`prices_daily`) and uses a padded 384-dim encoder in line with the
global spec. Later iterations can specialise the feature set for
stability-specific metrics.

## 1. Prerequisites

- Historical price data in `prices_daily` for the instruments/markets of
  interest.
- `numeric_window_embeddings` table available in `historical_db`.
- The `backfill_numeric_embeddings` script wired to treat
  `num-stab-core-v1` as a 384-dim padded numeric encoder.

## 2. Backfill numeric stability embeddings

From the project root (`prometheus_v2`), run:

```bash
python -m prometheus.scripts.backfill_numeric_embeddings \
  --as-of 2025-01-31 \
  --window-days 63 \
  --market-id US_EQ \
  --limit 500 \
  --model-id num-stab-core-v1
```

This will:

- Select up to 500 active `US_EQ` instruments.
- Build 63-day windows of (close, volume, log-return) features for each.
- Encode each window into a 384-dim vector using a padded numeric
  encoder (`PadToDimNumericEmbeddingModel`).
- Store embeddings in `numeric_window_embeddings` with
  `model_id = 'num-stab-core-v1'`.

## 3. Inspecting numeric stability embeddings

You can sanity-check stored stability embeddings via SQL:

```sql
SELECT entity_type, model_id, COUNT(*) AS n,
       MIN(octet_length(vector)) AS min_bytes,
       MAX(octet_length(vector)) AS max_bytes
FROM numeric_window_embeddings
WHERE model_id = 'num-stab-core-v1'
GROUP BY entity_type, model_id;
```

- `min_bytes` and `max_bytes` should both be `384 * 4 = 1536` for
  384-dim `float32` vectors.

## 4. Notes

- Future versions of `num-stab-core-v1` may:
  - Incorporate richer features (volatility paths, drawdown stats,
    liquidity measures) derived from additional tables.
  - Use a learned projection head instead of simple flatten+pad.
- The corresponding joint stability/fragility space that will consume
  these embeddings is described in:

  - `docs/joint_spaces/stab_num-stab-core-v1__num-scenario-core-v1__joint-profile-core-v1/README.md`.
