# 042 – EODHD Data Catalog and Schema Mapping

## 1. Purpose

This document is the **vendor-specific catalog** for the EODHD data
provider. It answers two questions:

- What data *types* and key fields can we get from EODHD?
- How do those map onto Prometheus v2 database tables and planned
  ingestion modules?

When we design a new engine or feature, this file is the first place to
check what is realistically available without changing providers.

This catalog is intentionally **coarse-grained**: it lists data types,
endpoints, and representative fields, not every raw key in EODHD’s
payloads. For detailed field-level info, defer to EODHD’s own
documentation.

---

## 2. Market & Reference Data

### 2.1 End-of-day prices (EOD OHLCV)

- **EODHD endpoints**
  - `GET /eod/{symbol}` – full or partial history of OHLCV bars.
- **Key payload fields**
  - `date` – trading date (YYYY-MM-DD)
  - `open`, `high`, `low`, `close`
  - `adjusted_close` – price adjusted for splits/dividends
  - `volume`
- **Prometheus tables**
  - `historical_db.prices_daily`
    - `instrument_id` – mapped from Prometheus `instruments.instrument_id`
    - `trade_date` ← `date`
    - `open`, `high`, `low`, `close`, `adjusted_close`, `volume`
    - `currency` – from `instruments.currency` (or EODHD metadata)
    - `metadata` – JSON blob (e.g. `{"source": "eodhd"}`)
- **Ingestion module**
  - `prometheus.data_ingestion.eodhd_client.EodhdClient`
  - `prometheus.data_ingestion.eodhd_prices` (already implemented)

### 2.2 Intraday prices (future)

- **EODHD**: intraday OHLCV bars (1m/5m/etc.) for many equities/FX/crypto.
- **Prometheus tables (planned)**
  - `prices_intraday_*` family – **not yet migrated**; will be added
    once we have intraday strategies.
- **Use cases**
  - Execution quality, slippage models, intraday backtests.

### 2.3 Corporate actions (splits & dividends)

- **EODHD endpoints**
  - Corporate actions API for splits, dividends, symbol changes, etc.
- **Representative fields**
  - `date`
  - `type` – `SPLIT`, `DIVIDEND`, `SPINOFF`, etc.
  - `split_ratio`, `dividend_amount`, `currency`
- **Prometheus tables (planned)**
  - `historical_db.corporate_actions` (not yet migrated; name reserved
    in 040 spec).
  - `prices_daily.metadata` for soft linkage when needed.
- **Use cases**
  - Correct adjustment of historical prices/returns.
  - Events for stability / fragility models.

### 2.4 Index & ETF data

- **EODHD**
  - EOD prices for indices and ETFs (same `/eod` endpoint).
  - ETF/Mutual fund holdings snapshots.
- **Prometheus mapping**
  - Indices/ETFs are just `instruments` with `asset_class="ETF"` or
    `asset_class="INDEX"` → `prices_daily` as usual.
  - Fund holdings → future table `fund_holdings` (not yet migrated).

---

## 3. Fundamentals & Company Data

EODHD exposes detailed fundamental data at annual and quarterly
frequencies for many equities and funds.

### 3.1 Financial statements & fundamentals

- **Data**
  - Income statement, balance sheet, cash flow.
  - Key ratios: margins, ROE, leverage, growth metrics, etc.
- **Prometheus tables (planned)**
  - `historical_db.financial_statements` (spec’d in 040, not yet
    migrated in this repo).
  - `historical_db.fundamental_ratios` (spec’d in 040).
- **Intended ingestion**
  - `prometheus.data_ingestion.fundamentals_eodhd` (future module).
- **Downstream users**
  - Profiles engine (issuer structural risk, quality metrics).
  - Stability / Soft-Target v2.
  - Fragility alpha models.

### 3.2 Company metadata

- **Data**
  - Company short/long name, sector/industry, country, ISIN, exchange,
    listings, etc.
- **Prometheus tables**
  - `runtime_db.issuers` – core issuer metadata (already migrated).
  - `runtime_db.instruments` – symbol, exchange, currency, status.
- **Intended usage**
  - Initial seeding of `issuers` and `instruments` (one-time or
    occasionally refreshed).

---

## 4. Alternative / Derived Market Data

### 4.1 Factors & risk premia (vendor or self-computed)

EODHD itself does not provide academic factor series, but we may derive
factors from EODHD prices or load external factor series.

- **Prometheus tables (now migrated in 0011)**
  - `historical_db.factors_daily`
    - `factor_id`, `trade_date`, `value`, `metadata`
  - `historical_db.instrument_factors_daily`
    - `instrument_id`, `trade_date`, `factor_id`, `exposure`
  - `historical_db.correlation_panels`
    - Panel metadata + matrix reference (e.g. path to stored matrix).
- **Intended ingestion**
  - Derived from `prices_daily` + possibly exogenous factor vendor.

