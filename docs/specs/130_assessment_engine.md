# 130 – Assessment Engine Specification

## 1. Purpose

The Assessment Engine is Prometheus v2’s core **per-instrument decision engine**. For a given date, market, and strategy context, it:
- Computes **expected returns or scores** for instruments over specified horizons.
- Produces **signals** (e.g., buy/hold/sell or continuous scores) with confidence.
- Integrates multiple alpha families, including Fragility Alpha, into a coherent view.

Its outputs feed directly into:
- Universe Engine (140) for candidate selection.
- Portfolio & Risk Engine (150) for optimization.
- Monitoring/UI (200) for transparency.

The Assessment Engine does **not** execute trades; it provides numeric inputs to later stages.

---

## 2. Scope

- Runs daily (initially POST_CLOSE per market) to generate next-day signals.
- May later support intraday refreshes for high-impact events.
- Supports multiple **strategies** with different objectives, horizons, and constraints, all using the same core engine but possibly different configs.

Entities considered:
- Instruments `I` in a given **strategy universe** (`strategy_id`, `market_id`) at `as_of_date`.

---

## 3. Inputs

### 3.1 Identifiers and context

- `strategy_id`: which strategy’s assessment is being computed.
- `market_id`: logical market (`US_EQ`, `EU_EQ`, etc.).
- `as_of_date`: evaluation date.
- Universe of instruments `U(as_of_date, strategy_id, market_id)` provided by Universe Engine (140) or prefilters.

### 3.2 Features per instrument

For each instrument `I` in the universe, build a feature vector from:

1. **Price & factor history**
   - Recent returns over multiple horizons.
   - Realized volatility, drawdowns.
   - Factor exposures and realized factor returns (value, momentum, carry, etc.).

2. **Regime context (100)**
   - `RegimeState.regime_embedding` and `regime_label` for relevant region/market.

3. **Profile information (035)**
   - `profile_embedding(issuer, as_of_date)`.
   - Risk flags (leverage, quality, etc.).

4. **Stability & Soft-Target (110)**
   - `StabilityVector` for issuer/sector/market.
   - `FragilityMeasures` / `HighFragility` where relevant.
   - `SoftTargetClass`.

5. **Fragility Alpha (135)**
   - `FragilityAlpha(O, t, H)` for relevant entity and horizon.
   - `SoftTargetScore` for that entity.

6. **Text embeddings (030)** (optional but recommended)
   - Recent aggregated news embeddings for issuer/sector.
   - Macro embeddings for region.

### 3.3 Targets (for training)

For model training & evaluation, we define targets over horizon `H`:
- `forward_return_H(I, t)` – realized log or simple return from `t` to `t+H`.
- Possibly **risk-adjusted** versions (alpha vs factor model).

For classification-style strategies, we may bucket into deciles or labels like `OUTPERFORM`, `NEUTRAL`, `UNDERPERFORM`.

---

## 4. Outputs

### 4.1 InstrumentScore

Conceptual data structure per instrument and horizon:

```python
from dataclasses import dataclass
from datetime import date
from typing import Dict

@dataclass
class InstrumentScore:
    instrument_id: str
    as_of_date: date
    horizon_days: int
    expected_return: float  # point estimate
    score: float  # normalized score, can be used for ranking
    confidence: float  # 0..1
    signal_label: str  # e.g. STRONG_BUY, BUY, HOLD, SELL, SHORT
    alpha_components: Dict[str, float]  # contributions from families (value, momentum, fragility, etc.)
    metadata: Dict[str, float]
```

### 4.2 Batch output

For a universe `U`, the Assessment Engine returns a mapping:

```python
Dict[instrument_id, InstrumentScore]
```

for each configured horizon (e.g. 5 days, 21 days).

---

## 5. Alpha Families and Combination

The Assessment Engine combines multiple **alpha families**:

- `value_alpha` – valuations (multiples vs history/peers).
- `momentum_alpha` – medium/short-term trends.
- `quality_alpha` – profitability, stability of earnings, etc.
- `carry_alpha` – dividend yields, carry proxies.
- `fragility_alpha` – from `135_fragility_alpha.md`.
- Possibly others (growth, sentiment, etc.).

### 5.1 Per-family models

Each family may have its own model or scoring rules:
- Simple linear/GBM models for value/momentum/carry.
- More complex models for fragility.

These produce per-family scores `alpha_family_k(I, t, H)` that are then combined.

### 5.2 Combination layer

A combination model (could be linear or small MLP) maps:

```text
[alpha_family_1, alpha_family_2, ..., context_features] → expected_return, score
```

