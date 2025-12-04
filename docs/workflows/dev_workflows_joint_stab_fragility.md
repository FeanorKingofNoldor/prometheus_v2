# Dev workflow: joint stability/fragility embeddings (joint-stab-fragility-v1)

This document describes how to build and inspect **joint
stability/fragility embeddings** for instruments using numeric stability
embeddings and optional structural profiles.

The workflow uses:

- `backfill_numeric_embeddings` – to produce numeric stability
  embeddings (`num-stab-core-v1`).
- `backfill_joint_profiles` – to provide structural profile embeddings
  (`joint-profile-core-v1`) as an optional branch.
- `backfill_joint_stab_fragility_states` – to combine stability + profile
  into joint STAB embeddings (`STAB_FRAGILITY_V0`).
- `show_joint_stab_fragility_states` – to inspect the resulting joint
  vectors.

## 1. Prerequisites

- Database migrations applied (including `numeric_window_embeddings` and
  `joint_embeddings`).
- Price history and numeric windows available for the instruments in
  your market (e.g. US_EQ).
- Profiles and joint profiles backfilled if you want to include the
  profile branch.

## 2. Step 1 – Backfill numeric stability embeddings

For v0, reuse the numeric window backfill with `num-stab-core-v1` for a
market (e.g. US_EQ):

```bash
python -m prometheus.scripts.backfill_numeric_embeddings \
  --as-of 2025-01-31 \
  --window-days 63 \
  --market-id US_EQ \
  --limit 500 \
  --model-id num-stab-core-v1
```

This writes 384-dim stability embeddings into `numeric_window_embeddings`
(tagged with `model_id = 'num-stab-core-v1'`).

## 3. (Optional) Step 2 – Ensure joint profiles are available

If you want to include structural profile risk in the STAB joint space,
run the joint profile workflow (see
`docs/dev_workflows_joint_profiles.md`) so that `PROFILE_CORE_V0`
embeddings exist for your issuers on the same `as_of` date.

## 4. Step 3 – Build joint STAB/fragility embeddings

Combine stability + (optional) profile embeddings into joint
STAB/fragility vectors:

```bash
python -m prometheus.scripts.backfill_joint_stab_fragility_states \
  --as-of 2025-01-31 \
  --market-id US_EQ \
  --stab-model-id num-stab-core-v1 \
  --profile-joint-model-id joint-profile-core-v1 \
  --joint-model-id joint-stab-fragility-v1 \
  --region US
```

This will, for each instrument:

- Load `num-stab-core-v1` embeddings from `numeric_window_embeddings`.
- Optionally load `joint-profile-core-v1` embeddings for the
  corresponding issuer.
- Combine numeric branches into `z_num ∈ R^384`.
- Pass `z_num` through `IdentityNumericJointModel` into
  `joint-stab-fragility-v1`.
- Insert rows into `joint_embeddings` with:
  - `joint_type = 'STAB_FRAGILITY_V0'`.
  - `model_id = 'joint-stab-fragility-v1'`.
  - `entity_scope` containing `entity_id` (instrument_id), optional
    `issuer_id`, `region`, and `as_of_date`.

## 5. Step 4 – Inspect joint STAB/fragility embeddings

Use the inspection CLI to list joint STAB embeddings for a date or
range:

```bash
python -m prometheus.scripts.show_joint_stab_fragility_states \
  --as-of 2025-01-31 \
  --model-id joint-stab-fragility-v1 \
  --limit 200
```

Typical output:

```text
as_of_date,instrument_id,issuer_id,region,model_id,dim,l2_norm
2025-01-31,AAA.US,ISS_ACME_CORP,US,joint-stab-fragility-v1,384,9.876543
...
```

You can also filter by `--instrument-id`, `--region`, or use
`--start/--end` to explore a history of stability/fragility states.

## 6. Notes

- The corresponding joint space is documented in:

  - `docs/joint_spaces/stab_num-stab-core-v1__num-scenario-core-v1__joint-profile-core-v1/README.md`.

- Scenario-based embeddings using `num-scenario-core-v1` can be
  constructed with:

  ```bash
  python -m prometheus.scripts.backfill_joint_stab_fragility_scenarios \
    --scenario-set-id SET_ABC123 \
    --scenario-model-id num-scenario-core-v1 \
    --joint-model-id joint-stab-fragility-v1 \
    --limit 100
  ```

  which projects numeric scenario embeddings into the same
  `STAB_FRAGILITY_V0` joint space with `entity_type="SCENARIO"` in the
  `entity_scope`. This provides a first v0 scenario branch for
  stability/fragility analysis.

- To inspect scenario-level STAB embeddings, use:

  ```bash
  python -m prometheus.scripts.show_joint_stab_fragility_scenarios \
    --scenario-set-id SET_ABC123 \
    --model-id joint-stab-fragility-v1 \
    --limit 200
  ```

- To find scenarios whose joint STAB embeddings are closest to an
  instrument's STAB state, use:

  ```bash
  python -m prometheus.scripts.find_similar_stab_scenarios \
    --instrument-id AAA.US \
    --as-of 2025-01-31 \
    --model-id joint-stab-fragility-v1 \
    --scenario-set-id SET_ABC123 \
    --top-k 20
  ```
