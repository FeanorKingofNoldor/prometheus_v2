# Market Regime Detection Engine – Detailed Plan

## 1. Purpose & Scope

Detect market regime transitions BEFORE they fully play out using 15 forward-looking indicators. Not a reactive coincident system—the goal is to see through the windshield, not the rearview mirror. Provides regime state (6 classifications) and transition probabilities to inform strategy parameter adjustments and risk management.

**Philosophy:**
- Dormant 95% of the time (most indicators normal)
- Gradual parameter adaptation as warnings cluster
- Only aggressive action when multiple domains confirm danger
- Forward-looking indicators that lead equity market moves by 1-6 months


## 2. Regime Classifications (6 States)

**1. Risk-On / Low Vol** – Goldilocks conditions, full allocation safe
**2. Risk-On / High Vol** – Growth continuing but choppy, tighten risk
**3. Transition / Rotation** – No clear trend, stock-picking matters, sector rotation
**4. Risk-Off / Grinding** – Slow deterioration, defensive posture begins
**5. Risk-Off / Panic** – Forced liquidation, correlation → 1, capital preservation mode
**6. Policy Response / Recovery** – Central bank rescue active, bargain hunting begins

## 3. High-Level Architecture

Modules under `regime/` (renamed from `macro/`):

- `indicators/` – 15 forward-looking indicators organized by domain:
  - `credit.py` – HY/IG spreads, leveraged loans, CDS basis, IG issuance
  - `rates.py` – 2-10Y curve, real yields, Eurodollar futures
  - `internals.py` – A/D line, new highs/lows, small vs. large cap
  - `flows.py` – Equity fund flows, margin debt
  - `macro.py` – ISM new orders, LEI, Sahm rule
- `classification/` – Hierarchical decision tree (not weighted scoring)
  - `decision_tree.py` – Step-by-step regime classification logic
  - `transition_matrix.py` – Base probabilities + dynamic adjustment
- `llm_enrichment/` – Single focused LLM task
  - `guidance_tracker.py` – Corporate forward guidance sentiment from earnings calls
- `engine/` – Daily orchestration: load indicators → classify → calculate transitions
- `storage/` – Writes `regime_state`, `regime_transitions`, `indicator_readings`
- `api/` – `get_current_regime()`, `get_transition_probabilities()`, `get_warning_clusters()`


## 4. The 15 Forward-Looking Indicators

### Category 1: Credit Market (4 indicators – lead by 3-6 months)
1. **HY vs. IG Spread Differential** – Credit quality bifurcation signal
2. **Leveraged Loan Market** – CLO spreads, covenant-lite performance
3. **IG New Issuance vs. Refinancing** – Funding market health
4. **CDS-Bond Basis** – Informed money hedging signal

### Category 2: Yield Curve & Rates (3 indicators – lead by 0-3 months)
5. **2-10Y Curve UN-inversion Speed** – Rapid steepening = recession starting
6. **Real Yields (TIPS)** – Policy restrictiveness vs. growth
7. **Eurodollar Futures Curve** – Market's Fed expectations

### Category 3: Market Internals (3 indicators – lead by 1-3 months)
8. **Advance-Decline vs. Price Divergence** – Breadth deterioration
9. **New Highs/Lows Rate of Change** – Distribution signal
10. **Small Cap vs. Large Cap** – Leverage/cyclical sensitivity

### Category 4: Positioning & Flows (2 indicators – lead by weeks)
11. **Equity Fund Flows (Institutional)** – Smart money positioning
12. **Margin Debt** – Leverage saturation

### Category 5: Macro Leading (3 indicators – lead by 3-12 months)
13. **ISM Manufacturing New Orders** – Forward demand
14. **Leading Economic Index (LEI)** – Composite forward indicator
15. **Sahm Rule (Unemployment)** – Recession trigger (never failed historically)

### LLM Enrichment (1 task)
16. **Corporate Guidance Sentiment** – Weekly earnings call analysis, % guiding down

