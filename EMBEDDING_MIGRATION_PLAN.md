# Prometheus v2 – Pre-Embedding Runtime Plan

## 1. Purpose

This document explains **what we should run and validate first** before
committing to a full embedding-based runtime (numeric/text/joint), so that we
have:

- A solid **baseline backtest and pipeline** that works end-to-end.
- A clear, staged path to introducing embeddings, λ̂, and Meta on top.

Think of this as the **migration checklist** from the current v0
price+STAB-centric world to the embedding-centric world described in
`EMBEDDING_WORLD_VISION.md`.

---

## 2. Assumed Current State

You already have:

- Two Postgres DBs configured via `.env`:
  - `prometheus_historical` – historical data.
  - `prometheus_runtime` – runtime state.
- Migrations applied to both DBs.
- Historical prices backfilled into `prices_daily` (1997–2024) for US equities.
- S&P 500 instruments/issuers ingested and attached to `US_EQ` market.
- Basic backfill scripts and tests already run at least once.

Hardware:

- Threadripper 5975WX (32 cores)
- 160 GB RAM
- Tesla V100 32GB (CUDA), accessible from Omarchy
- 1.5 TB fast storage mounted at `/mnt/data` (for heavy backfills, logs, etc.)

---

## 3. Phase 0 – Sanity: Tests and Data Checks

Before any heavy backfills or backtests, verify:

### 3.1 Tests

```bash
cd /home/feanor/coding_projects/prometheus_v2
source venv/bin/activate

# Fast/unit tests only
pytest

# Integration tests (DB required)
pytest -m integration tests/integration
```

### 3.2 Data sanity

```bash
# Historical coverage
./venv/bin/python << 'EOF'
from prometheus.core.database import get_db_manager

dm = get_db_manager()
with dm.get_historical_connection() as conn:
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM prices_daily')
    print('prices_daily rows:', cur.fetchone()[0])
    cur.execute('SELECT MIN(trade_date), MAX(trade_date) FROM prices_daily')
    print('prices_daily range:', cur.fetchone())
    cur.execute('SELECT COUNT(*) FROM news_articles')
    print('news_articles rows:', cur.fetchone()[0])
    cur.execute('SELECT MIN(DATE(timestamp)), MAX(DATE(timestamp)) FROM news_articles')
    print('news_articles range:', cur.fetchone())
    cur.close()
EOF
```

**Goal:** confirm you have continuous EOD price data and at least several
years of news (from 2015 onward).

---

## 4. Phase 1 – Baseline Backtest (No Embeddings Required)

Goal: prove the entire backtest stack (TimeMachine → engines → Broker →
BacktestRunner → DB writes → Meta stubs) works cleanly over a real period.

### 4.1 Define sleeves

Use the helper script (already created):

```bash
cd /home/feanor/coding_projects/prometheus_v2
source venv/bin/activate

python scripts/setup_phase1_sleeves.py
```

This prints three sleeves for `US_CORE_LONG_EQ` on `US_EQ`:

- `US_CORE_LONG_EQ_H5`
- `US_CORE_LONG_EQ_H21`
- `US_CORE_LONG_EQ_H63`

These differ **only** in assessment horizon (5/21/63 days) and are wired to:

- `universe_id = {sleeve_id}_UNIVERSE`
- `portfolio_id = {sleeve_id}_PORTFOLIO`
- `assessment_strategy_id = {sleeve_id}_ASSESS`

### 4.2 Run a small backtest campaign (Q1 2014)

