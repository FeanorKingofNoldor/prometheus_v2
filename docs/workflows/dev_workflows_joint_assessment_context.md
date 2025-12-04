# Dev workflow: joint assessment context embeddings (joint-assessment-context-v1)

This document describes how to backfill and inspect **Assessment context
embeddings** that combine profile, regime, stability, and recent text
context into `R^384` via `joint-assessment-context-v1`.

The underlying joint space is specified in:

- `docs/joint_spaces/assessment_joint-profile-core-v1__joint-regime-core-v1__joint-stab-fragility-v1__text-fin-general-v1/README.md`.

## 1. Prerequisites

Before building joint Assessment context vectors, you should have:

- Profile joint embeddings (`PROFILE_CORE_V0`) populated via
  `backfill_joint_profiles`.
- Regime joint context embeddings (`REGIME_CONTEXT_V0`) populated via
  `backfill_joint_regime_context`.
- STAB/fragility joint embeddings (`STAB_FRAGILITY_V0`) populated via
  `backfill_joint_stab_fragility_states`.
- NEWS/text embeddings (`text-fin-general-v1`) available in
  `text_embeddings` (e.g. via `backfill_text_embeddings`).

At v0, these components provide:

- `z_profile(entity, as_of) ∈ R^384` – structural profile context.
- `z_regime_ctx(region, as_of) ∈ R^384` – joint regime/macro context.
- `z_stab(entity, as_of) ∈ R^384` – stability/fragility state.
- `z_text_recent(region, as_of) ∈ R^384` – recent NEWS text context over
  a short look-back window.

## 2. Backfill joint Assessment context embeddings

Use the dedicated CLI script `backfill_joint_assessment_context.py` to
construct Assessment context embeddings for a universe of instruments on
an as-of date.

Example: US_EQ universe on a given date

```bash
python -m prometheus.scripts.backfill_joint_assessment_context \
  --as-of 2025-01-31 \
  --market-id US_EQ \
  --region US \
  --profile-joint-model-id joint-profile-core-v1 \
  --regime-joint-model-id joint-regime-core-v1 \
  --stab-joint-model-id joint-stab-fragility-v1 \
  --text-model-id text-fin-general-v1 \
  --text-window-days 7 \
  --joint-model-id joint-assessment-context-v1
```

This will:

1. Build a universe of instruments from `instruments` for the given
   `--market-id` (and/or explicit `--instrument-id` arguments).
2. For each instrument and `--as-of` date, attempt to load:
   - Issuer-level profile joint embedding
     (`PROFILE_CORE_V0`, `joint-profile-core-v1`).
   - Instrument-level STAB joint embedding
     (`STAB_FRAGILITY_V0`, `joint-stab-fragility-v1`).
   - Region-level regime joint embedding
     (`REGIME_CONTEXT_V0`, `joint-regime-core-v1`) using `--region`.
   - Recent NEWS text context by aggregating
     `text-fin-general-v1` embeddings over the window
     `[as_of - text-window-days + 1, as_of]`.
3. Combine the available branches into a single context vector
   `z_assessment ∈ R^384` via a weighted average (branches with missing
   vectors or zero weight are skipped).
4. Insert rows into `joint_embeddings` with:
   - `joint_type = 'ASSESSMENT_CTX_V0'`.
   - `model_id = 'joint-assessment-context-v1'` (or the value passed via
     `--joint-model-id`).
   - `entity_scope` describing the instrument, optional issuer, region,
     as_of_date, and branch source tags.

## 3. Inspect Assessment context embeddings

Use the inspection CLI to view Assessment context embeddings and basic
vector diagnostics:

```bash
python -m prometheus.scripts.show_joint_assessment_context \
  --as-of 2025-01-31 \
  --model-id joint-assessment-context-v1 \
  --limit 200
```

You can also filter by instrument, issuer, region, or date range, e.g.:

```bash
python -m prometheus.scripts.show_joint_assessment_context \
  --instrument-id AAA.US \
  --region US \
  --start 2025-01-01 --end 2025-03-31 \
  --model-id joint-assessment-context-v1
```

Typical output:

