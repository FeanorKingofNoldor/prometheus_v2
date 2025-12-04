# Dev Workflow – Full-Day Core Pipeline (Ingestion → Engines → Books → Backtests → Meta)

This workflow stitches together the existing building blocks into a
single "full day" flow you can run in a dev environment:

1. Ingest data for a given date range.
2. Create/advance `engine_runs` for that date + region.
3. Run Profiles/STAB/Fragility/Assessment (`SIGNALS` phase).
4. Build universes (`UNIVERSES` phase).
5. Build portfolio targets + Risk (`BOOKS` phase).
6. Run sleeve backtests through the execution bridge.
7. Run Meta-Orchestrator to select top sleeves and record decisions.
8. Inspect decisions and execution artifacts.

The commands below assume:

- Region: `US` (mapping to `market_id = US_EQ`).
- Strategy: `US_CORE_LONG_EQ` (core long-only US equity sleeve family).
- Example full trading date: `2024-03-29`.

Adjust dates/ids as needed.

## Quick path: one-command full-day run

If migrations and ingestion are already done for your chosen date/region,
you can drive the full day with a single CLI call:

```bash
python -m prometheus.scripts.run_full_day_core_pipeline \
  --as-of 2024-03-29 \
  --region US \
  --strategy-id US_CORE_LONG_EQ \
  --market-id US_EQ \
  --campaign-start 2024-01-02 \
  --campaign-end 2024-03-29 \
  --top-k 3
```

This will:

- Ensure and advance the `engine_runs` row for `(as_of_date=2024-03-29, region='US')`
  through SIGNALS → UNIVERSES → BOOKS.
- Run the canonical backtest campaign + Meta-Orchestrator for
  `US_CORE_LONG_EQ` in `US_EQ` over `[2024-01-02, 2024-03-29]`.
- Print a CSV of backtest runs and a summary of the recorded Meta decision
  (if any).

You can still follow the detailed steps below when you need more control.

---

## 0. Pre-requisites

Before running the full-day workflow you should have:

- Migrations applied up to at least:
  - `0018_meta_orchestrator_core` (engine_decisions, decision_outcomes, executed_actions).
  - `0020_execution_core` (orders, fills, positions_snapshots).
- Historical DB populated with:
  - `prices_daily` (EOD prices) for desired instruments.
  - Optional: fundamentals/news if you want richer profiles/text context.
- Runtime DB empty or in a known-good state.

For dev, it is recommended to use a small universe (e.g. just S&P 500) to
keep runtimes reasonable.

---

## 1. Ingest data for the day

For a real run you will ingest from EODHD or another vendor. Example for
US equities (adjust dates as needed):

```bash
cd /home/feanor/coding_projects/prometheus_v2

# 1.1 Ingest instruments (S&P 500 sample)
python -m prometheus.scripts.ingest_eodhd_sp500_instruments

# 1.2 Ingest prices for a date range covering your test date
python -m prometheus.scripts.ingest_eodhd_prices \
  --start 2024-01-01 \
  --end 2024-03-31

# 1.3 Optionally ingest fundamentals
python -m prometheus.scripts.ingest_eodhd_fundamentals \
  --start 2024-01-01 \
  --end 2024-03-31
```

After this step, `historical_db.prices_daily` and `instruments` should be
populated for the tickers you care about.

---

## 2. Create or ensure an engine run for the day/region

We operate engine_runs per `(as_of_date, region)`. For the example date
`2024-03-29` and region `US`:

```bash
cd /home/feanor/coding_projects/prometheus_v2

python -m prometheus.scripts.run_engine_state \
  --as-of 2024-03-29 \
  --region US \
  --ensure
```

This will:

- Ensure a row exists in `engine_runs` with `phase = WAITING_FOR_DATA` for
  `(as_of_date=2024-03-29, region='US')` if it did not already.

You can inspect it with:

```bash
python -m prometheus.scripts.show_engine_runs --as-of 2024-03-29 --region US
```

---

## 3. Mark data ready once ingestion is complete

Once you are confident that ingestion is complete for `(2024-03-29, US)`,
mark the run `DATA_READY`:

