# Joint Space: Assessment Context – joint-profile-core-v1 + joint-regime-core-v1 + joint-stab-fragility-v1 + text-fin-general-v1

This document describes a planned v0 joint space for **Assessment
context vectors**, built from:

- `joint-profile-core-v1` – structural issuer/country profiles.
- `joint-regime-core-v1` – joint regime context (numeric + text).
- `joint-stab-fragility-v1` – stability/fragility joint space.
- `text-fin-general-v1` – recent financial text/news context.

The folder name encodes the ingredients of the space:

- `assessment_joint-profile-core-v1__joint-regime-core-v1__joint-stab-fragility-v1__text-fin-general-v1`

## 1. Goals

The Assessment Context joint space aims to provide **compact, expressive
context vectors** as features for expected-return models and other
Assessment components. Each embedding summarises:

- The entity's **structural profile**.
- The current **regime** and macro backdrop.
- The current **stability/fragility** state.
- Recent **financial text** signals.

These embeddings can be used as inputs to ML models (trees, MLPs) or as
conditioning variables for simpler numeric models.

## 2. Branches

### 2.1 Profile context – joint-profile-core-v1

- Input: `z_profile(entity, as_of) ∈ R^384` from the profile joint space.

### 2.2 Regime context – joint-regime-core-v1

- Input: `z_regime_context(region, as_of) ∈ R^384` from the regime joint
  space (`REGIME_CONTEXT_V0`).

### 2.3 Stability/fragility context – joint-stab-fragility-v1

- Input: `z_stab(entity, as_of) ∈ R^384` from the stability/fragility
  joint space.

### 2.4 Recent text context – text-fin-general-v1

- Input: `z_text_recent(entity or region, as_of) ∈ R^384` built from
  recent financial/news text (e.g. last 7–30 days) using
  `text-fin-general-v1`.

## 3. Joint model – joint-assessment-context-v1

The joint model `joint-assessment-context-v1` combines the four context
branches into a single 384-dim embedding:

```text
z_assessment = f( z_profile, z_regime_ctx, z_stab, z_text_recent ) ∈ R^384
```

For v0, an acceptable construction is:

- Concatenate available context vectors and apply a linear/MLP
  projection back to `R^384`, or
- Compute a weighted average when all branches are in `R^384` and
  present for a given entity.

Example (weighted average):

```text
z_assessment = (w_prof * z_profile
                + w_reg  * z_regime_ctx
                + w_stab * z_stab
                + w_text * z_text_recent)
               / (w_prof + w_reg + w_stab + w_text)
```

## 4. Persistence in `joint_embeddings`

Assessment context embeddings can be stored in `historical_db.joint_embeddings` with:

- `joint_type = 'ASSESSMENT_CTX_V0'` (proposed label).
- `as_of_date` – date of the context snapshot.
- `entity_scope` – JSON describing the entity and context, e.g.:

  ```json
  {
    "entity_type": "INSTRUMENT",
    "entity_id": "AAA.US",
    "region": "US",
    "source": "profile+regime+stab+text",
    "as_of_date": "2025-01-31"
  }
  ```

- `model_id = 'joint-assessment-context-v1'`.
- `vector` – `z_assessment ∈ R^384` as float32 bytes.

## 5. Use in Assessment Engine

Assessment engines can use `z_assessment` as:

- A direct feature vector for expected-return models per entity.
- A conditioning context to modulate parameters of simpler numeric
  models (e.g. risk premia by region/regime cluster).

Over time, the same context space can be reused across different
horizons and strategies, simplifying feature engineering.

## 6. Future work

- Implement an initial `joint-assessment-context-v1` model (e.g. linear
  projection) and backfill script to populate Assessment Context
  embeddings.
- Add inspection tools to visualise and debug context embeddings
  (nearest neighbours, cluster plots, etc.).
- Integrate context embeddings into Assessment engine pipelines once
  basic performance and stability are validated.