```text
as_of_date,instrument_id,issuer_id,region,model_id,dim,l2_norm
2025-01-31,AAA.US,AAA,US,joint-assessment-context-v1,384,11.234567
...
```

## 4. Find similar Assessment contexts

Once you have populated `ASSESSMENT_CTX_V0` embeddings, you can search
for instruments whose context is most similar to a given instrument on a
given date. This is useful for questions such as:

> "Which instruments look most similar to AAA.US in joint Assessment
> context on 2025-01-31?"

Use the similarity CLI:

```bash
python -m prometheus.scripts.find_similar_assessment_context \
  --instrument-id AAA.US \
  --as-of 2025-01-31 \
  --model-id joint-assessment-context-v1 \
  --top-k 20
```

You can optionally restrict candidates to a region, e.g. `--region US`.
The script prints a CSV with cosine similarity and Euclidean distance:

```text
cosine,euclidean,instrument_id,issuer_id,region,source
0.992345,0.432100,BBB.US,BBB,US,profile+regime+stab+text
...
```

Higher cosine indicates a more similar Assessment context, while lower
Euclidean distance indicates closer proximity in the underlying `R^384`
space.

## 5. Use Assessment context as model features

Once `ASSESSMENT_CTX_V0` embeddings exist for a universe/date, you can
use them directly as features in the Assessment Engine via the
`ContextAssessmentModel` backend exposed by `run_assessment`.

Example: score a handful of instruments using only joint Assessment
context as input:

```bash
python -m prometheus.scripts.run_assessment \
  --strategy-id CORE_LONG_EQ \
  --market-id US_EQ \
  --instrument-id AAPL.US MSFT.US \
  --as-of 2025-01-31 \
  --horizon-days 21 \
  --backend context \
  --model-id assessment-context-v1 \
  --assessment-context-model-id joint-assessment-context-v1
```

This will:

- Read `ASSESSMENT_CTX_V0` embeddings for the given instruments/date
  from `joint_embeddings`.
- Map simple diagnostics of the context vector (e.g. L2 norm) into
  `expected_return`, `score`, `confidence`, and `signal_label`.
- Persist results into `instrument_scores` with
  `model_id = 'assessment-context-v1'` (or the value you provide via
  `--model-id`).

For comparison, you can run the original price/STAB-based backend:

```bash
python -m prometheus.scripts.run_assessment \
  --strategy-id CORE_LONG_EQ \
  --market-id US_EQ \
  --instrument-id AAPL.US MSFT.US \
  --as-of 2025-01-31 \
  --horizon-days 21 \
  --backend basic \
  --model-id assessment-basic-v1 \
  --use-joint-context \
  --assessment-context-model-id joint-assessment-context-v1
```

This uses the existing `BasicAssessmentModel` (price + STAB) but also
logs the Assessment context norm into `InstrumentScore.metadata` when
available, which is useful for diagnostics.

## 6. Use Assessment context in backtests and Meta campaigns

Once you are satisfied that `ASSESSMENT_CTX_V0` is populated and
behaving sensibly for your instruments/regions, you can use the
`ContextAssessmentModel` as the Assessment backend inside sleeve
backtests and Meta campaigns.

### 6.1 Backtest campaign with context-based Assessment

Use `run_backtest_campaign` with `--assessment-backend context` to run a
multi-sleeve campaign where Assessment scores are driven purely by joint
Assessment context embeddings:

```bash
python -m prometheus.scripts.run_backtest_campaign \
  --market-id US_EQ \
  --start 2025-01-01 \
  --end 2025-03-31 \
  --sleeve US_CORE_20D:US_CORE_LONG_EQ:US_EQ:US_CORE_UNIVERSE:US_CORE_PORT:US_CORE_ASSESS:21 \
  --assessment-backend context \
  --assessment-context-model-id joint-assessment-context-v1
```

Internally this:

- Builds `SleeveConfig` objects for each `--sleeve`.
- Configures the sleeve pipeline to use `ContextAssessmentModel` instead
  of `BasicAssessmentModel`.
- Persists scores into `instrument_scores` with
  `model_id ≈ 'assessment-context-v1'` (unless you override
  `--assessment-model-id`).
- Feeds those scores into the Universe and Portfolio engines as usual.

