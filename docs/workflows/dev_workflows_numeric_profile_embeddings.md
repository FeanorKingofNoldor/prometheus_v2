# Dev workflow: numeric profile embeddings (num-profile-core-v1)

This document describes how to backfill **numeric profile embeddings**
using the `num-profile-core-v1` encoder model via the generic numeric
backfill script or a dedicated profile encoder script.

The goal is to produce 384-dim numeric embeddings for issuer/country
profiles based on structured fundamentals and behaviour metrics.

## 1. Prerequisites

- Tables containing numeric profile features, e.g. `fundamentals_daily`,
  `profile_factors`, or a denormalised `issuer_profile_features` view,
  with at least:
  - `entity_type` (e.g. `ISSUER`, `COUNTRY`).
  - `entity_id` (e.g. `issuer_id`, `country_code`).
  - `as_of_date`.
  - A feature vector (columns or JSON) representing ratios, leverage,
    growth, quality metrics, etc.
- `numeric_window_embeddings` or a dedicated `numeric_profile_embeddings`
  table available in `historical_db`.

## 2. v0 approach via numeric window backfill

For a simple v0 approximation, you can:

- Treat `num-profile-core-v1` as applying the same window logic as
  `num-regime-core-v1` but keyed on a representative instrument per
  issuer/country (e.g. the primary equity).
- Use `backfill_numeric_embeddings` with `model_id = 'num-profile-core-v1'`.

Example:

```bash
python -m prometheus.scripts.backfill_numeric_embeddings \
  --as-of 2025-01-31 \
  --window-days 126 \
  --market-id US_EQ \
  --limit 500 \
  --model-id num-profile-core-v1
```

This yields 384-dim embeddings `z_profile(entity, as_of)` in
`numeric_window_embeddings` tagged with `model_id = 'num-profile-core-v1'`.

## 3. Future dedicated profile encoder

In a more refined version, `num-profile-core-v1` should:

- Operate on structured fundamentals/features rather than price windows.
- Read from profile feature tables, not `prices_daily`.
- Persist into a dedicated embeddings table or reuse
  `numeric_window_embeddings` with a different `entity_type`.

A dedicated script `backfill_numeric_profile_embeddings.py` could then:

- Iterate over issuers/countries.
- Build feature vectors for each as of `as_of_date`.
- Apply a 384-dim encoder (linear/MLP) to produce `z_profile`.
- Store results with `entity_type = 'ISSUER'` or `COUNTRY`,
  `model_id = 'num-profile-core-v1'`.

## 4. Notes

- The primary consumer joint space for these embeddings is the profile
  joint space documented in:

  - `docs/joint_spaces/profile_num-profile-core-v1__text-profile-v1__num-regime-core-v1/README.md`.

- For now, this workflow is a placeholder; once the profile feature
  pipeline and encoder are implemented, update this document with actual
  commands and schema details.