### 4.2 Derived returns & volatility (already implemented)

- **Data**
  - 1/5/21-day returns, 21/63-day realised vol.
- **Prometheus tables**
  - `returns_daily`, `volatility_daily` (migrated in 0002, populated by
    `prometheus.data_ingestion.derived.returns_volatility`).
- **Source**
  - Derived solely from EODHD `prices_daily` (no direct EODHD endpoint).

---

## 5. Text & Event Data

EODHD exposes several classes of textual and event-like data (news,
calendar events, earnings, dividends). Only some will be used; this
catalog is meant to show what fits where.

### 5.1 News articles & headlines

- **EODHD**
  - News/headlines API for equities, indices, and macro topics.
- **Prometheus tables (now migrated in 0011)**
  - `news_articles`
    - `article_id` (bigserial PK)
    - `timestamp` (UTC)
    - `source`
    - `language`
    - `headline`
    - `body`
    - `metadata` (e.g. tickers, categories, importance flags)
  - `news_links`
    - `article_id` FK → `news_articles`
    - `issuer_id` (nullable)
    - `instrument_id` (nullable)
- **Intended ingestion**
  - `prometheus.data_ingestion.news_eodhd` (future) will:
    - Write rows into `news_articles`.
    - Map articles to issuers/instruments via `news_links`.
- **Downstream users**
  - Latent State Engine (issuer/macro state).
  - Profiles text features.
  - Black Swan / crisis detectors.

### 5.2 Earnings & corporate events

- **EODHD**
  - Earnings calendar, earnings reports, dividends, splits, etc.
- **Prometheus tables (now migrated)**
  - `filings`
    - For full filings and reports; `text_ref` points to storage.
  - `earnings_calls`
    - `call_date`, `transcript_ref`, `metadata`.
  - `macro_events`
    - `event_type`, `timestamp`, `country`, `description`, `text_ref`,
      `metadata`.
- **Not yet created but implied**
  - `dividend_events`, `corporate_actions` (see 040 spec) – will be
    added as separate migrations when we decide on exact shape.
- **Intended ingestion**
  - `prometheus.data_ingestion.events_earnings_eodhd`
  - `prometheus.data_ingestion.events_dividends_eodhd`
  - `prometheus.data_ingestion.macro_events_eodhd`

---

## 6. Macro, FX, and Cross-Asset Data

EODHD offers various macro and FX series (indices, FX pairs, economic
indicators). We do **not** aim to use every series; the goal is to know
what buckets exist.

### 6.1 Macro time series (future schema)

- **Potential data**
  - Indices such as major equity indices, volatility indices (VIX),
    rates/yields, etc.
  - These can either be treated as instruments (and logged in
    `prices_daily`) or as scalar macro series.
- **Prometheus tables (planned)**
  - `macro_time_series` as per 040 spec (not yet migrated) for scalar
    macro indicators where modelling them as instruments is awkward.

### 6.2 FX & crypto

- **EODHD**
  - EOD and intraday prices for FX pairs and crypto assets.
- **Prometheus mapping**
  - Represent FX pairs and crypto as `instruments` with appropriate
    `asset_class` (`FX`, `CRYPTO`) and use `prices_daily` exactly as for
    equities.

---

## 7. Summary of Current Schema Coverage

After migration `0011_historical_text_and_factors`, the **historical
DB** supports the following EODHD-backed or compatible data families:

1. **Core market data**
   - `prices_daily` – from EODHD EOD prices (implemented).
   - `returns_daily`, `volatility_daily` – derived from prices
     (implemented).
2. **Factors & correlations**
   - `factors_daily` – internal or external factor series.
   - `instrument_factors_daily` – per-instrument exposures.
   - `correlation_panels` – panel metadata + matrix refs.
3. **Text & events**
   - `news_articles`, `news_links` – mapped from EODHD news APIs.
   - `filings`, `earnings_calls` – mapped from EODHD earnings/filings
     data.
   - `macro_events` – mapped from macro/calendar endpoints.
4. **Embeddings** (from earlier migrations)
   - `text_embeddings`, `numeric_window_embeddings`, `joint_embeddings`
     – store embeddings derived from any of the above.

What is **not** yet migrated, but is part of the long-term plan:

- `macro_time_series` (scalar macro indicators).
- `corporate_actions`, `dividend_events` tables.
- Execution/microstructure tables (quotes, trades, etc.).

Whenever we need a new feature, the workflow should be:

1. Check 042 (this file) to see whether EODHD provides the necessary
   raw data and whether a target table already exists.
2. If a schema exists but no ingestion code, add the ingestion module
   under `prometheus/data_ingestion/` and a small CLI/backfill driver in
   `prometheus/scripts/`.
3. If no schema exists yet, extend the data model (020), add a
   migration, then implement ingestion.
