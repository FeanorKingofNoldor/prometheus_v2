# Data Ingestion & Normalization Service – Detailed Plan

## 1. Purpose & Scope

Single, authoritative subsystem that fetches all external data, cleans and validates it, and writes it into the system’s historical databases. No other component talks to external providers.

Covers:
- Market data (equities, indices; EOD; later intraday aggregates).
- Fundamentals (financial statements, ratios).
- Macro & credit time series.
- Company metadata and index membership.
- Filings, transcripts, and major corporate event documents.
- News & events (including those later used by Black Swan Engine & profiles).


## 2. High-Level Architecture

### 2.1 Internal Modules

- `sources/` – provider-specific clients (read-only, pure fetchers).
  - `market_data_client`
  - `fundamentals_client`
  - `macro_data_client`
  - `news_client`
  - `filings_client`
- `normalizers/` – map raw provider payloads → internal canonical records.
  - `market_normalizer`
  - `fundamentals_normalizer`
  - `macro_normalizer`
  - `news_normalizer`
  - `filings_normalizer`
- `writers/` – DB write layer (bulk inserts/updates with upserts).
  - `historical_db_writer`
- `orchestration/` – scheduling and job orchestration.
  - `daily_pipeline`
  - `event_driven_pipeline`
- `validation/` – data quality checks and metrics.
  - `dq_rules`, `dq_runner`

All of these are **pure Python modules** inside `data_ingestion` in the new project.


## 3. Data Contracts

### 3.1 Inputs

- Provider configs (env/config DB):
  - API keys
  - endpoints / rate limits
  - symbol / ID mappings
- Schedules / triggers:
  - Daily cron for EOD data.
  - Weekly/monthly tasks for less frequent series.
  - Event triggers from webhooks or polling (new filing, major news).

### 3.2 Outputs – Tables written (Historical DBs)

Same schema in both `training_historical` and `prod_historical` (different DB instances):

- `companies`
  - `company_id` (PK)
  - `ticker`, `isin`, `name`, `sector`, `industry`, `country`
  - `listing_date`, `delisting_date` (nullable)
  - `metadata_json`

- `equity_prices_daily`
  - `ticker`, `date` (PK composite)
  - `open`, `high`, `low`, `close`, `adj_close`, `volume`
  - `currency`
  - `source`

- `sp500_constituents`
  - `ticker`, `effective_date` (PK composite)
  - `end_date` (nullable)
  - `index_name`

- `corporate_actions`
  - `id` (PK)
  - `ticker`, `action_date`, `action_type` (SPLIT, DIVIDEND, etc.)
  - `details_json`

- `financial_statements`
  - `statement_id` (PK)
  - `company_id`
  - `fiscal_period` (e.g. 2025Q2)
  - `fiscal_year`
  - `statement_type` (IS, BS, CF)
  - `report_date`
  - `values_json` (normalized line items)

- `fundamental_ratios`
  - `company_id`, `period_start`, `period_end` (PK composite)
  - `roe`, `roic`, `gross_margin`, `op_margin`, `net_margin`
  - `leverage`, `interest_coverage`, `revenue_growth`, `eps_growth`
  - `metrics_json` for extensible fields

- `macro_time_series`
  - `series_id`, `date` (PK composite)
  - `value`
  - `frequency` (DAILY/WEEKLY/MONTHLY)
  - `metadata_json`

- `news_events`
  - `event_id` (PK)
  - `company_id` (nullable)
  - `sector` (nullable)
  - `event_date`
  - `source` (newswire, outlet)
  - `event_type` (NEWS, OPINION, SOCIAL_POST, ALERT, etc.)
  - `headline`
  - `body_text` or `body_ref`
  - `raw_metadata`

- `filings`
  - `filing_id` (PK)
  - `company_id`
  - `filing_type` (10-K, 10-Q, AGM_DOC,...)
  - `filing_date`
  - `period_end`
  - `text_blob` or `text_ref`
  - `raw_metadata_json`

- `earnings_calls`
  - `call_id` (PK)
  - `company_id`
  - `call_date`
  - `transcript_text` or ref
  - `raw_metadata_json`

These tables are consumed by Profile Service, Macro Regime, Universe Selection, Backtesting, and Black Swan Engine.


## 4. Core Flows

### 4.1 Daily EOD Ingestion Flow

1. `daily_pipeline` triggered after market close.
2. Fetch:
   - Latest daily prices for all tracked tickers.
   - Any new corporate actions.
   - New macro data with daily frequency.
3. Normalize:
   - Convert provider payloads into canonical records.
   - Enforce currency, scale, and symbol mapping.
4. Validate:
   - No missing fields for required data.
   - Prices/volumes within sanity bounds (no crazy negatives, etc.).
5. Write:
   - Bulk upsert into `equity_prices_daily`, `corporate_actions`, `macro_time_series`.
6. Record run status:
   - Write to a `ingestion_runs`/`data_quality_metrics` table with errors/warnings.

### 4.2 Fundamentals & Filings Flow

- Frequency: event-driven + periodic catch-up.
1. Poll/receive new filings and fundamentals from providers.
2. Normalize financial statements into `financial_statements` and `fundamental_ratios`.
3. Store full text of filings in `filings`.
4. Validate accounting continuity (e.g. no huge, unexplained jumps without events).
5. Insert into historical DB.

