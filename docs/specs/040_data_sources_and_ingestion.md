# 040 – External Data Sources and Ingestion Specification

## 1. Purpose

This document answers:
- **Who** fetches all external data Prometheus v2 needs.
- **How** data is ingested (pipelines, staging, QC, storage).
- **How** engines retrieve data again (read APIs, not direct provider calls).
- A catalog of **every external data type** and the component responsible for fetching it.

Initial focus is US equities with S&P 500, but the design generalizes to other universes and regions.

---

## 2. High-Level Architecture

### 2.1 Responsibilities

- `prometheus/data_ingestion/`
  - Owns **all external data fetching**.
  - Contains per-domain ingestion modules (prices, fundamentals, macro, news, filings, etc.).
  - Contains **provider adapters** (e.g. vendor APIs, CSV/Parquet loaders).

- `prometheus/data/` (or `prometheus/core/data_access/`)
  - Owns **read-side APIs** for engines and services.
  - Converts DB tables (020) into typed Python objects and dataframes.
  - Enforces that engines **never** talk directly to external providers.

- Orchestrator (012/013)
  - Triggers ingestion DAGs:
    - daily EOD market data updates,
    - periodic fundamentals/macro refresh,
    - continuous or frequent news/text ingestion.
  - Ensures ingestion jobs have appropriate resource classes and SLOs.

### 2.2 Ingestion pattern (staging → QC → swap)

Each ingestion job follows the same pattern:

1. **Fetch**
   - Call provider API / download file / query feed for the target date(s) and instruments.
   - Write raw data to a **staging area** (e.g. `stg_*` tables or temporary files).

2. **Normalize & validate**
   - Transform into canonical schema defined in 020.
   - Run schema checks (types, ranges) and basic quality checks (missingness, outliers).

3. **QC & metrics**
   - Compute per-day, per-market QC metrics.
   - Compare with historical baselines (020 + 180).
   - If QC fails, mark the batch as **degraded**; alert and optionally abort swap.

4. **Swap into production tables**
   - Insert/update data in the final tables (020) in an atomic fashion for that date/market.

5. **Log ingestion metadata**
   - Who ran it (automation, manual), when, provider, coverage, QC summary.

### 2.3 Retrieval pattern

- Engines and services never call providers.
- Instead they use data access APIs such as (conceptually):
  - `get_prices(instrument_ids, start_date, end_date, frequency="D")`
  - `get_returns(...)`
  - `get_macro_series(series_ids, ...)`
  - `get_profiles(instrument_ids, as_of_date, ...)`
- These live in `prometheus/data/api.py` and read from:
  - the normalized tables defined in 020,
  - possibly short-lived in-memory caches for hot data.

---

## 3. External Data Catalog

This section lists **all external data types** we expect to fetch, with: an ID, description, ingestion owner, storage, and primary consumers.

### 3.1 Market & Reference Data (Equities/Futures/FX)

These are the backbone for prices and instruments.

1. `INSTRUMENTS_STATIC`
- Description: Static reference data for instruments (equities, ETFs, futures, FX pairs, indices).
- Fields: instrument_id, issuer_id, market_id, ticker, name, currency, listing_exchange, asset_class, status, primary_flag, first_trade_date, last_trade_date, etc.
- Ingestion owner: `prometheus/data_ingestion/instruments.py`
- Storage: `instruments` table (020) and related `issuers`, `markets`.
- Primary consumers: all engines (especially Universe, Portfolio, Assessment, Regime).

2. `INDEX_CONSTITUENTS`
- Description: Membership and weights for benchmark indices (e.g. S&P 500, sector indices).
- Initial scope: S&P 500 for US_EQ.
- Fields: index_id, instrument_id, effective_date, weight, inclusion_flag.
- Ingestion owner: `prometheus/data_ingestion/indexes.py`
- Storage: `index_constituents` (implied by 020).
- Primary consumers: Universe Engine (140), Risk/Portfolio (150), Meta (160), Synthetic Scenarios (170).

