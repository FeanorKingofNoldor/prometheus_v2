# Dev workflow: numeric embeddings backfill

This document describes how to backfill numeric window embeddings into the
`numeric_window_embeddings` table using the
`backfill_numeric_embeddings.py` script.

The primary v0 use case is the `num-regime-core-v1` model, which produces
384-dimensional numeric embeddings suitable for the Regime engine and
other downstream components.

## Prerequisites

- Database migrations applied (including the `numeric_window_embeddings`
  table).
- Historical price data present in `prices_daily` for the instruments or
  markets you want to embed.
- A working Postgres connection configured via the core Prometheus
  config.

## Basic usage: market-wide backfill for num-regime-core-v1

From the project root (`prometheus_v2`), run:

```bash
python -m prometheus.scripts.backfill_numeric_embeddings \
  --as-of 2025-01-31 \
  --window-days 63 \
  --market-id US_EQ \
  --limit 500 \
  --model-id num-regime-core-v1
```

This will:

- Select up to 500 instruments from the `US_EQ` market.
- For each instrument, build a 63-trading-day numeric window with 3
  features per day (close, volume, log return).
- Flatten the window and pad/truncate it to a 384-dimensional vector
  (the standard v0 embedding size).
- Store the resulting vectors in `numeric_window_embeddings` with
  `model_id = 'num-regime-core-v1'`.

## Targeting specific instruments

To embed one or more specific instruments instead of an entire market,
pass `--instrument-id` one or more times and omit `--market-id`:

```bash
python -m prometheus.scripts.backfill_numeric_embeddings \
  --as-of 2025-01-31 \
  --window-days 63 \
  --instrument-id TEST_INST_1 \
  --instrument-id TEST_INST_2 \
  --model-id num-regime-core-v1
```

## Using the simple flattening model

For debugging or exploratory work, you can use the legacy
`numeric-simple-v1` model, which stores the raw flattened window without
forcing a fixed dimension:

```bash
python -m prometheus.scripts.backfill_numeric_embeddings \
  --as-of 2025-01-31 \
  --window-days 63 \
  --market-id US_EQ \
  --limit 100 \
  --model-id numeric-simple-v1
```

In this case, the embedding dimension will be `window_days * 3`.

## Verifying stored embeddings

You can inspect stored embeddings directly from the database, for
example by querying `numeric_window_embeddings` for a given
`entity_id`, `as_of_date`, and `model_id`, and decoding the `vector`
column as a `float32` NumPy array.

For `num-regime-core-v1`, each decoded vector should have shape `(384,)`
regardless of the exact window length used upstream, due to the
flatten-and-pad/truncate behaviour of the numeric encoder.