```bash
python -m prometheus.scripts.run_engine_state \
  --as-of 2024-03-29 \
  --region US \
  --ensure \
  --data-ready
```

This transitions the `engine_runs` row from `WAITING_FOR_DATA` to
`DATA_READY`.

---

## 4. Advance the engine run through SIGNALS → UNIVERSES → BOOKS → COMPLETED

There are two options: **manual heartbeats** or the **engine daemon**.

### 4.1 Manual heartbeats (cron-style)

Call `--advance-all` in a loop (for dev: just run it a few times):

```bash
# First heartbeat – should trigger run_signals_for_run
python -m prometheus.scripts.run_engine_state --advance-all

# Second heartbeat – should trigger run_universes_for_run
python -m prometheus.scripts.run_engine_state --advance-all

# Third heartbeat – should trigger run_books_for_run and finalise to COMPLETED
python -m prometheus.scripts.run_engine_state --advance-all
```

Check state:

```bash
python -m prometheus.scripts.show_engine_runs --as-of 2024-03-29 --region US
```

You should see the run in `COMPLETED` phase.

### 4.2 Engine daemon (medium-term option)

Alternatively, you can let the daemon perform the heartbeats:

```bash
python -m prometheus.orchestration.engine_daemon \
  --poll-interval-seconds 60 \
  --region US
```

This will repeatedly call `advance_run` for all active runs until they
reach `COMPLETED` or `FAILED`. You can stop it with `Ctrl+C` once runs
are completed.

---

## 5. What happened during SIGNALS/UNIVERSES/BOOKS

Once the run reaches `COMPLETED`, the following should have occurred for
`as_of_date=2024-03-29`, `region=US`:

1. **SIGNALS phase (`run_signals_for_run`)**:
   - Built **Profiles** for issuers in the region (`profiles` table).
   - Ran **STAB** (`StabilityEngine` + `BasicPriceStabilityModel`):
     - Wrote to `stability_vectors` and `soft_target_classes`.
   - Ran **Fragility Alpha** (`FragilityAlphaEngine`):
     - Wrote to `fragility_measures`.
   - Ran **Assessment Engine** with `BasicAssessmentModel`:
     - Wrote instrument scores to `instrument_scores`.

2. **UNIVERSES phase (`run_universes_for_run`)**:
   - Built a `CORE_EQ_US` universe for the date using `BasicUniverseModel`.
   - Wrote membership decisions to `universe_members`.

3. **BOOKS phase (`run_books_for_run`)**:
   - Constructed a core long-only equity book:
     - `book_id = US_CORE_LONG_EQ`
     - Uses `CORE_EQ_US` universe.
   - Ran `PortfolioEngine` with `BasicLongOnlyPortfolioModel`:
     - Wrote targets into `target_portfolios`.
     - Mirrored per-entity weights into `book_targets`.
   - Optionally applied **Risk Management** (`apply_risk_constraints`):
     - Logged actions into `risk_actions`.

You can sanity check these tables with simple SQL or existing CLIs (e.g.
`show_risk_actions`).

---

## 6. Run sleeve backtests through execution bridge

With signals/universes/books in place, you can now run end-to-end sleeve
backtests that:

- Use the same engines (STAB/Assessment/Universe/Portfolio).
- Route orders through the unified execution API.
- Persist `orders`, `fills`, `positions_snapshots`, and `executed_actions`.

The easiest path is the canonical campaign+meta CLI.

### 6.1 Canonical campaign + Meta for a strategy/market

Example for `US_CORE_LONG_EQ` on `US_EQ`:

```bash
python -m prometheus.scripts.run_campaign_and_meta \
  --strategy-id US_CORE_LONG_EQ \
  --market-id US_EQ \
  --start 2024-01-02 \
  --end 2024-03-29 \
  --top-k 3
```

This will:

1. Build a small grid of sleeves for `US_CORE_LONG_EQ` in `US_EQ` using
   `build_core_long_sleeves`.
2. Run `run_backtest_campaign` over the date range using the sleeve
   pipeline (STAB/Assessment/Universe/Portfolio + BacktestRunner).
