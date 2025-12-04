# Dev workflow: numeric Regime Engine (numeric embeddings)

This document describes how to run the numeric Regime Engine end-to-end
using the `run_numeric_regime` CLI. The focus is on the v0 numeric
regime path based on numeric window embeddings.

This is a **developer workflow** for the current iteration, not a final
user-facing spec. Details (models, thresholds, prototypes) may change as
Regime evolves.

## Prerequisites

- Database migrations applied (including `numeric_window_embeddings`,
  `regimes`, and `regime_transitions`).
- Historical price data in `prices_daily` for the instrument you want to
  use as a numeric proxy for a region (e.g. an index future or ETF).
- A working DB config so that `get_db_manager()` can connect.

## Basic usage: run numeric regime with 384-dim embeddings

From the project root (`prometheus_v2`), run:

```bash
python -m prometheus.scripts.run_numeric_regime \
  --region US \
  --instrument-id AAPL.US \
  --as-of 2025-01-31 \
  --window-days 63 \
  --model-id num-regime-core-v1
```

What this does:

- Builds a 63-trading-day numeric window for `AAPL.US` with 3 features
  per day (close, volume, log return).
- Uses the `num-regime-core-v1` numeric encoder to produce a
  384-dimensional embedding (flatten + pad/truncate).
- Uses that embedding as the centre of a simple NEUTRAL prototype and
  classifies the region using `NumericRegimeModel`.
- Persists the embedding into `numeric_window_embeddings` and the regime
  state into `regimes` / `regime_transitions`.
- Prints a one-line summary to stdout, e.g.:

```text
Regime as of 2025-01-31 for region US: label=NEUTRAL, confidence=1.000
```

In this v0 workflow the prototype is deliberately trivial (the current
embedding itself); the value is in exercising the full numeric pipeline
and validating that embeddings and regimes are written correctly.

## Using the simple flattening model instead

For debugging or exploratory runs where you care about the raw flattened
window rather than a fixed 384-dim vector, use the legacy
`numeric-simple-v1` model:

```bash
python -m prometheus.scripts.run_numeric_regime \
  --region US \
  --instrument-id AAPL.US \
  --as-of 2025-01-31 \
  --window-days 63 \
  --model-id numeric-simple-v1
```

In this case:

- The encoder flattens the `(window_days, 3)` window into a
  `window_days * 3`-dimensional vector.
- That vector becomes both the stored embedding and the NEUTRAL
  prototype centre.

## Verifying stored regime state and embeddings

After a run you can sanity-check what was written.

1. **Numeric embeddings** (historical DB):

   - Query `numeric_window_embeddings` for
     `(entity_type='INSTRUMENT', entity_id=<instrument_id>, as_of_date, model_id)`.
   - Decode `vector` as a `float32` NumPy array.
   - For `num-regime-core-v1`, the decoded vector should have shape
     `(384,)`.

2. **Regime states** (runtime DB):

   - Query `regimes` for `(region=<region>, as_of_date=<as_of>)`.
   - Check that `regime_label`, `confidence`, `metadata`, and
     `regime_embedding` are populated.
   - Decode `regime_embedding` as a `float32` NumPy array; it should
     match the embedding used for classification in this run.

3. **Transitions**:

   - As you run multiple dates for the same region, `regime_transitions`
     will accumulate transitions; you can later use `RegimeStorage`
     methods and integration tests as a guide for computing empirical
     transition matrices.

This workflow gives you a repeatable way to exercise the numeric Regime
Engine end-to-end while we continue to evolve the underlying models and
prototype configuration.
