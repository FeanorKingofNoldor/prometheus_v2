# Dev workflow: joint portfolio embeddings (joint-portfolio-core-v1)

This document describes how to build and inspect **joint portfolio
embeddings** that represent whole portfolios as 384-dim vectors in
`R^384` via `joint-portfolio-core-v1`.

The underlying joint space is specified in:


## 1. Prerequisites

Before building joint portfolio embeddings, you should have:

- Portfolio risk reports populated in `runtime_db.portfolio_risk_reports`.
- Numeric portfolio embeddings (`num-portfolio-core-v1`) populated via
  `backfill_numeric_portfolio_embeddings` into
  `numeric_window_embeddings` with `entity_type = 'PORTFOLIO'`.

## 2. Backfill numeric portfolio embeddings

Use the numeric portfolio backfill CLI to create 384-dim numeric
embeddings for portfolios on a given date:

```bash
python -m prometheus.scripts.backfill_numeric_portfolio_embeddings \
  --as-of 2025-01-31 \
  --model-id num-portfolio-core-v1 \
  --limit 100
```

This will:

- Read up to 100 rows from `portfolio_risk_reports` for `as_of=2025-01-31`.
- Build deterministic feature vectors from `risk_metrics`,
  `exposures_by_sector`, and `exposures_by_factor`.
- Encode them into 384-dim embeddings with `num-portfolio-core-v1` and
  store them in `numeric_window_embeddings` with
  `entity_type='PORTFOLIO'`.

## 3. Backfill joint portfolio embeddings

Convert numeric portfolio embeddings into joint portfolio embeddings in
`joint_embeddings`:

```bash
python -m prometheus.scripts.backfill_joint_portfolios \
  --as-of 2025-01-31 \
  --numeric-model-id num-portfolio-core-v1 \
  --joint-model-id joint-portfolio-core-v1 \
  --limit 100
```

This will:

1. Load numeric portfolio embeddings from `numeric_window_embeddings`
   where:
   - `entity_type = 'PORTFOLIO'`.
   - `model_id = 'num-portfolio-core-v1'`.
   - `as_of_date = 2025-01-31`.
2. For each `(portfolio_id, as_of_date)`:
   - Construct a `JointExample` with:
     - `joint_type = 'PORTFOLIO_CORE_V0'`.
     - `entity_scope` including `entity_type='PORTFOLIO'`,
       `portfolio_id`, and `as_of_date`.
     - `numeric_embedding = z_portfolio`.
3. Use `IdentityNumericJointModel` and `JointEmbeddingService` to write
   384-dim joint vectors into `joint_embeddings` with
   `model_id = 'joint-portfolio-core-v1'`.


Use the inspection CLI to list joint portfolio embeddings for a date or
range:

```bash
python -m prometheus.scripts.show_joint_portfolios \
  --as-of 2025-01-31 \
  --model-id joint-portfolio-core-v1 \
  --limit 200
```

You can also filter by `portfolio_id` and/or use `--start/--end` to look
at a history of portfolio states:

```bash
python -m prometheus.scripts.show_joint_portfolios \
  --portfolio-id PORTFOLIO_CORE_US_EQ_001 \
  --start 2025-01-01 --end 2025-12-31 \
  --model-id joint-portfolio-core-v1
```

Typical output:

```text
as_of_date,portfolio_id,model_id,dim,l2_norm
2025-01-31,PORTFOLIO_CORE_US_EQ_001,joint-portfolio-core-v1,384,8.765432
...
```

## 5. Find similar portfolios
+
+Once joint portfolio embeddings have been backfilled, you can search for
+portfolios whose joint representation is most similar to a given
+portfolio on a date. For example:
+
+```bash
+python -m prometheus.scripts.find_similar_portfolios \
+  --portfolio-id PORTFOLIO_CORE_US_EQ_001 \
+  --as-of 2025-01-31 \
+  --model-id joint-portfolio-core-v1 \
+  --top-k 20
+```
+
+This prints a CSV with cosine similarity and Euclidean distance:
+
+```text
+cosine,euclidean,portfolio_id,source
+0.991234,0.345678,PORTFOLIO_CORE_US_EQ_007,num-portfolio-core-v1
+...
+```
+
+You can use this to explore historical portfolio states that resemble a
+current portfolio configuration, for example when analysing drawdowns or
+stress periods.
+
+## 6. Notes

- This v0 joint space is effectively an identity projection over
  `num-portfolio-core-v1`; the joint model is `IdentityNumericJointModel`.
- Over time, `joint-portfolio-core-v1` can be upgraded to a learned or
  hand-crafted projection that also incorporates additional branches
  (e.g. aggregated profile/STAB features) while preserving the same
  interface.
- Once populated, joint portfolio embeddings can be used by Meta and
  Monitoring components to:
  - compare current portfolios to historical ones,
  - search for past portfolios with similar risk/return profiles,
  - visualise portfolio states in a low-dimensional map (via PCA/UMAP
    over the joint vectors).