3. `PRICES_EOD`
- Description: End-of-day OHLCV prices for instruments.
- Fields: date, instrument_id, open, high, low, close, adjusted_close, volume.
- Ingestion owner: `prometheus/data_ingestion/prices_eod.py`
- Storage: `prices_daily` (020).
- Primary consumers: Regime (100), Assessment (130), Portfolio & Risk (150), Scenarios (170), Meta (160).

4. `RETURNS_EOD`
- Description: Daily log/simple returns (can be derived from `PRICES_EOD` but sometimes fetched directly).
- Ingestion owner: usually derived by ETL job: `prometheus/data_ingestion/derived/returns.py`.
- Storage: `returns_daily` (020).
- Primary consumers: Regime, factor models, scenario generation, Portfolio & Risk.

5. `INTRADAY_BARS` (future expansion)
- Description: Intraday OHLCV bars (e.g. 1/5/15 min) for backtesting intraday strategies.
- Ingestion owner: `prometheus/data_ingestion/prices_intraday.py`.
- Storage: `prices_intraday_*` tables (not yet detailed in 020).
- Primary consumers: future versions of backtesting, execution, intraday risk.

6. `FX_RATES`
- Description: Daily FX spot rates (and possibly forward points) for major currency pairs.
- Ingestion owner: `prometheus/data_ingestion/fx.py`.
- Storage: `fx_rates_daily` (implied by 020).
- Primary consumers: Portfolio & Risk, Regime, macro/scenario engines.

7. `CORPORATE_ACTIONS`
- Description: Splits, dividends, symbol changes, mergers, spin-offs, etc.
- Ingestion owner: `prometheus/data_ingestion/corporate_actions.py`.
- Storage: `corporate_actions` table.
- Primary consumers: data adjustment layer (returns, prices), Universe, Portfolio & Risk.

### 3.2 Fundamentals & Estimates

8. `FUNDAMENTALS_ANNUAL`
- Description: Annual financial statements (balance sheet, income statement, cash flow) and fundamentals.
- Ingestion owner: `prometheus/data_ingestion/fundamentals.py`.
- Storage: `fundamentals_annual` table (issuer_id, period_end_date, metrics...).
- Primary consumers: Profiles (035), Assessment (130), Stability/Soft-Target (110), Fragility Alpha (135).

9. `FUNDAMENTALS_QUARTERLY`
- Description: Quarterly financials analogous to annual.
- Ingestion owner: same as above.
- Storage: `fundamentals_quarterly`.
- Primary consumers: same as annual, but for more timely signals.

10. `ANALYST_ESTIMATES`
- Description: Consensus estimates (EPS, revenues, target prices), and possibly revisions.
- Ingestion owner: `prometheus/data_ingestion/estimates.py`.
- Storage: `analyst_estimates`.
- Primary consumers: Profiles, Assessment, Fragility Alpha (over-optimism / complacency), Portfolio & Risk.

11. `FUNDAMENTAL_RATIOS`
- Description: Precomputed ratios (P/E, P/B, ROE, leverage, margins). Could be internal derivation, but may also come from providers.
- Ingestion owner: `prometheus/data_ingestion/derived/ratios.py`.
- Storage: `fundamental_ratios`.
- Primary consumers: Profiles, Stability/Soft-Target, Assessment.

### 3.3 Macro, Credit, and Volatility Data

12. `MACRO_TIME_SERIES`
- Description: Key macro variables (GDP growth, inflation, unemployment, PMI, yields, spreads, etc.).
- Ingestion owner: `prometheus/data_ingestion/macro.py`.
- Storage: `macro_time_series` (020).
- Primary consumers: Regime Engine (100), Black Swan / Stability engines (110/135), Scenarios (170), Meta.

13. `YIELD_CURVES`
- Description: Term structure of government bond yields for major curves.
- Ingestion owner: `prometheus/data_ingestion/yield_curves.py`.
- Storage: `yield_curves` (benchmark curve_id, date, tenors, yields).
- Primary consumers: Macro regimes, risk-free rate computation, Portfolio & Risk.

14. `CREDIT_SPREADS`
- Description: Corporate/sovereign credit spreads indices (IG, HY), CDS indices.
- Ingestion owner: `prometheus/data_ingestion/credit.py`.
- Storage: `credit_spreads`.
- Primary consumers: Regimes, Stability/Soft-Target, Fragility Alpha, Scenarios.