## 5. Data Contracts

### 5.1 Inputs

- Historical DB:
  - `macro_time_series` for macro/rates data
  - Market data feeds for credit/equity indicators
  - Earnings call transcripts (via data ingestion or API)
- Config:
  - Indicator thresholds (percentile-based, not absolute)
  - Decision tree logic definitions
  - Transition matrix (empirical from backtest)

### 5.2 Outputs

- **regime_state** (daily):
  - `date` (PK)
  - `regime_classification` (1-6)
  - `confidence` (0-1, based on signal clarity)
  - `alert_level` (GREEN/YELLOW/ORANGE/RED)
  - `warning_count` (how many of 15 indicators flashing)
  - `contributing_indicators` (JSON array of which indicators triggered)
  - `llm_context` (text summary from guidance tracker)

- **regime_transitions** (events):
  - `transition_date`
  - `from_regime`
  - `to_regime`
  - `duration_in_prior` (days)
  - `trigger_indicators` (JSON)
  - `lead_time_actual` (post-mortem: how many days before equity moved)

- **indicator_readings** (time series):
  - `date`
  - `indicator_name`
  - `value`
  - `percentile_1y` (vs. 1-year history)
  - `percentile_5y` (vs. 5-year history)
  - `rate_of_change_5d`
  - `rate_of_change_20d`
  - `warning_flag` (boolean: above threshold?)

- **transition_probabilities** (daily):
  - `date`
  - `current_regime`
  - `to_regime` (for each possible target)
  - `base_probability` (from empirical matrix)
  - `adjusted_probability` (based on indicator momentum)

API:
- `get_current_regime()` → Current state + confidence + warnings
- `get_transition_probabilities()` → Dict of next-regime probabilities
- `get_warning_clusters()` → Which indicator categories are flashing
- `get_indicator_detail(indicator_name)` → Time series + current reading


## 6. Classification Logic: Hierarchical Decision Tree (Not Scoring)

**Step 1: Check for Crisis (override everything)**
```
IF (any extreme reading):
  - VIX > 40 AND credit spreads > 90th percentile AND breadth collapsing
  → Risk-Off / Panic
  DONE.
```

**Step 2: Check for Central Bank Rescue**
```
IF (recent emergency policy AND VIX declining from highs AND spreads stabilizing):
  → Policy Response / Recovery
  DONE.
```

**Step 3: Check Credit/Funding Stress**
```
IF (credit indicators show consistent widening):
  → Risk-Off / Grinding
ELSE continue...
```

**Step 4: Check Volatility Regime**
```
IF (VIX < 15 AND breadth healthy AND credit tight):
  → Risk-On / Low Vol
IF (VIX 20-30 AND breadth healthy AND credit okay):
  → Risk-On / High Vol
```

**Step 5: Default**
```
ELSE → Transition / Rotation
```

### 6.1 Warning Cluster Logic (for Alert Levels)

Count how many of the 15 indicators are flashing warnings (above threshold).
Require **cross-domain confirmation** (at least 2 different categories).

**GREEN (All Clear):**
- < 3 indicators flashing
- Action: Full risk-on, no constraints

**YELLOW (Early Warning):**
- 3-5 indicators flashing, at least 2 categories
- Action: Increase monitoring, tighten new entry criteria, reduce max position size slightly

**ORANGE (Trouble Brewing):**
- 6-9 indicators flashing, credit + curve + internals all showing stress
- Action: Reduce leverage 25-50%, tilt defensive, pause mean-reversion strategies

**RED (Windshield Cracked):**
- 10+ indicators flashing, multiple severe readings
- Action: Defensive posture, 50%+ cash or hedged

### 6.2 Daily Classification Flow

1. **Load data** for all 15 indicators
2. **Calculate percentiles and thresholds** for each
3. **Run decision tree** → regime classification
4. **Count warnings** → alert level
5. **Calculate transition probabilities** (base matrix + indicator momentum adjustment)
6. **Run LLM guidance tracker** (weekly batch, cache results)
7. **Write outputs** to regime_state, indicator_readings, transition_probabilities
8. **Log regime transitions** if classification changed from prior day


