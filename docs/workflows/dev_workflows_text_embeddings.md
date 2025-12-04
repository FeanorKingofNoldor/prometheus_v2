# Dev workflow: text embeddings backfill

This document describes how to backfill text embeddings for news articles
into the `text_embeddings` table using the
`backfill_text_embeddings.py` script and the `text-fin-general-v1`
encoder.

## Prerequisites

- Database migrations applied (including the `text_embeddings` table).
- The `transformers` and `torch` Python packages installed in the current
  environment.
- Access to the `historical_db.news_articles` table with at least the
  following columns:
  - `article_id`
  - `published_at`
  - `language`
  - `headline`
  - `body`

## Basic usage

From the project root (`prometheus_v2`), run:

```bash
python -m prometheus.scripts.backfill_text_embeddings \
  --as-of 2025-01-31 \
  --language en \
  --model-id text-fin-general-v1
```

This will:

- Load English (`language = 'en'`) news articles from `historical_db.news_articles`
  with `published_at <= '2025-01-31'`.
- Concatenate `headline` and `body` into a single text field.
- Embed the texts using the Hugging Face model configured in
  `backfill_text_embeddings.py` (by default
  `sentence-transformers/all-MiniLM-L6-v2`).
- Store the resulting 384-dim vectors in `text_embeddings` with
  `model_id = 'text-fin-general-v1'`.

## Date ranges

To backfill over an explicit date range:

```bash
python -m prometheus.scripts.backfill_text_embeddings \
  --date-range 2025-01-01 2025-01-31 \
  --language en \
  --model-id text-fin-general-v1
```

`--as-of` and `--date-range` are mutually exclusive.

## Controlling volume

You can use `--limit` to cap the number of articles processed in a single
run, which is useful when testing:

```bash
python -m prometheus.scripts.backfill_text_embeddings \
  --as-of 2025-01-31 \
  --language en \
  --model-id text-fin-general-v1 \
  --limit 500
```

## Changing the underlying HF model

By default the script uses
`sentence-transformers/all-MiniLM-L6-v2` as the underlying encoder. You
can override this via `--hf-model-name`:

```bash
python -m prometheus.scripts.backfill_text_embeddings \
  --as-of 2025-01-31 \
  --language en \
  --model-id text-fin-general-v1 \
  --hf-model-name sentence-transformers/all-MiniLM-L12-v2
```

The logical `model_id` (e.g. `text-fin-general-v1`) is stored in the
DB; the HF model name is a runtime configuration detail.
