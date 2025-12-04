# Joint Space: Portfolios – num-portfolio-core-v1

This document describes a planned v0 joint space for **portfolio-level
embeddings**, built from:

- Numeric portfolio encoder: `num-portfolio-core-v1`.

The folder name encodes the ingredient of the space:

- `portfolio_num-portfolio-core-v1`

## 1. Goals

The portfolio joint space aims to represent entire portfolios as points
in `R^384`, capturing:

- Holdings structure (weights across assets/sectors/regions).
- Factor exposures and risk characteristics.
- Stability/fragility-related portfolio metrics (if included in the
  encoder).

Use cases include:

- Comparing current portfolios to past portfolios that experienced
  strong performance or large drawdowns.
- Supporting risk dashboards with "distance to known bad states"
  measures at the portfolio level.
- Providing compact portfolio context vectors to Meta-Orchestrator and
  Assessment engines.

## 2. Encoder – num-portfolio-core-v1

- Input: portfolio feature vectors built from:
  - weights (possibly projected into factor/sector buckets),
  - factor exposures and risk stats,
  - summary stability/fragility indicators.
- Output: `z_portfolio(portfolio_id, as_of) ∈ R^384`.

In v0, this encoder can be implemented as a simple linear/MLP projection
from the feature vector to `R^384`.

## 3. Persistence in embeddings tables

Portfolio embeddings can be stored in a dedicated
`numeric_portfolio_embeddings` table or in `numeric_window_embeddings`
with `entity_type = 'PORTFOLIO'` and `model_id = 'num-portfolio-core-v1'`.

Alternatively, a joint-level representation can be stored in
`joint_embeddings` with:

- `joint_type = 'PORTFOLIO_CORE_V0'` (proposed label).
- `as_of_date` – portfolio snapshot date.
- `entity_scope` JSON including `portfolio_id` and metadata.

## 4. Future work

- Define and implement `num-portfolio-core-v1` as a concrete encoder.
- Add backfill and inspection workflows for portfolio embeddings.
- Consider extending this space to include additional branches (e.g.
  linking to `joint-profile-core-v1` and `joint-stab-fragility-v1` for
  portfolio-of-entities representations).