## 7. Integration: Regime → Strategy Parameter Adaptation

**Not just position sizing—adapt HOW strategies operate:**

### Risk-On / Low Vol
- Position sizing: 100% of normal
- Entry bar: Normal conviction threshold
- Stop distances: Wide (give room)
- Max position size: 5%
- Strategy mix: All strategies active

### Risk-On / High Vol
- Position sizing: 80% of normal
- Entry bar: Higher conviction required
- Stop distances: Tighter (-5% vs. -8%)
- Max position size: 4%
- Strategy mix: All active, favor momentum

### Transition / Rotation
- Position sizing: 60% of normal
- Entry bar: Highest conviction only
- Stop distances: Tight (-5%)
- Max position size: 3%
- Strategy mix: Pause mean-reversion, favor stock-picking

### Risk-Off / Grinding
- Position sizing: 40% of normal
- Entry bar: Defensive sectors only
- Stop distances: Very tight (-3%)
- Max position size: 3%
- Strategy mix: Pause growth/cyclical, defensive value only

### Risk-Off / Panic
- Position sizing: 0-20% of normal
- Entry bar: Exit mode, not entry mode
- Stop distances: Immediate
- Strategy mix: Capital preservation, consider shorts/hedges

### Policy Response / Recovery
- Position sizing: 100-120% of normal (aggressive)
- Entry bar: Lower threshold (bargain hunting)
- Stop distances: Wide (let bounce play out)
- Max position size: 6%
- Strategy mix: Quality value aggressive, momentum resumes

## 8. Interactions with Other Components

- **System Stability Engine (formerly Black Swan)**:
  - If entity soft-target scores elevate → increase transition probability to Risk-Off
  - If Stability Engine goes RED → override regime to Risk-Off / Panic
- **Universe Selection**:
  - Regime determines sector tilts (defensive vs. cyclical)
  - Alert level determines universe size (smaller in ORANGE/RED)
- **Assessment Engine**:
  - Regime context fed into decision prompts
  - Higher bar for entries in Risk-Off regimes
- **Risk Management**:
  - Alert level directly sets max exposure, leverage, concentration limits
- **Backtesting**:
  - Regime-aware backtests required to validate parameter adaptation
- **Meta Orchestrator**:
  - Analyzes performance by regime to tune parameters
  - Quarterly reviews of transition matrix accuracy


## 9. Backtesting & Calibration

### 9.1 Historical Labeling (One-Time)
- Manually classify last 20 years month-by-month into 6 regimes
- This is ground truth for validation

### 9.2 Indicator Validation
- For each historical regime, check:
  - Would decision tree have classified correctly?
  - Which indicators gave earliest warning?
  - Which gave false signals?
- Tune thresholds until >80% classification accuracy

### 9.3 Lead Time Measurement
- For major transitions (2008 crash, 2020 COVID, 2022 bear):
  - How many months in advance did 6+ indicators flash?
  - What was optimal "act now" threshold?
- Target: 1-4 month early warning on major regime shifts

### 9.4 False Positive Analysis
- Count times when 6+ indicators flashed but NO regime change in 6 months
- Acceptable rate: 20-30% (2-3 false alarms per decade)
- If >50%, thresholds too sensitive

### 9.5 Strategy Performance Validation
- Backtest strategies with and without regime-based parameter adaptation
- Measure: Sharpe ratio improvement, max drawdown reduction
- Regime adaptation must show >0.3 Sharpe improvement or >10% drawdown reduction
- If not, the system isn't adding value

## 10. Implementation Phases

### Phase 1 (Month 1): Foundation
- Implement 5 easiest indicators: VIX, IG-HY spread, 2-10Y curve, A/D line, ISM new orders
- Get data pipeline working
- Prove daily calculation

### Phase 2 (Month 2): Credit Indicators
- Add leveraged loans, CDS basis, IG issuance, real yields
- These require better data sources but high signal value

