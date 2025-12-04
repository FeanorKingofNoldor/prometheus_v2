# Joint Space: Episodes – num-regime-core-v1 + text-fin-general-v1

This document describes a planned v0 joint space for **episodes**
(crisis/event windows), built from:

- Numeric encoder: `num-regime-core-v1` (384-dim regime numeric
  embeddings on daily windows).
- Text encoder: `text-fin-general-v1` (384-dim financial/news text
  embeddings).
- Joint model: `joint-episode-core-v1` (initially implemented via
  `SimpleAverageJointModel`).

The folder name encodes the ingredients of the space:

- `episode_num-regime-core-v1__text-fin-general-v1`
  - `episode` – use case / space type.
  - `num-regime-core-v1` – numeric branch model_id.
  - `text-fin-general-v1` – text branch model_id.

## 1. Concept

An **episode** is a tagged event window, such as a crisis, policy
intervention, or major dislocation. Each episode is described by at
least:

- `episode_id` – unique identifier.
- `label` – short human-readable name (e.g. `COVID_LIQ_2020`).
- `region` – e.g. `US`, `EU`, `GLOBAL`.
- `start_date`, `end_date` – inclusive date range for the episode.
- `metadata` – JSON with additional tags (severity, type, notes, etc.).

The goal of this joint space is to represent each episode as a single
vector in `R^384` that captures both:

- Numeric **behaviour** of markets around the episode.
- Text **narrative** (news, commentary, policy statements) during the
  same window.

## 2. Numeric branch – Episode-level regime embedding

### 2.1 Source

- Base numeric encoder: `num-regime-core-v1` (384-dim) used by
  `NumericRegimeModel`.
- For a given `(region, date)` the Regime Engine produces a
  `regime_embedding ∈ R^384` stored in `runtime_db.regimes`.

### 2.2 Episode aggregation

For a given episode `(episode_id, region, start_date, end_date)`:

1. Collect daily regime embeddings for all trading days `t` in the
   window:

   - Query `regimes` for rows with `region = <region>` and
     `start_date <= as_of_date <= end_date`.
   - Decode `regime_embedding` as `z_regime(t) ∈ R^384`.

2. Aggregate into a single **episode-level numeric embedding**:

   - v0 rule: simple arithmetic mean over the window:

     ```text
     z_num_episode = mean_t z_regime(t) ∈ R^384
     ```

   - Future variants may use pre/during/post windows with different
     weights, but v0 uses a single mean for clarity.

## 3. Text branch – Episode-level NEWS embedding

### 3.1 Source

- Base text encoder: `text-fin-general-v1` (384-dim), with embeddings
  stored in `historical_db.text_embeddings`.
- Relevant tables:
  - `text_embeddings` with `source_type = 'NEWS'` and
    `model_id = 'text-fin-general-v1'`.
  - `news_articles` providing `published_at` and `language`.

### 3.2 Episode aggregation

For the same `(episode_id, region, start_date, end_date)`:

1. Select NEWS articles whose `published_at` lies in the window, e.g.:

   - `start_date <= DATE(published_at) <= end_date`.
   - Optional filter by `language` (e.g. `EN`).

2. Join to `text_embeddings` and collect vectors `v_i ∈ R^384` for all
   matching articles.

3. Aggregate into a **single episode-level text embedding**:

   - v0 rule: simple mean across articles:

     ```text
     z_text_episode = mean_i v_i ∈ R^384
     ```

   - Future variants may weight articles by importance or source.

If no text embeddings are available for the episode window, that episode
is skipped by the joint backfill script.

## 4. Joint model – SimpleAverageJointModel

For v0, the episode joint space uses the same simple joint model as the
regime context space:

- Implementation: `SimpleAverageJointModel` from
  `prometheus.encoders.models_joint_simple`.
- Inputs per episode:
  - `z_num_episode ∈ R^384`.
  - `z_text_episode ∈ R^384`.
- Output:

  ```text
  z_joint_episode = (w_num * z_num_episode + w_text * z_text_episode) / (w_num + w_text)
  ```

- Initial weights:
  - `numeric_weight = 0.5`.
  - `text_weight = 0.5`.

Thus each episode is mapped to `z_joint_episode ∈ R^384` in the
`joint-episode-core-v1` space.

## 5. Persistence in `joint_embeddings`

Each episode joint embedding is stored as one row in
`historical_db.joint_embeddings` with:

- `joint_type = 'EPISODE_V0'`.
- `as_of_date` – canonical date for the episode (v0: typically
  `end_date` or `start_date`, to be documented in the backfill script).
- `entity_scope` – JSON describing the episode, e.g.:

  ```json
  {
    "episode_id": "EP_COVID_LIQ_2020",
    "label": "COVID_Liquidity_2020",
    "region": "US",
    "window": {"start_date": "2020-02-20", "end_date": "2020-04-15"},
    "source": "regime+news"
  }
  ```

- `model_id = 'joint-episode-core-v1'`.
- `vector` – `z_joint_episode` as float32 bytes.
- `vector_ref = NULL` (for now).

## 6. Backfill workflow (planned)

A future script `prometheus.scripts.backfill_joint_episode_context`
will:

1. Iterate over episodes from a configured source (e.g. an `episodes`
   table or static config file).
2. For each episode, compute `z_num_episode` and `z_text_episode` as
   described above.
3. Use `SimpleAverageJointModel` to compute `z_joint_episode`.
4. Persist rows into `joint_embeddings` with
   `joint_type = 'EPISODE_V0'` and `model_id = 'joint-episode-core-v1'`.

The exact CLI shape will mirror `backfill_joint_regime_context`, with
options to:

- Filter by episode_id / region.
- Restrict to a subset of episode date ranges.
- Choose `language` and text `model_id` if needed.

## 7. Future evolution

Later iterations may:

- Replace the simple average joint model with a learned projection while
  preserving this folder and model_id.
- Add additional branches (e.g. macro-only text, factor-based numeric
  encoders) in new spaces with names that enumerate all ingredients, e.g.:

  - `episode_num-regime-core-v1__num-scenario-core-v1__text-fin-general-v1`.

This document is the single source of truth for what goes into
`joint-episode-core-v1` and how episode embeddings are constructed in
v0.