This combination is trained to improve predictive performance on forward returns/alphas while respecting constraints (e.g., stability penalties for fragile names).

Fragility Alpha and Stability inputs can be used as:
- **penalty terms** (e.g., reduce score if fragility is high for long positions).
- **direct alpha** for downside/short ideas.

---

## 6. APIs

Module: `prometheus/assessment/api.py`

```python
from datetime import date
from typing import List, Dict

class AssessmentEngine:
    """Computes per-instrument expected returns and signals for strategies."""

    def score_universe(
        self,
        strategy_id: str,
        market_id: str,
        instrument_ids: List[str],
        as_of_date: date,
        horizon_days: int,
    ) -> Dict[str, InstrumentScore]:
        """Score a list of instruments for a strategy and horizon.

        Args:
            strategy_id: Strategy identifier.
            market_id: Market identifier (e.g. US_EQ).
            instrument_ids: Universe of instruments to score.
            as_of_date: Date as of which assessment is done.
            horizon_days: Prediction horizon in trading days.
        """

    def score_strategy_default(
        self,
        strategy_id: str,
        market_id: str,
        as_of_date: date,
    ) -> Dict[str, InstrumentScore]:
        """Score the strategy's default universe at default horizon(s).

        The default universe and horizons are defined in config.
        """
```

---

## 7. Storage & Integration

### 7.1 Storage table

**Table:** `instrument_scores`

- `strategy_id` (text)
- `market_id` (text)
- `instrument_id` (text)
- `as_of_date` (date)
- `horizon_days` (int)
- `expected_return` (numeric)
- `score` (numeric)
- `confidence` (numeric)
- `signal_label` (text)
- `alpha_components` (jsonb)
- `model_id` (text) – assessment model version
- `metadata` (jsonb)

PK: (`strategy_id`, `market_id`, `instrument_id`, `as_of_date`, `horizon_days`, `model_id`).

### 7.2 Integration

- **Universe Engine (140):**
  - Can use scores to rank/select instruments or to tier the universe.

- **Portfolio & Risk Engine (150):**
  - Uses `expected_return` and `score` as primary input for optimization.

- **Meta-Orchestrator (160):**
  - Analyzes performance of assessment models across regimes and stability/fragility conditions.

- **Monitoring/UI (200):**
  - Displays top/bottom names, contributions of alpha families, signal labels.

---

## 8. Configuration

Module: `prometheus/assessment/config.py`

```python
from pydantic import BaseModel
from typing import List, Dict

class AssessmentConfig(BaseModel):
    strategy_id: str
    markets: List[str]
    horizons_days: List[int]
    base_model_id: str  # main assessment model
    alpha_family_models: Dict[str, str]  # e.g. {"value": "value-v1", "momentum": "mom-v1", "fragility": "frag-v1"}
    use_fragility_penalty: bool = True
    max_soft_target_exposure: float = 0.0  # strategy-specific
    feature_spec_id: str  # defines which features are used
```

Configs are stored in `engine_configs` with `engine_name="ASSESSMENT"`.

---

## 9. Training & Backtesting

### 9.1 Training pipeline

- Collect historical data:
  - features per instrument per `as_of_date` (see Inputs section).
  - targets: forward returns/alphas over specified horizons.
- Train per-family and combination models:
  - Validate with strict time-based splits to avoid lookahead.
- Log training data specs and metrics in `models` table.

### 9.2 Backtesting

- Incorporate Assessment Engine into backtest loops:
  - At each step T, simulate `score_universe` using only data up to T.
  - Feed scores into Universe + Portfolio engines to generate positions.
  - Evaluate portfolio P&L, risk, drawdowns.

- Slice results by:
  - regime (from Regime Engine),
  - stability/fragility states,
  - soft-target exposure.

### 9.3 Validation

- Check that signals:
  - show monotonic relationship between score deciles and forward returns.
  - degrade gracefully under regime/stability stress.
- Confirm that fragility-aware penalties reduce exposure to catastrophic drawdowns.

---

## 10. Orchestration

- The Assessment Engine runs as part of `M_engines_D` DAGs (see 013) after Regime, Stability & Soft-Target, and Profiles are updated:
  - For each `strategy_id` × `market_id` combination:
    - Evaluate `score_strategy_default` (or `score_universe` with given universe).
    - Persist `instrument_scores`.
    - Log decisions to `engine_decisions` with `engine_name="ASSESSMENT"`.

- Intraday refreshes (future):
  - Optionally re-run Assessment for subsets of instruments upon critical events (e.g., big news, macro events) using updated features.

This spec is the reference for implementing `prometheus/assessment` in Prometheus v2.