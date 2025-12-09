# Phase 1 Complete: Core Strategy Configuration

## Summary
Phase 1 is complete. The core strategy configuration has been defined and verified.

## Strategy Configuration

- **Strategy ID:** `US_CORE_LONG_EQ`
- **Market ID:** `US_EQ`
- **Universe:** S&P 500 constituents (794 instruments with historical data)
- **Objective:** Long-only US equity exposure

## Sleeve Configurations

Three sleeves with different assessment horizons:

### 1. US_CORE_LONG_EQ_H5 (5-day horizon)
- Sleeve ID: `US_CORE_LONG_EQ_H5`
- Universe ID: `US_CORE_LONG_EQ_H5_UNIVERSE`
- Portfolio ID: `US_CORE_LONG_EQ_H5_PORTFOLIO`
- Assessment Strategy ID: `US_CORE_LONG_EQ_H5_ASSESS`
- Assessment Horizon: 5 days

### 2. US_CORE_LONG_EQ_H21 (21-day horizon)
- Sleeve ID: `US_CORE_LONG_EQ_H21`
- Universe ID: `US_CORE_LONG_EQ_H21_UNIVERSE`
- Portfolio ID: `US_CORE_LONG_EQ_H21_PORTFOLIO`
- Assessment Strategy ID: `US_CORE_LONG_EQ_H21_ASSESS`
- Assessment Horizon: 21 days

### 3. US_CORE_LONG_EQ_H63 (63-day horizon)
- Sleeve ID: `US_CORE_LONG_EQ_H63`
- Universe ID: `US_CORE_LONG_EQ_H63_UNIVERSE`
- Portfolio ID: `US_CORE_LONG_EQ_H63_PORTFOLIO`
- Assessment Strategy ID: `US_CORE_LONG_EQ_H63_ASSESS`
- Assessment Horizon: 63 days

## Data Verification

✓ **Historical Database Ready:**
- 794 instruments with complete price data
- 4,338,280 price bars loaded
- Date range: 1997-01-02 to 2024-12-06 (27+ years of data)
- Covers full 2014-2024 target backtest period

## Usage

### Generate Sleeve Configuration
```bash
python scripts/setup_phase1_sleeves.py
```

### Example Backtest Command (Q1 2014 validation)
```bash
source venv/bin/activate

python prometheus/scripts/run_backtest_campaign.py \
  --market-id US_EQ \
  --start 2014-01-01 \
  --end 2014-03-31 \
  --sleeve US_CORE_LONG_EQ_H5:US_CORE_LONG_EQ:US_EQ:US_CORE_LONG_EQ_H5_UNIVERSE:US_CORE_LONG_EQ_H5_PORTFOLIO:US_CORE_LONG_EQ_H5_ASSESS:5 \
  --sleeve US_CORE_LONG_EQ_H21:US_CORE_LONG_EQ:US_EQ:US_CORE_LONG_EQ_H21_UNIVERSE:US_CORE_LONG_EQ_H21_PORTFOLIO:US_CORE_LONG_EQ_H21_ASSESS:21 \
  --sleeve US_CORE_LONG_EQ_H63:US_CORE_LONG_EQ:US_EQ:US_CORE_LONG_EQ_H63_UNIVERSE:US_CORE_LONG_EQ_H63_PORTFOLIO:US_CORE_LONG_EQ_H63_ASSESS:63 \
  --initial-cash 1000000 \
  --max-workers 3
```

## Next Steps: Phase 2

Phase 2 will backfill encoder embeddings:
1. Text embeddings from news (GPU-accelerated)
2. Numeric window embeddings from price data
3. Joint embeddings combining text + numeric
4. Profile, regime, stability, and assessment context embeddings

Estimated time: 28-92 compute hours (parallelizable)

## Notes

- Sleeves are configuration objects, not database records
- They are passed as CLI arguments to the backtest runner
- No explicit database setup was needed beyond existing migrations
- Risk parameters will be tuned during Phase 6 (optimization)
- The `build_core_long_sleeves` helper from `prometheus.backtest.catalog` generates these configurations automatically