15. `VOLATILITY_INDICES`
- Description: Implied volatility indices (e.g. VIX, VSTOXX).
- Ingestion owner: `prometheus/data_ingestion/volatility_indices.py`.
- Storage: `volatility_indices`.
- Primary consumers: Regimes, Stability, Scenarios, Portfolio & Risk.

### 3.4 Events & Calendars

16. `EARNINGS_CALENDAR`
- Description: Upcoming/actual earnings announcement dates and times.
- Ingestion owner: `prometheus/data_ingestion/events_earnings.py`.
- Storage: `earnings_events`.
- Primary consumers: Profiles, Assessment, Stability, Scenarios (event-driven shocks).

17. `DIVIDEND_EVENTS`
- Description: Declared dividends (ex-date, record date, payment date, amount).
- Ingestion owner: `prometheus/data_ingestion/events_dividends.py`.
- Storage: `dividend_events`.
- Primary consumers: Portfolio & Risk (cash flows), Profiles.

18. `MACRO_EVENTS`
- Description: Scheduled and realized macro events (FOMC, CPI releases, payrolls, etc.).
- Ingestion owner: `prometheus/data_ingestion/macro_events.py`.
- Storage: `macro_events` (020).
- Primary consumers: Regime, Scenarios, Black Swan/stability engines.

19. `CALENDARS_MARKET_HOLIDAYS`
- Description: Exchange holidays and special trading days per market.
- Ingestion owner: `prometheus/data_ingestion/calendars.py`.
- Storage: `markets` table calendar_spec or a separate `market_calendar` table.
- Primary consumers: Calendars (012), Orchestrator (013), all time-based engines.

### 3.5 Textual Data: Filings, Transcripts, News

20. `FILINGS`
- Description: Corporate filings (10-K, 10-Q, 20-F, etc., and local equivalents).
- Ingestion owner: `prometheus/data_ingestion/filings.py`.
- Storage: `filings` table (020) + raw text storage (object store or text field), plus `text_embeddings` (030) after encoding.
- Primary consumers: Profiles (035), Assessment, Fragility Alpha, Stability.

21. `EARNINGS_CALL_TRANSCRIPTS`
- Description: Transcripts of earnings calls and similar events.
- Ingestion owner: `prometheus/data_ingestion/transcripts.py`.
- Storage: `earnings_calls` (020) + `text_embeddings`.
- Primary consumers: Profiles, Assessment, Stability/Soft-Target, Fragility Alpha.

22. `NEWS_ARTICLES`
- Description: News articles and headlines relevant to instruments, sectors, macro.
- Ingestion owner: `prometheus/data_ingestion/news.py`.
- Storage: `news_articles`, `news_links` (020) + `text_embeddings` for content/headlines.
- Primary consumers: Regime (text side), Profiles, Stability, Fragility Alpha, Black Swan engine, Scenarios.

23. `NEWS_TICKER_STREAM`
- Description: Real-time-ish headlines with minimal content.
- Ingestion owner: same as above, possibly a streaming job.
- Storage: same tables or a `news_stream` table.
- Primary consumers: Monitoring/alerts, Black Swan detection components, future real-time modules.

### 3.6 Execution & Microstructure Data

24. `QUOTES_TRADES`
- Description: Level-1 quotes and trade prints for execution-quality monitoring and simple microstructure features.
- Ingestion owner: `prometheus/data_ingestion/execution/quotes_trades.py`.
- Storage: `quotes_trades_intraday` (aggregated and possibly compressed).
- Primary consumers: Execution service, Stability (liquidity measures), Portfolio & Risk (slippage models), Meta.

25. `ORDER_BOOK_SNAPSHOTS` (optional/high-volume)
- Description: Level-2 snapshots or order-book depth for selected instruments.
- Ingestion owner: `prometheus/data_ingestion/execution/order_book.py`.
- Storage: `order_book_snapshots` (carefully compressed/partitioned).
- Primary consumers: Execution, microstructure-aware stability measures, research.

