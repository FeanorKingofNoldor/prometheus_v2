# Dev workflow: joint profile embeddings (joint-profile-core-v1)

This document describes how to build and inspect **joint profile
embeddings** that combine numeric profile, behaviour, and profile text
signals into `R^384` via `joint-profile-core-v1`.

The workflow uses:

- `backfill_numeric_embeddings` – to produce numeric profile embeddings
  (`num-profile-core-v1`).
- `backfill_profile_text_embeddings` – to produce profile text
  embeddings (`text-profile-v1`).
- `backfill_joint_profiles` – to combine numeric + text into joint
  profile embeddings (`PROFILE_CORE_V0`).
- `show_joint_profiles` – to inspect the resulting joint vectors.
- `find_similar_profiles` – to search for issuers with similar joint
  profile embeddings in `PROFILE_CORE_V0`.

## 1. Prerequisites

- Database migrations applied (including `profiles`, `numeric_window_embeddings`,
  `text_embeddings`, and `joint_embeddings`).
- Profiles populated in `runtime_db.profiles` for the issuers of
  interest.
- Numeric windows backfilled for representative instruments (e.g. via the
  regime/profile numeric workflows).
- Text encoder dependencies installed (`transformers`, `torch`).

## 2. Step 1 – Backfill numeric profile embeddings

For a v0 approximation, reuse the numeric window backfill with
`num-profile-core-v1` for a market (e.g. US_EQ):

```bash
python -m prometheus.scripts.backfill_numeric_embeddings \
  --as-of 2025-01-31 \
  --window-days 126 \
  --market-id US_EQ \
  --limit 500 \
  --model-id num-profile-core-v1
```

This writes 384-dim numeric embeddings into `numeric_window_embeddings`
(tagged with `model_id = 'num-profile-core-v1'`).

## 3. Step 2 – Backfill profile text embeddings

Embed profile text for the same date using `text-profile-v1`:

```bash
python -m prometheus.scripts.backfill_profile_text_embeddings \
  --as-of 2025-01-31 \
  --model-id text-profile-v1 \
  --hf-model-name sentence-transformers/all-MiniLM-L6-v2
```

This will:

- Select profile rows from `profiles` with `as_of_date = '2025-01-31'`.
- Build a text document from `structured` fields
  (`business_description`, `risk_summary`, `recent_events_summary`).
- Store 384-dim vectors in `text_embeddings` with
  `source_type = 'PROFILE', model_id = 'text-profile-v1'` and
  `source_id = "{issuer_id}:{as_of_date}"`.

## 4. Step 3 – Build joint profile embeddings

Combine numeric profile + behaviour + profile text into joint profile
embeddings:

```bash
python -m prometheus.scripts.backfill_joint_profiles \
  --as-of 2025-01-31 \
  --numeric-profile-model-id num-profile-core-v1 \
  --behaviour-model-id num-regime-core-v1 \
  --text-model-id text-profile-v1 \
  --joint-model-id joint-profile-core-v1
```

This will, for each issuer with suitable numeric and text embeddings:

- Load numeric profile and (optionally) behaviour embeddings for a
  representative instrument.
- Load the corresponding profile text embedding.
- Combine numeric branches into a single `z_num ∈ R^384`.
- Fuse `z_num` and `z_text` via `SimpleAverageJointModel` into
  `z_joint_profile ∈ R^384`.
- Insert rows into `joint_embeddings` with:
  - `joint_type = 'PROFILE_CORE_V0'`.
  - `model_id = 'joint-profile-core-v1'`.
  - `entity_scope` containing `issuer_id`, `instrument_id`, and
    `as_of_date`.

## 5. Step 4 – Inspect joint profile embeddings

Use the inspection CLI to list joint profile embeddings for a date or
range:

```bash
python -m prometheus.scripts.show_joint_profiles \
  --as-of 2025-01-31 \
  --model-id joint-profile-core-v1 \
  --limit 200
```

Typical output:

```text
as_of_date,issuer_id,instrument_id,model_id,dim,l2_norm
2025-01-31,ISS_ACME_CORP,ACME.US,joint-profile-core-v1,384,11.234567
...
```

You can also filter by `--issuer-id` or use `--start/--end` to inspect a
history of profile embeddings.

## 6. Find similar profiles

Once joint profile embeddings have been backfilled, you can search for
issuers whose profiles are closest to a given issuer in
`PROFILE_CORE_V0` space. For example:

```bash
python -m prometheus.scripts.find_similar_profiles \
  --issuer-id ISS_ACME_CORP \
  --as-of 2025-01-31 \
  --model-id joint-profile-core-v1 \
  --top-k 20
```

This prints a CSV with cosine similarity and Euclidean distance:

```text
cosine,euclidean,issuer_id,instrument_id,region,source
0.993210,0.401234,ISS_PEER_CORP,PEER.US,US,num+text
...
```

You can use this to explore issuer clusters, potential peers, or
universe design candidates based on holistic profile information.

## 7. Notes

- The corresponding joint space is documented in:

  - `docs/joint_spaces/profile_num-profile-core-v1__text-profile-v1__num-regime-core-v1/README.md`.

- This is a v0 developer workflow and can be refined as dedicated
  profile feature tables and numeric encoders become available.