```bash
cd /home/feanor/coding_projects/prometheus_v2
source venv/bin/activate

python prometheus/scripts/run_backtest_campaign.py \
  --market-id US_EQ \
  --start 2014-01-02 \
  --end   2014-03-31 \
  --sleeve US_CORE_LONG_EQ_H5:US_CORE_LONG_EQ:US_EQ:US_CORE_LONG_EQ_H5_UNIVERSE:US_CORE_LONG_EQ_H5_PORTFOLIO:US_CORE_LONG_EQ_H5_ASSESS:5 \
  --sleeve US_CORE_LONG_EQ_H21:US_CORE_LONG_EQ:US_EQ:US_CORE_LONG_EQ_H21_UNIVERSE:US_CORE_LONG_EQ_H21_PORTFOLIO:US_CORE_LONG_EQ_H21_ASSESS:21 \
  --sleeve US_CORE_LONG_EQ_H63:US_CORE_LONG_EQ:US_EQ:US_CORE_LONG_EQ_H63_UNIVERSE:US_CORE_LONG_EQ_H63_PORTFOLIO:US_CORE_LONG_EQ_H63_ASSESS:63 \
  --initial-cash 1000000 \
  --max-workers 3
```

Notes:

- `assessment-backend` defaults to `basic`, which uses price+STAB only.
- λ̂ is **off** by default (no lambda provider configured) – that is fine.

This should print a CSV with one row per sleeve:

```text
run_id,sleeve_id,strategy_id,cumulative_return,annualised_sharpe,max_drawdown
<uuid>,US_CORE_LONG_EQ_H5,US_CORE_LONG_EQ,...
<uuid>,US_CORE_LONG_EQ_H21,US_CORE_LONG_EQ,...
<uuid>,US_CORE_LONG_EQ_H63,US_CORE_LONG_EQ,...
```

### 4.3 Inspect results

Simple checks:

```bash
# Recent backtest_runs
psql -h localhost -U feanor -d prometheus_runtime -c \
  "SELECT run_id, strategy_id, start_date, end_date, metrics_json->>'cumulative_return' AS cumret \
     FROM backtest_runs \
 ORDER BY created_at DESC LIMIT 5;"

# Daily equity for last run
psql -h localhost -U feanor -d prometheus_runtime -c \
  "SELECT date, equity_curve_value, drawdown \
     FROM backtest_daily_equity \
 ORDER BY date DESC LIMIT 10;"

# Sanity: some trades exist
psql -h localhost -U feanor -d prometheus_runtime -c \
  "SELECT COUNT(*) FROM backtest_trades;"
```

**Success criteria:**

- No crashes.
- Reasonable, non-zero equity curves.
- Trades and positions written.

This is your **baseline non-embedding backtest**.

---

## 5. Phase 2 – Numeric Embeddings for Backtest Window

Goal: populate `numeric_window_embeddings` for the **same period you backtest**
(plus some buffer), so that future engines and λ̂ experiments can use them.

### 5.1 Daily numeric backfill (2010–2024 as a starter)

Use the enhanced `backfill_numeric_embeddings_comprehensive.py` which supports
`--start-date` / `--end-date` for daily dates.

```bash
cd /home/feanor/coding_projects/prometheus_v2
source venv/bin/activate

# Test run: only 2024, limited instruments
python -m prometheus.scripts.backfill_numeric_embeddings_comprehensive \
  --start-date 2024-01-01 \
  --end-date   2024-12-31 \
  --window-days 63 \
  --market US_EQ \
  --limit 10
```

If that succeeds, run for the full window you care about, e.g. 2010–2024:

```bash
python -m prometheus.scripts.backfill_numeric_embeddings_comprehensive \
  --start-date 2010-01-01 \
  --end-date   2024-12-31 \
  --window-days 63 \
  --market US_EQ \
  --skip-existing
```

This will fill `numeric_window_embeddings` for multiple models:

- `num-regime-core-v1`
- `num-stab-core-v1`
- `num-profile-core-v1`
- `num-scenario-core-v1`
- `num-portfolio-core-v1`

over all instruments that have price data.

### 5.2 Verify numeric embeddings

```bash
./venv/bin/python << 'EOF'
from prometheus.core.database import get_db_manager

dm = get_db_manager()
with dm.get_historical_connection() as conn:
    cur = conn.cursor()
    cur.execute('SELECT model_id, COUNT(*) FROM numeric_window_embeddings GROUP BY model_id ORDER BY model_id')
    for model_id, cnt in cur.fetchall():
        print(model_id, cnt)
    cur.close()
EOF
```