You can compare results to a baseline using the basic backend with
optional joint context diagnostics:

```bash
python -m prometheus.scripts.run_backtest_campaign \
  --market-id US_EQ \
  --start 2025-01-01 \
  --end 2025-03-31 \
  --sleeve US_CORE_20D:US_CORE_LONG_EQ:US_EQ:US_CORE_UNIVERSE:US_CORE_PORT:US_CORE_ASSESS:21 \
  --assessment-backend basic \
  --assessment-use-joint-context \
  --assessment-context-model-id joint-assessment-context-v1
```

### 6.2 Backtest + Meta campaign with context-based Assessment

For a full backtest + Meta-Orchestrator sweep you can use
`run_campaign_and_meta` with the same Assessment flags:

```bash
python -m prometheus.scripts.run_campaign_and_meta \
  --strategy-id US_EQ_CORE_LONG_EQ \
  --market-id US_EQ \
  --start 2025-01-01 \
  --end 2025-03-31 \
  --top-k 3 \
  --assessment-backend context \
  --assessment-context-model-id joint-assessment-context-v1
```

This will:

- Build a small catalog of core long-only sleeves for the given
  `strategy_id`/`market_id`.
- Run a backtest campaign where each sleeve uses context-based
  Assessment.
- Invoke the Meta-Orchestrator to select the top-`k` sleeves by
  backtest metrics and record a decision row in `engine_decisions`.

You can switch back to the basic backend by omitting these flags or by
explicitly setting `--assessment-backend basic`.

## 7. Compare Assessment backends
+
+Once you have run both the basic and context Assessment backends for the
+same strategy/market/horizon (e.g. via `run_assessment`,
+`run_backtest_campaign`, or `run_campaign_and_meta`), you can compare
+their outputs directly from `instrument_scores` using the
+`compare_assessment_models` CLI.
+
+Example: compare basic vs context models for a sleeve strategy:
+
+```bash
+python -m prometheus.scripts.compare_assessment_models \
+  --strategy-id US_CORE_LONG_EQ \
+  --market-id US_EQ \
+  --horizon-days 21 \
+  --model-a-id assessment-basic-v1 \
+  --model-b-id assessment-context-v1 \
+  --start 2025-01-01 --end 2025-03-31
+```
+
+This will:
+
+- Join `instrument_scores` rows for the two `model_id`s on
+  `(strategy_id, market_id, instrument_id, as_of_date, horizon_days)`.
+- Optionally filter by `--start/--end` and `--min-confidence`.
+- Print summary statistics:
+  - Number of overlapping score pairs.
+  - Means and standard deviations of `score` and `expected_return` for
+    each model.
+  - Pearson correlations `corr(score_a, score_b)` and
+    `corr(expected_return_a, expected_return_b)` when defined.
+
+To inspect raw pairs, add `--dump-pairs` to emit a CSV to stdout:
+
+```bash
+python -m prometheus.scripts.compare_assessment_models \
+  --strategy-id US_CORE_LONG_EQ \
+  --market-id US_EQ \
+  --horizon-days 21 \
+  --model-a-id assessment-basic-v1 \
+  --model-b-id assessment-context-v1 \
+  --start 2025-01-01 --end 2025-03-31 \
+  --min-confidence 0.2 \
+  --dump-pairs > assessment_model_pairs.csv
+```
+
+The CSV columns are:
+
+- `as_of_date`
+- `instrument_id`
+- `expected_return_a`, `score_a` (model A)
+- `expected_return_b`, `score_b` (model B)
+
+You can load this into a notebook or BI tool for deeper analysis
+(scatter plots, decile comparisons, regime slices, etc.).
+
+## 8. Notes

- The combination logic currently uses a simple weighted average across
  the available branches. You can adjust branch weights via
  `--w-profile`, `--w-regime`, `--w-stab`, and `--w-text`.
- The implementation follows the patterns used in other joint backfills:
  - `backfill_joint_regime_context`.
  - `backfill_joint_episode_context`.
  - `backfill_joint_profiles`.
  - `backfill_joint_stab_fragility_states`.
- Over time, the `joint-assessment-context-v1` space can become the
  primary feature backend for expected-return models, reducing bespoke
  feature engineering per strategy.
