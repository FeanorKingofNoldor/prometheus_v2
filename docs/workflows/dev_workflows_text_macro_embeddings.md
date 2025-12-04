# Dev workflow: macro text embeddings (text-macro-v1)

This document describes how to backfill **macro text embeddings** using
the `text-macro-v1` encoder model.

The goal is to produce 384-dim embeddings for macro/policy/news text
(FOMC statements, ECB speeches, major macro headlines) for use in the
`joint-regime-core-v1` and related macro-driven spaces.

## 1. Prerequisites

- Table(s) containing macro text, e.g. `macro_events` or a filtered
  subset of `news_articles`, with at least:
  - `event_id` or `article_id`.
  - `event_date` or `published_at`.
  - `text` (full statement or concatenated headline/body).
- `text_embeddings` table available in `historical_db`.
- `transformers` and `torch` installed for running the text encoder.

## 2. Decide on macro source and logical IDs

For v0 you can reuse `news_articles` with a macro filter or a dedicated
`macro_events` table:

- `source_type = 'MACRO'`.
- `source_id` = `event_id` or `article_id` as string.

## 3. Run a macro text backfill using text-macro-v1

Use the dedicated CLI script `backfill_macro_text_embeddings.py`:

```bash
python -m prometheus.scripts.backfill_macro_text_embeddings \
  --date-range 2024-01-01 2024-12-31 \
  --model-id text-macro-v1 \
  --hf-model-name sentence-transformers/all-MiniLM-L6-v2
```

This should:

- Select macro events or filtered news for the given date range.
- Embed their text using `text-macro-v1` (384-dim, same base model
  family as the other text encoders, but tuned for macro/policy).
- Store vectors into `text_embeddings` with
  `source_type = 'MACRO', model_id = 'text-macro-v1'`.

## 4. Inspecting macro text embeddings

Check that macro embeddings were written correctly:

```sql
SELECT source_type, model_id, COUNT(*) AS n,
       MIN(octet_length(vector)) AS min_bytes,
       MAX(octet_length(vector)) AS max_bytes
FROM text_embeddings
WHERE source_type = 'MACRO'
  AND model_id = 'text-macro-v1'
GROUP BY source_type, model_id;
```

- `min_bytes` and `max_bytes` should both be `384 * 4 = 1536` if the
  encoder outputs 384-dim `float32` vectors.

## 5. Notes

- The primary joint space that consumes these embeddings for v0 is:
  - `docs/joint_spaces/regime_num-regime-core-v1__text-macro-v1/README.md`.
- For an end-to-end example that goes from `macro_events` → `text_embeddings`
  → joint regime+macro context, see:
  - `docs/dev_workflows_joint_regime_macro_context.md`.