### 4.3 News & Social Flow (for Black Swan & Profiles)

1. Continuously ingest news headlines & articles (batched).
2. Ingest selected social media posts for whitelisted accounts.
3. Normalize into `news_events` with tags and metadata.
4. Basic deduplication and spam filtering.
5. These rows are then used by:
   - Profile Service (for event summaries).
   - Black Swan Engine (for crisis detection).


## 5. Interfaces

This service does **not** expose complex business APIs; its main interface is the database state plus minimal status APIs.

- `run_daily_ingestion(date)` → runs full daily job, returns summary (+ logs to DB).
- `run_fundamentals_ingestion(since_timestamp)` → backfill or live.
- `run_news_ingestion(since_timestamp)`.
- `get_last_ingestion_status(component)` → used by Monitoring.

All other services access data via DB clients, not via this service directly.


## 6. Interactions with Other Players

- **Profile Service**: reads `companies`, `financial_statements`, `fundamental_ratios`, `filings`, `earnings_calls`, `news_events`.
- **Macro Regime Service**: reads `macro_time_series`.
- **Universe Selection Service**: reads `equity_prices_daily`, `fundamental_ratios`, `sp500_constituents`.
- **Backtesting Engine**: reads all historical tables; in TRAINING mode, ingestion may point to synthetic sources.
- **Black Swan Emergency Engine**: reads `news_events` and `macro_time_series`.
- **Monitoring**: reads `ingestion_runs` and data-quality logs.


## 7. Failure Modes & Safeguards

- **Atomicity per data unit** (per date/scope):
  - For each ingestion unit (e.g. daily prices for a date, fundamentals for a period, news since T), the system either:
    - Fully ingests and validates the batch, then commits it to the main tables, **or**
    - Discards it entirely and leaves the main tables unchanged for that unit.
- **Staging + swap pattern**:
  - Write incoming data into a staging structure (temporary tables or in-memory frames).
  - Run all validation checks on staging.
  - If validation passes:
    - Delete any existing rows in the main table(s) for that date/scope.
    - Insert the validated data in a single transaction.
  - If validation fails:
    - Do **not** touch existing main data for that date/scope.
    - Log the failure and mark the ingestion run as FAILED for that component.
- Downstream nightly prep:
  - MUST check ingestion status for the required date range.
  - If an ingestion unit failed, the correct response is to **re-run ingestion for that unit**, which will clear/repopulate rows atomically via the staging + swap pattern.
- Rate limit / provider errors:
  - Retry with backoff.
  - Fall back to alternative providers if configured.


## 8. Implementation Notes

- Use bulk operations for DB writes to avoid slow row-by-row inserts.
- Use idempotent design: re-running a job for `date` should produce the same DB state.
- Keep provider-specific quirks isolated in `sources/` and `normalizers/` so core logic is clean.


## 9. TODOs for Third-Pass Enhancements

These items were the focus of the third implementation pass.

- Implemented a concrete market data client `EodhdMarketDataClient` for daily
  S&P 500 OHLCV using EODHD All‑in‑One under `sources/market_data_client.py` and
  wired it into `orchestration/daily_pipeline.py`.
- Updated the Phase 2 dev workflow doc to describe EODHD-backed ingestion and
  the dependency on `sp500_constituents`.

Remaining third-pass TODOs (deferred):

- Implemented concrete provider clients for **market data**, **fundamentals**,
  **macro**, and **news** under `sources/` and wired them into the
  orchestration modules:
  - `EodhdMarketDataClient` for daily S&P 500 EOD prices (Phase 2 daily
    pipeline).
  - `EodhdMacroDataClient` for a small initial set of macro series written into
    `macro_time_series`.
  - `EodhdFundamentalsClient` for S&P 500 fundamentals snapshots, stored in
    `financial_statements` and `fundamental_ratios` (metrics_json-heavy for
    now).
  - `EodhdNewsClient` for financial news, stored in `news_events`.
- TODO: Implement a concrete **filings/earnings** client and map it into the
  `filings` and `earnings_calls` tables (currently left empty in this pass).
- TODO: Introduce richer data quality rules (e.g. cross-series consistency
  checks, provider vs provider comparisons) in `validation/`.
- TODO: Add full staging+swap semantics for fundamentals, filings, and news
  flows once the natural unit of atomicity (per period, per filing batch, etc.)
  is finalized.
- TODO: Add backfill utilities for large historical imports (e.g. CSV-based
  loaders) that reuse the same normalizers and writers but operate over
  multi-year ranges efficiently.

### 9.1 Explicit TODOs for Fourth-Pass Enhancements

The following items are intentionally **not** part of the third pass and should
be revisited in a later iteration once the S&P 500 EOD pipeline is stable:

- TODO (v4): Extend market data ingestion beyond S&P 500 to additional indices
  and global universes, ideally leveraging EODHD bulk endpoints per exchange.
- TODO (v4): Add intraday aggregation ingestion (e.g. 1m/5m bars) and integrate
  them into `stock_metrics` and backtesting.
- TODO (v4): Implement more advanced DQ checks for price gaps, stale data, and
  cross-source reconciliation where multiple providers are available.
- TODO (v4): Provide CLI/automation helpers for large initial backfills (multi-
  year S&P 500 history) with progress reporting and resumable chunks.