### Phase 3 (Month 3): Complete Set
- Add remaining internals, positioning, macro indicators
- Implement decision tree classification
- Build transition matrix from historical data

### Phase 4 (Month 4): LLM Layer
- Build earnings call guidance tracker
- Weekly batch processing
- Integrate sentiment into warning clusters

### Phase 5 (Month 5): Integration
- Wire regime state into risk management constraints
- Wire alert levels into strategy parameter adaptation
- Build monitoring dashboard

### Phase 6 (Month 6+): Live Validation
- Paper trade with regime-aware system
- Compare to baseline (no regime adaptation)
- Tune thresholds based on real-world behavior
- Iterate monthly

## 11. Failure Modes & Safeguards

- **Data missing:** If >3 indicators unavailable, mark regime UNKNOWN with low confidence, downstream systems go neutral/defensive
- **Whipsaw protection:** Require regime to hold for 3 consecutive days before declaring transition (except RED alerts)
- **Override capability:** Human operators can force regime classification if system is clearly wrong
- **Version tracking:** Store decision_tree_version with each regime_state row for reproducibility
- **Regular recalibration:** Quarterly reviews of thresholds and transition matrix
- **Post-mortem logging:** Every regime transition gets reviewed: was it correct? Early enough? False positive?

## 12. Success Metrics

- **Lead time:** Average days of early warning before major regime shifts (target: 30-90 days)
- **Classification accuracy:** % of correctly classified historical regimes (target: >80%)
- **False positive rate:** Warnings that didn't lead to regime change (target: <30%)
- **Sharpe improvement:** Regime-aware strategies vs. baseline (target: +0.3)
- **Drawdown reduction:** Max drawdown with regime adaptation vs. without (target: -10%+)
- **Warning cluster precision:** When 6+ indicators flash, how often is it real? (target: >70%)

## Future: Joint numeric+text regime embedding space

In a later phase, the Regime Engine will produce and consume regime
embeddings from a joint numeric+text space that combines market windows and
macro/news context, as outlined in
`docs/new_project_plan/joint_embedding_shared_spaces_plan.md`. This shared
space will support regime clustering, similarity search, and regime-aware
analytics for other engines.

## Future: Mathematical tools roadmap for regimes

To keep the macro regime service extensible without rewriting core
infrastructure each iteration, we introduce a staged roadmap for
math-heavy components. Only the v2 items are candidates for near-term
implementation; later items are explicitly deferred.

- **v2 – Distribution-shift and information-theoretic features**
  - Add rolling entropy and differential entropy of key market and credit
    indicators as regime features.
  - Compute KL/JS divergence between current indicator distributions and
    regime-specific baselines ("distance from normal").
  - Use simple mutual information estimates between indicators and
    historical regime labels to rank which indicators are actually
    informative.
- **v3 – Temporal structure and complexity features**
  - Add autocorrelation / mixing-time diagnostics on core indicators to
    inform regime half-lives and transition-speed assumptions.
  - Add basic spectral and/or wavelet energy features (e.g. dominance of
    slow vs fast components in volatility and breadth) as additional
    inputs to the classifier.
  - Optionally track compression-based complexity (e.g. Lempel–Ziv
    ratios) of price/indicator windows as a separate "complexity
    regime" axis.
- **v4+ – State-space and filtering models**
  - Layer a Kalman/unscented Kalman or related state-space filter on top
    of the rule-based classifier to smooth noisy indicator readings and
    provide uncertainty estimates per regime state.
  - Use Fisher-information-style diagnostics to quantify how much data
    is available to reliably detect transitions between specific pairs
    of regimes.

In a later phase, the Regime Engine will produce and consume regime
embeddings from a joint numeric+text space that combines market windows and
macro/news context, as outlined in
`docs/new_project_plan/joint_embedding_shared_spaces_plan.md`. This shared
space will support regime clustering, similarity search, and regime-aware
analytics for other engines.