3. For each sleeve run:
   - Write `backtest_runs`, `backtest_daily_equity`, `backtest_trades`.
   - Use `apply_execution_plan` to write `orders`, `fills`,
     `positions_snapshots`.
   - Mirror fills into `executed_actions`.
   - Record a `BACKTEST_SLEEVE_RUNNER` decision + outcome into
     `engine_decisions` and `decision_outcomes`.
4. Invoke Meta-Orchestrator (`run_meta_for_strategy`) to:
   - Rank sleeves by Sharpe/return/drawdown.
   - Record a `META_ORCHESTRATOR` decision selecting top-k sleeves into
     `engine_decisions`.

The CLI prints a CSV of runs and a summary of whether Meta recorded a
decision.

---

## 7. Inspect results: execution, runs, decisions

### 7.1 Engine runs

```bash
python -m prometheus.scripts.show_engine_runs --as-of 2024-03-29 --region US
```

### 7.2 Orders, fills, positions for a backtest portfolio

```bash
# Orders for a portfolio (BACKTEST mode)
python -m prometheus.scripts.show_orders \
  --portfolio-id US_CORE_LONG_EQ \
  --mode BACKTEST \
  --limit 50

# Fills for the same portfolio
python -m prometheus.scripts.show_fills \
  --portfolio-id US_CORE_LONG_EQ \
  --mode BACKTEST \
  --limit 50

# Positions snapshots
python -m prometheus.scripts.show_positions_snapshots \
  --portfolio-id US_CORE_LONG_EQ \
  --mode BACKTEST \
  --limit 50
```

### 7.3 Backtest runs and metrics

If you used `run_campaign_and_meta`, it already printed a CSV. You can
also query `backtest_runs` directly.

### 7.4 Meta decisions and outcomes

Use the meta CLIs to inspect what the Meta-Orchestrator and
BacktestRunner wrote into meta tables:

```bash
# All recent decisions for the strategy (Meta + sleeve backtests)
python -m prometheus.scripts.show_engine_decisions \
  --strategy-id US_CORE_LONG_EQ \
  --limit 50 \
  --include-outcomes

# Only Meta-Orchestrator decisions
python -m prometheus.scripts.show_engine_decisions \
  --engine-name META_ORCHESTRATOR \
  --strategy-id US_CORE_LONG_EQ \
  --limit 20

# Only BACKTEST_SLEEVE_RUNNER decisions (one per sleeve run)
python -m prometheus.scripts.show_engine_decisions \
  --engine-name BACKTEST_SLEEVE_RUNNER \
  --strategy-id US_CORE_LONG_EQ \
  --limit 20
```

You can further explore config+env similarity via:

```bash
# Find runs similar to a given run_id in META_CONFIG_ENV_V0 space
python -m prometheus.scripts.find_similar_meta_runs \
  --run-id <some_run_id> \
  --model-id joint-meta-config-env-v1 \
  --top-k 10
```

---

## 8. Optional: Risk on/off comparison in full-day context

To compare a risk-on vs risk-off version of this full-day flow:

1. Keep steps 1–5 identical.
2. For the **risk-on** backtest+meta run, use:

   ```bash
   python -m prometheus.scripts.run_campaign_and_meta \
     --strategy-id US_CORE_LONG_EQ \
     --market-id US_EQ \
     --start 2024-01-02 \
     --end 2024-03-29 \
     --top-k 3
   ```

3. For the **risk-off** variant, add `--disable-risk`:

   ```bash
   python -m prometheus.scripts.run_campaign_and_meta \
     --strategy-id US_CORE_LONG_EQ \
     --market-id US_EQ \
     --start 2024-01-02 \
     --end 2024-03-29 \
     --top-k 3 \
     --disable-risk
   ```

4. Use `show_engine_decisions` and `show_risk_actions` to compare
   outcomes and logged risk interventions.

---

This workflow gives you a **single-day, end-to-end path** from raw data
→ engine_runs → targets → execution logs → backtests → meta decisions,
using only the CLIs and engines already present in the repository.