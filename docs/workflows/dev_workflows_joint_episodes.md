# Dev workflow: joint episode embeddings

This document describes how to build **joint episode embeddings** that
combine numeric regime embeddings (`num-regime-core-v1`) with NEWS text
embeddings (`text-fin-general-v1`) into an `R^384` episode space via
`joint-episode-core-v1`.

Episodes are defined externally in a JSON file and used by the
`backfill_joint_episode_context` script to populate the
`joint_embeddings` table with `joint_type = 'EPISODE_V0'`.

## 1. Prerequisites

- Regime Engine has been run for the relevant `region`/date windows so
  that `runtime_db.regimes` contains `regime_embedding` rows
  (`num-regime-core-v1`, 384-dim).
- NEWS text embeddings have been backfilled for those windows using
  `text-fin-general-v1` and stored in `text_embeddings`.
- Episodes are defined in a JSON file as described below.

## 2. Define episodes in JSON

Create a JSON file (e.g. `episodes_example.json`) containing a list of
episodes:

```json
[
  {
    "episode_id": "EP_COVID_LIQ_2020",
    "label": "COVID Liquidity 2020",
    "region": "US",
    "start_date": "2020-02-20",
    "end_date": "2020-04-15"
  },
  {
    "episode_id": "EP_FOMC_2022_06",
    "label": "FOMC Hike Panic 2022-06",
    "region": "US",
    "start_date": "2022-06-10",
    "end_date": "2022-06-25"
  }
]
```

Each object must contain:

- `episode_id` – unique identifier.
- `label` – descriptive label (used in `entity_scope`).
- `region` – must match the `region` values in the `regimes` table.
- `start_date`, `end_date` – inclusive YYYY-MM-DD date range.

## 3. Backfill joint episode embeddings

From the project root (`prometheus_v2`), run:

```bash
python -m prometheus.scripts.backfill_joint_episode_context \
  --episodes-file episodes_example.json \
  --text-model-id text-fin-general-v1 \
  --joint-model-id joint-episode-core-v1 \
  --language EN
```

This will, for each episode:

1. Load all `regime_embedding` vectors for the episode's `region` and
   date window from `regimes`.
2. Compute an episode-level numeric embedding by averaging regime
   embeddings in `R^384`.
3. Load all `NEWS` text embeddings from `text_embeddings` joined with
   `news_articles` for the same date window, `source_type='NEWS'`, and
   `model_id = 'text-fin-general-v1'` (optionally filtered by
   `language`).
4. Compute an episode-level text embedding by averaging these vectors in
   `R^384`.
5. Use `SimpleAverageJointModel` to compute a joint episode embedding
   in `R^384`.
6. Insert a row into `joint_embeddings` with:
   - `joint_type = 'EPISODE_V0'`.
   - `model_id = 'joint-episode-core-v1'`.
   - `as_of_date = end_date` of the episode.
   - `entity_scope` containing `episode_id`, `label`, `region`, and the
     `start_date`/`end_date` window.

## 4. Inspecting joint episodes

You can inspect stored joint episode embeddings directly via SQL, for
example:

```sql
SELECT as_of_date, entity_scope, model_id, octet_length(vector) AS bytes
FROM joint_embeddings
WHERE joint_type = 'EPISODE_V0'
  AND model_id = 'joint-episode-core-v1';
```

- `bytes` should be `384 * 4 = 1536` for 384-dim `float32` vectors.
- `entity_scope` will show `episode_id`, `label`, `region`, and
  `window`.

For more detailed analysis, you can export rows to a CSV and decode
`vector` using NumPy in a notebook.

## 5. Notes

- This is a v0 developer workflow. As episode definitions and joint
  models evolve, the same `joint-episode-core-v1` space and folder
  (`episode_num-regime-core-v1__text-fin-general-v1`) will remain the
  canonical specification for this joint space.
- The corresponding joint space specification is documented in:

  - `docs/joint_spaces/episode_num-regime-core-v1__text-fin-general-v1/README.md`.