**Goal:** ensure you have non-trivial counts for the 5 core models.

At this point you have a **numeric feature surface** ready for later
embedding-aware engines and λ̂ experiments, while the live/backtest pipeline
still uses its existing price+STAB logic.

---

## 6. Phase 3 – Optional: Baseline λₜ(x) and Simple λ̂

This phase is optional before switching to full embeddings, but recommended if
you want λ̂-aware universes **before** context Assessment and joint spaces.

### 6.1 Backfill λₜ(x)

```bash
# Example: 2015–2024
python -m prometheus.scripts.backfill_opportunity_density \
  --start 2015-01-01 \
  --end   2024-12-31 \
  --market US_EQ \
  --lookback-days 20 \
  --min-cluster-size 5 \
  --output data/lambda_US_EQ_20150101_20241231.csv
```

This produces CSV rows with:

- `as_of_date, market_id, sector, soft_target_class, num_instruments,
   dispersion, avg_vol_window, lambda_value`

### 6.2 Train a first λ̂ model (simple features)

Use `run_opportunity_density_experiment.py` (once configured) to map simple
features (returns, vol, STAB class) → λ̂ and produce a predictions CSV.

Later, you can extend the feature set to include embeddings.

### 6.3 Wire λ̂ into universes/backtests

Configure `configs/universe/core_long_eq_daily.yaml`:

```yaml
core_long_eq:
  US:
    lambda_predictions_csv: data/lambda_predictions_US_EQ.csv
    lambda_experiment_id: US_EQ_SIMPLE_V0
    lambda_score_column: lambda_hat
    lambda_score_weight: 10.0
```

Then `run_backtest_campaign_and_meta_for_strategy` will automatically create a
`CsvLambdaClusterScoreProvider` and feed λ̂ into universes used by the
backtest.

**This is still v0; embedding-based λ̂ can be added later.**

---

## 7. Phase 4 – Introduce Context Assessment Backend

Goal: upgrade the Assessment Engine to use **joint Assessment context
embeddings** (`ASSESSMENT_CTX_V0`), still over a bounded period (e.g. 2015–2024)
so you can compare directly to the baseline.

High-level steps (details belong in a separate HOWTO):

1. Backfill text embeddings for NEWS (2015–2024) with `text-fin-general-v1`.
2. Backfill joint profiles, joint regime context, and joint STAB embeddings.
3. Backfill `ASSESSMENT_CTX_V0` via `backfill_joint_assessment_context.py`.
4. Run backtests with:

   ```bash
   --assessment-backend context \
   --assessment-context-model-id joint-assessment-context-v1
   ```

5. Compare metrics vs the basic backend for the same sleeves/period.

At this point you have one core engine (Assessment) fully embedding-based.

---

## 8. Phase 5 – Only Then Consider Full 1997–2024 Embedding Backfill

Once:

- Baseline backtests are stable.
- Numeric embeddings for the backtest horizon are populated.
- λₜ(x)/λ̂ and/or context Assessment show real value over 2010–2024.

…then decide if you want to:

- Extend numeric + joint embeddings back to 1997 for maximum regime
  coverage, or
- Keep training windows at something like 2005–2024 which already spans
  multiple regimes.

Large 1997–2024 backfills are CPU/GPU/IO heavy; they make sense **after** you
have at least one embedding-based improvement wired in and validated.

---

## 9. Summary

Before switching the runtime to rely on embeddings everywhere, we should:

1. **Prove the pipeline works** with a non-embedding baseline backtest.
2. **Populate numeric embeddings** for the backtest window so that future
   engines and λ̂ experiments have features ready.
3. Optionally, **introduce λₜ(x)/λ̂** with simple features first.
4. **Upgrade Assessment** to context-based on top of joint embeddings.
5. Only then consider **full-horizon 1997–2024 embedding backfills**.

This staged approach uses your hardware efficiently, keeps feedback loops
short, and ensures we always have a working baseline to compare against as we
turn on more of the embedding stack.