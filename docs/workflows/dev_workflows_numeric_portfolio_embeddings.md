# Dev workflow: numeric portfolio embeddings (num-portfolio-core-v1)

This document describes a planned workflow for backfilling **numeric
portfolio embeddings** using the `num-portfolio-core-v1` encoder model.

The goal is to represent whole portfolios as 384-dimensional vectors in
`R^384` based on holdings, factor exposures, and risk characteristics.

## 1. Prerequisites

- A table or view containing portfolio snapshots and features, e.g.
  `portfolio_snapshots` or `portfolio_features`, with at least:
  - `portfolio_id`.
  - `as_of_date`.
  - Weight vector or aggregate features (factor exposures, sector/region
    breakdown, risk metrics, etc.).
- A target embeddings table, e.g. `numeric_portfolio_embeddings` or
  reuse of `numeric_window_embeddings` with
  `entity_type = 'PORTFOLIO'`.

## 2. v0 encoder behaviour

`num-portfolio-core-v1` is defined as a 384-dim encoder that:

- Takes a portfolio feature vector (e.g. flattened factor exposures,
  risk stats, concentration measures).
- Applies a deterministic mapping (linear layer or small MLP) to produce
  `z_portfolio(portfolio_id, as_of) ∈ R^384`.

In a simple v0 implementation, this encoder can:

- Flatten the feature vector and pad/truncate to 384 dims, or
- Use a fixed linear projection initialised from a stable seed.

## 3. Run a numeric portfolio backfill using num-portfolio-core-v1

Use the dedicated backfill script `backfill_numeric_portfolio_embeddings.py`:

```bash
python -m prometheus.scripts.backfill_numeric_portfolio_embeddings \
  --as-of 2025-01-31 \
  --model-id num-portfolio-core-v1 \
  --limit 100
```

This will:

- Select up to 100 portfolios with risk reports at `2025-01-31` from
  `portfolio_risk_reports`.
- Build feature vectors from `risk_metrics`, `exposures_by_sector`, and
  `exposures_by_factor` JSON fields.
- Encode them into 384-dim embeddings with `num-portfolio-core-v1`
  (via `PadToDimNumericEmbeddingModel`).
- Store results into `numeric_window_embeddings` with
  `entity_type = 'PORTFOLIO'` and
  `model_id = 'num-portfolio-core-v1'`.
## 4. Notes

- The portfolio joint space using these embeddings is documented in:

  - `docs/joint_spaces/portfolio_num-portfolio-core-v1/README.md`.

- For an end-to-end example that goes from portfolio risk reports →
  numeric portfolio embeddings → joint portfolio embeddings, see:

  - `docs/dev_workflows_joint_portfolios.md`.
