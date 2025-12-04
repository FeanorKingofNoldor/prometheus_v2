# Dev workflow: profile text embeddings (text-profile-v1)

This document describes how to backfill **profile text embeddings** for
issuer/country profiles using the `text-profile-v1` encoder model.

The goal is to produce 384-dim embeddings for profile-related text
(filings, earnings calls, profile narratives) for use in the
`joint-profile-core-v1` and related spaces.

## 1. Prerequisites

- Table(s) containing profile text, e.g. `profiles_text` or
  `issuer_profiles`, with at least:
  - `profile_id` or `issuer_id`
  - `as_of_date` or `updated_at`
  - `text` (concatenated filings, call excerpts, narratives), or
    `headline` + `body` fields that can be concatenated.
- `text_embeddings` table available in `historical_db`.
- `transformers` and `torch` installed for running the text encoder.

## 2. Decide on profile source and logical IDs

For v0 this workflow uses the runtime `profiles` table as the source and
maps rows into `text_embeddings` as:

- `source_type = 'PROFILE'`.
- `source_id` = `"{issuer_id}:{as_of_date}"` (e.g. `"ISS_ACME:2025-01-31"`).

This convention matches the current runtime schema
(`issuer_id + as_of_date` as the natural key) and can be revised later if
you introduce a dedicated `profiles_text` or `issuer_profiles` table.

## 3. Run a profile text backfill using text-profile-v1

Use the dedicated backfill script:

```bash
python -m prometheus.scripts.backfill_profile_text_embeddings \
  --as-of 2025-01-31 \
  --model-id text-profile-v1
```

This should:

- Select profile rows as of `2025-01-31`.
- Embed their text using `text-profile-v1` (384-dim, same base model
  family as `text-fin-general-v1`).
- Store vectors into `text_embeddings` with
  `source_type = 'PROFILE', model_id = 'text-profile-v1'`.

## 4. Inspecting profile text embeddings

Check that profile embeddings were written correctly:

```sql
SELECT source_type, model_id, COUNT(*) AS n, 
       MIN(octet_length(vector)) AS min_bytes,
       MAX(octet_length(vector)) AS max_bytes
FROM text_embeddings
WHERE source_type = 'PROFILE'
  AND model_id = 'text-profile-v1'
GROUP BY source_type, model_id;
```

- `min_bytes` and `max_bytes` should both be `384 * 4 = 1536` if the
  encoder outputs 384-dim `float32` vectors.

## 5. Notes

- The corresponding joint space that will consume these embeddings is
  documented in:

  - `docs/joint_spaces/profile_num-profile-core-v1__text-profile-v1__num-regime-core-v1/README.md`.

- For now, this workflow is a placeholder until the profile text
  backfill script is implemented; once that script exists, update this
  document with its actual CLI and options.
