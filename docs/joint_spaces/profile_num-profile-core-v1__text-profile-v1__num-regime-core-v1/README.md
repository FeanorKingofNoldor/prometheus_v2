# Joint Space: Profiles – num-profile-core-v1 + text-profile-v1 + num-regime-core-v1

This document describes a planned v0 joint space for **issuer and
country profiles**, built from:

- Numeric profile encoder: `num-profile-core-v1` (384-dim embeddings
  over structured fundamentals and behaviour features).
- Text profile encoder: `text-profile-v1` (384-dim embeddings over
  profile-related text: filings, earnings call segments, narratives).
- Behaviour branch: `num-regime-core-v1` (384-dim regime numeric
  embeddings over medium-horizon return/vol windows).
- Joint model: `joint-profile-core-v1`.

The folder name encodes the ingredients of the space:

- `profile_num-profile-core-v1__text-profile-v1__num-regime-core-v1`
  - `profile` – use case / space type.
  - `num-profile-core-v1` – structured numeric profile branch.
  - `text-profile-v1` – profile text branch.
  - `num-regime-core-v1` – behaviour branch (market behaviour history).

## 1. Goals

This joint space aims to represent issuers/countries by combining:

- **Structural fundamentals** (leverage, growth, quality, profitability,
  etc.).
- **Textual narratives** (filings, call transcripts, governance
  commentary).
- **Behavioural history** (how the entity behaved across different
  regimes).

The result is a 384-dim embedding `z_profile(entity) ∈ R^384` that
supports:

- Finding “profile neighbours” for robustness checks.
- Supporting Universe and Assessment engines with richer context.
- Identifying clusters of fragile or robust issuers.

## 2. Branches

### 2.1 Numeric profile branch – num-profile-core-v1

- Encoder: `num-profile-core-v1`.
- Input: structured fundamentals and behaviour features, e.g.:
  - leverage ratios, coverage ratios,
  - growth and profitability metrics,
  - quality and size factors.
- Output: `z_num_profile(entity, as_of) ∈ R^384`.

In v0, this may be approximated using price-based windows via the
numeric backfill script, but the long-term design is to operate directly
on fundamentals/profile feature tables.

### 2.2 Text profile branch – text-profile-v1

- Encoder: `text-profile-v1`.
- Input: text fields summarising the issuer/country profile, e.g.:
  - filings excerpts,
  - call transcript snippets,
  - profile narratives and governance commentary.
- Output: `z_text_profile(entity, as_of) ∈ R^384`.

Embeddings are stored in `text_embeddings` with
`source_type = 'PROFILE', model_id = 'text-profile-v1'`.

### 2.3 Behaviour branch – num-regime-core-v1

- Encoder: `num-regime-core-v1`.
- Input: numeric windows feeding the Regime Engine, capturing medium-
  horizon return/vol behaviour.
- Output: `z_behaviour(entity, as_of) ∈ R^384`.

This branch captures how the entity behaves under different regimes and
market conditions.

## 3. Joint model – joint-profile-core-v1

The joint model `joint-profile-core-v1` combines the numeric, text, and
behaviour branches into a single profile embedding.

For v0, a simple deterministic construction is acceptable, such as:

- Concatenate available embeddings and apply a linear projection back to
  `R^384`, or
- Compute a weighted average when all branch embeddings are already in
  `R^384`.

Example (weighted average):

```text
z_joint_profile = (w_num * z_num_profile
                   + w_text * z_text_profile
                   + w_beh * z_behaviour)
                  / (w_num + w_text + w_beh)
```

Weights can be tuned based on the relative importance of fundamentals,
text, and behaviour.

## 4. Persistence in `joint_embeddings`

Profile joint embeddings can be stored in `historical_db.joint_embeddings` with:

- `joint_type = 'PROFILE_CORE_V0'` (proposed v0 label).
- `as_of_date` – date associated with the profile snapshot.
- `entity_scope` – JSON describing the profile entity, e.g.:

  ```json
  {
    "entity_type": "ISSUER",
    "entity_id": "ISS_ACME_CORP",
    "region": "US",
    "source": "profile+regime+text",
    "as_of_date": "2025-01-31"
  }
  ```

- `model_id = 'joint-profile-core-v1'`.
- `vector` – `z_joint_profile ∈ R^384` as float32 bytes.

## 5. Relationship to other engines

The profile joint space can support multiple engines:

- **Universe** – favour robust profile clusters, exclude problematic
  clusters.
- **Assessment** – use profile embeddings as part of the context space
  for expected-return models.
- **STAB** – include structural profile risk as a branch in the
  stability/fragility joint space.

## 6. Future work

- Implement `num-profile-core-v1` as a dedicated encoder on
  fundamentals/behaviour features.
- Implement `text-profile-v1` backfill and collect profile text
  embeddings.
- Implement `joint-profile-core-v1` as a real projection head (e.g.
  MLP) rather than a simple average.
- Add backfill and inspection scripts for this space, analogous to the
-  regime and episode joint workflows.
  - The initial v0 backfill script is
    `prometheus.scripts.backfill_joint_profiles`.