26. `EXECUTION_REPORTS`
- Description: Your own trade fills, order states, transaction costs.
- Ingestion owner: `prometheus/data_ingestion/execution/reports.py` (from broker or OMS).
- Storage: `executed_actions`, `transaction_costs` tables.
- Primary consumers: Portfolio & Risk, Meta (Kronos), Monitoring.

### 3.7 Risk & Factor Data

27. `FACTOR_RETURNS_EXTERNAL` (optional)
- Description: External factor returns from a vendor (value, momentum, size, quality, etc.), if you don’t fully compute your own.
- Ingestion owner: `prometheus/data_ingestion/factors_external.py`.
- Storage: `factors_daily` (020) with a provider tag.
- Primary consumers: Portfolio & Risk, Regime, Assessment, Fragility Alpha, Scenarios.

28. `BENCHMARK_INDICES`
- Description: Time series of major benchmarks (SPX, sector indices, country indices).
- Ingestion owner: `prometheus/data_ingestion/indexes.py`.
- Storage: `benchmark_indices_daily` (or a subset of `prices_daily` and `returns_daily` flagged as indices).
- Primary consumers: Portfolio & Risk, Meta, Monitoring.

### 3.8 Optional / Alternative Data (future)

29. `ALTERNATIVE_DATA_SERIES`
- Description: Vendor-specific alternative data (web traffic, app usage, spending estimates, etc.).
- Ingestion owner: `prometheus/data_ingestion/alternative.py`.
- Storage: `alternative_data_series`.
- Primary consumers: Profiles, Assessment, Stability/Soft-Target, Meta.

These are optional and only added once the core stack is stable.

---

## 4. Ingestion DAGs per Data Family

Using the orchestration patterns from 012/013, ingestion is organized as DAGs:

- `US_EQ_ingest_prices_D` (daily)
  - Fetch S&P 500 (and related) prices and returns for US_EQ.
  - Write to staging, QC, swap into `prices_daily`/`returns_daily`.

- `US_EQ_ingest_fundamentals_M` (monthly/quarterly)
  - Refresh fundamentals and ratios for covered issuers.

- `GLOBAL_macro_ingest_D` / `_W`
  - Refresh macro time series, yields, credit spreads, volatility indices.

- `GLOBAL_text_ingest_continuous`
  - Near-continuous ingestion of news, filings, transcripts as they appear.

- `US_EQ_ingest_execution_intraday`
  - Ingest quotes/trades and execution reports from brokers/venues (frequency tuned to cost and storage).

Each DAG uses the staging → QC → swap pattern and writes ingestion metadata so downstream components (Kronos, Monitoring) know which days/markets are fully ingested and at what quality level.

---

## 5. Initial Minimal Scope: S&P 500 US_EQ

To bootstrap the system focusing only on S&P 500 US equities, the **minimal ingestion set** is:

- `INSTRUMENTS_STATIC` for US_EQ + S&P 500 universe.
- `INDEX_CONSTITUENTS` for S&P 500.
- `PRICES_EOD` and `RETURNS_EOD` for S&P 500 constituents + SPX index.
- `FX_RATES` for USD base (and maybe EUR/JPY if needed for macro).
- `MACRO_TIME_SERIES` for a small core set (rates, inflation, key US macro indicators).
- Optionally, basic `FUNDAMENTALS_ANNUAL/QUARTERLY` for those issuers.

Other categories (news, filings, execution microstructure, alternative data) can be phased in incrementally as the core v2 stack and backtesting harness mature.

---

## 6. Summary

- **Who fetches data**: `prometheus/data_ingestion/*` modules, orchestrated by DAGs from 012/013.
- **How it is done**: provider-specific fetch → staging → normalization → QC → atomic swap into v2 tables.
- **How it is read**: engines use `prometheus/data/*` APIs, never provider SDKs directly.
- **What we fetch**: this file enumerates all external data types (market, fundamentals, macro, events, text, execution, risk, alt-data) and the responsible ingestion component.

This spec ensures data ingestion is explicit, auditable, and decoupled from engine logic, making it easy to start with S&P 500 and extend to multi-region, multi-asset coverage later.