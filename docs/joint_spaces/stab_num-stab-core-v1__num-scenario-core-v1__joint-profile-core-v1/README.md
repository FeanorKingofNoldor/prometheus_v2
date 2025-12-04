# Joint Space: Stability/Fragility – num-stab-core-v1 + num-scenario-core-v1 + joint-profile-core-v1

This document describes a planned v0 joint space for **stability and
fragility** states and scenarios, built from:

- Numeric stability encoder: `num-stab-core-v1` (384-dim embeddings for
  stability-related numeric windows).
- Numeric scenario encoder: `num-scenario-core-v1` (384-dim embeddings
  for synthetic/historical shock scenarios).
- Optional profile branch: `joint-profile-core-v1` (cross-modal issuer
  profile embeddings) to capture structural risk.
- Joint model: `joint-stab-fragility-v1`.

The folder name encodes the ingredients of the space:

- `stab_num-stab-core-v1__num-scenario-core-v1__joint-profile-core-v1`
  - `stab` – use case / space type (Stability/Soft Target / fragility).
  - `num-stab-core-v1` – numeric stability branch.
  - `num-scenario-core-v1` – scenario/shock branch.
  - `joint-profile-core-v1` – optional profile structural risk branch.

## 1. Goals

This joint space aims to represent:

- **Stability/fragility states** of entities (instruments, issuers,
  markets),
- **Shock scenarios** (synthetic or historical), and
- **Structural profiles** of those entities

in a common `R^384` space where:

- Entities that become fragile in similar ways under stress live near
each other.
- Scenarios that produce similar patterns of instability live near each
other.
- Distances between current states, scenarios, and profiles give a
quantitative notion of "how close we are to known bad regions".

## 2. Branches

### 2.1 Numeric stability branch – num-stab-core-v1

- Encoder: `num-stab-core-v1`.
- Input: numeric windows and/or engineered stability features per
  entity, e.g.:
  - realised volatility paths,
  - drawdown history,
  - liquidity/volume metrics.
- Output: `z_stab(entity, as_of) ∈ R^384`.

For v0, `num-stab-core-v1` may share the same basic window features as
`num-regime-core-v1` but is wired through separate model_id and
calibration to allow later specialisation.

### 2.2 Scenario branch – num-scenario-core-v1

- Encoder: `num-scenario-core-v1`.
- Input: standardised scenario shock vectors or path shapes (e.g. shocks
  to prices, spreads, vols over a fixed horizon).
- Output: `z_scenario(scenario_id) ∈ R^384`.

This branch allows both synthetic and historical scenarios to be
represented as points in the same space as stability states.

### 2.3 Optional profile branch – joint-profile-core-v1

- Encoder: `joint-profile-core-v1`.
- Input: joint profile embeddings combining fundamentals,
  behaviour, and text (`text-profile-v1`).
- Output: `z_profile(entity) ∈ R^384`.

This branch captures slow-moving structural risk factors (leverage,
quality, governance, etc.) so that entities with inherently fragile
profiles are positioned appropriately in the space.

## 3. Joint model – joint-stab-fragility-v1

The joint model `joint-stab-fragility-v1` combines the branches above
into a single stability/fragility representation.

For v0, a simple construction is acceptable, such as:

- Concatenate available branch embeddings and apply a linear projection
  back to `R^384`, or
- Compute a weighted average in `R^384` when all branches already live
  in the same dimension.

Example (weighted average) when all branches are present:

```text
z_joint = (w_stab * z_stab + w_scen * z_scenario + w_prof * z_profile)
          / (w_stab + w_scen + w_prof)
```

Weights (`w_stab`, `w_scen`, `w_prof`) can be tuned based on how much we
trust each branch for a given use case.

## 4. Persistence in `joint_embeddings`

Each stability/fragility joint embedding would be stored as a row in
`historical_db.joint_embeddings` with:

- `joint_type = 'STAB_FRAGILITY_V0'` (proposed v0 label).
- `as_of_date` – date associated with the state or scenario.
- `entity_scope` – JSON carrying details, e.g.:

  - For an entity stability state:

    ```json
    {
      "entity_type": "INSTRUMENT",
      "entity_id": "AAA.US",
      "region": "US",
      "source": "stab+scenarios+profile",
      "stab_window": {"start_date": "2025-01-01", "end_date": "2025-01-31"}
    }
    ```

  - For a scenario-only embedding:

    ```json
    {
      "scenario_id": "SCN_HY_SPREAD_WIDEN_2008",
      "source": "scenarios",
      "metadata": {"shock_type": "CREDIT_SPREAD", "severity": "HIGH"}
    }
    ```

- `model_id = 'joint-stab-fragility-v1'`.
- `vector` – `z_joint ∈ R^384` as float32 bytes.

## 5. Relationship to STAB engine

The STAB engine (Stability / Soft Target Engine) can:

- Produce stability vectors and soft-target states for entities.
- Optionally project these into the joint stability/fragility space via
  this joint model, either:
  - in an offline job for analysis, or
  - as an additional embedding attached to entities for use by
    Assessment, Black Swan, or Meta engines.

In v0, this joint space is primarily a **research/analysis tool**;
later, it can become an input feature for other engines once trained or
calibrated.

## 6. Future work

- Implement `num-stab-core-v1` and `num-scenario-core-v1` concretely as
  separate numeric encoders producing 384-dim embeddings.
- Design and train (or calibrate) `joint-stab-fragility-v1` beyond a
  simple average, e.g. using contrastive/objective losses that bring
  fragile states close to relevant scenarios.
- Add backfill scripts analogous to `backfill_joint_regime_context` and
-  `backfill_joint_episode_context` for populating this space with:
-  - current stability states,
-  - historical stress events,
-  - synthetic scenarios.
- The initial v0 backfill for **entity stability states** is provided by
-  `prometheus.scripts.backfill_joint_stab_fragility_states`.
- Integrate these embeddings into the STAB engine outputs and
-  downstream consumers.
