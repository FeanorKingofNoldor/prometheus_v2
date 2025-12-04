# 110 – Stability & Soft-Target Engine Specification

## 1. Purpose

The Stability & Soft-Target Engine quantifies:
- **Stability** – how stable/robust markets, entities, and portfolios are under current conditions.
- **Fragility / Soft-Target status** – how vulnerable they are to plausible shocks, without predicting the shocks themselves.

It provides:
- Continuous **stability vectors** `S(O, t)` per entity/portfolio.
- Scenario-based **fragility measures** `V(O, t)` for entities and portfolios.
- Soft-target flags that indicate entities that are both fragile and structurally weak.

These outputs are used by:
- Fragility Alpha (`135_fragility_alpha.md`) via `WeakProfile`, `Instability`, `HighFragility` components.
- Assessment Engine (130) to penalize trades in fragile contexts.
- Universe Engine (140) to filter/prioritize entities.
- Portfolio & Risk (150) to adjust risk budgets and constraints.
- Monitoring/UI (200) to surface system stability and soft targets.

---

## 2. Scope and Entities

Entities `O` include:
- **Market/region level**: `MARKET` entities such as US_EQ, EU_EQ, JP_EQ.
- **Issuers**: companies, sovereigns (`issuer_id`).
- **Sectors/indices**.
- **Currencies/FX pairs**.
- **Portfolios**: internal portfolios defined in `portfolios`.
- **Tier-1 system entities** from the Stability entity registry:
  - Global systemically important banks (G‑SIBs).
  - Key sovereigns whose crises create global contagion.
  - **Chokepoints** (critical infrastructure/trade routes/networks like major straits, canals, SWIFT).
  - Central banks (Fed, ECB, BoJ, PBoC, BoE, SNB, etc.).
  - Critical commodities (oil, gas, semiconductors, wheat, etc.).
- **Key institutional positions (roles)** – e.g. US President, Fed Chair, ECB President, heads of major regulators – modeled as `POSITION` entities whose **role is stable but occupant changes over time**.

Implementation detail:
- The concrete Tier-1 registry (initially ~70 entities) lives in `prometheus/stability/entities.py`.
- Role-based `POSITION` entities refer to institutional roles, not hard-coded names; a separate mapping (data layer) associates each role with the current person over time. This ensures the engine tracks the *right* individuals for a given date without baking names into the core logic.

Stability & Soft-Target runs daily per `as_of_date` (initially POST_CLOSE) but some indicators may be computed intraday later.

---

## 3. Inputs

### 3.1 From Regime Engine (100)

- `RegimeState(as_of_date, region, regime_label, regime_embedding, confidence)`.

### 3.2 From Profiles (035)

- `ProfileSnapshot` per issuer/sector:
  - `structured` fundamentals and macro data.
  - `profile_embedding`.
  - `risk_flags` (e.g., leverage_score, debt_sustainability_score, external_vulnerability_score).

### 3.3 Market microstructure & risk features

From `historical_db`:
- Price and return time series.
- Volume and liquidity proxies.
- Spread (if available).
- Realized volatility (`volatility_daily`).
- Correlation panels.

Engineered features:
- Liquidity indicators (e.g., turnover, bid-ask spreads, Amihud-type metrics where possible).
- Volatility indicators.
- Cross-asset and cross-entity correlations.

### 3.4 Scenario library

From a scenario definition module (may live under `prometheus/portfolio` or a shared location):
- A curated set of **shock scenarios** `S = {S_k}`:
  - Parametric shocks (e.g., +200bps parallel shift, -20% equity indices, +X bps credit spreads, FX moves).
  - Historical episodes (e.g., 2008-like, Eurozone crisis-like, COVID-like) captured as multi-asset shock vectors.

---

## 4. Outputs

### 4.1 StabilityVector

For each entity or portfolio `O` at time `t`:

```python
from dataclasses import dataclass
from datetime import date
from typing import Dict

@dataclass
class StabilityVector:
    entity_type: str  # MARKET, ISSUER, SECTOR, FX, PORTFOLIO
    entity_id: str
    as_of_date: date
    stability_score: float  # 0 (unstable) .. 1 (very stable)
    components: Dict[str, float]  # e.g. {"liquidity": 0.7, "vol": 0.4, "contagion": 0.3}
    metadata: Dict[str, float]
```

### 4.2 FragilityMeasures

Scenario-based fragility for entities and portfolios:

```python
@dataclass
class FragilityMeasures:
    entity_type: str
    entity_id: str
    as_of_date: date
    expected_shortfall: float  # ES under scenario distribution
    worst_case_loss: float
    scenario_losses: Dict[str, float]  # scenario_id -> loss
    metadata: Dict[str, float]
```

From these, we can derive:
- `HighFragility(O,t) ∈ [0,1]` – normalized fragility index.

### 4.3 SoftTarget flags

- A binary or categorical flag:

```text
SoftTargetClass(O, t) ∈ {NONE, WATCHLIST, SOFT_TARGET}
```

based on a combination of:
- low `stability_score`,
- high `HighFragility`,
- weak profiles (risk_flags) and regime context.

---

## 5. Stability Computation

### 5.1 Component scores

For each entity/portfolio, compute component scores in [0,1], where higher = more stable:

- `liquidity_component` – based on turnover, spreads, depth.
- `vol_component` – inverse of realized vol relative to history.
- `contagion_component` – inverse of **empirically learned contagion impact** from other entities, especially sovereigns.
- `fundamental_component` – from profile risk_flags (e.g., 1 - leverage_score).

`contagion_component` deserves special treatment:
- For **sovereigns**, we learn from history how shocks to that sovereign have propagated to:
  - local banks and corporates,
  - neighboring countries,
  - asset classes (FX, rates, equities).
- For **non-sovereign entities**, we learn their sensitivity to:
  - sovereign shocks (home country + key funding/market countries),
  - sector/region shocks (e.g., CRE, regional banks),
  - systemic stress indicators (from Regime & crisis pattern specs).

The contagion effect is estimated using backtests over historical crises (see 045 and 180):
- identify sovereign/sector shock episodes (Thailand 1997, Korea 1997–98, Indonesia 1997–98, Russia 1998, Argentina 2001, Euro crisis, 2008, etc.),
- measure realized losses/vol/credit spreads for each entity following those shocks,
- fit models mapping sovereign/sector features → conditional impact distribution on other entities.

`contagion_component(O, t)` is then a **stability score** derived from the expected impact of relevant sovereign/sector shocks on `O` given the current state (regimes, debt structure, exposures), not just raw correlations.

### 5.2 Aggregation

Define:

```text
stability_score(O, t) = w_L * liquidity_component
                        + w_V * vol_component
                        + w_C * contagion_component
                        + w_F * fundamental_component

# weights w_* may depend on entity_type and regime.
```

`components` in `StabilityVector` store the individual pieces; overall `stability_score` is their weighted sum or a more robust aggregation function (e.g., min/percentile).

Regime-aware adjustment:
- In regimes naturally high in volatility (e.g., risk-on with high realized vol but functioning markets), adjust expectations so that `vol_component` isn’t always low.

---

## 6. Fragility (Scenario-Based)

### 6.1 Scenario application

For each entity/portfolio `O` and scenario `S_k`:
- Map scenario shocks onto:
  - relevant instruments (price/return shocks),
  - factors (factor return shocks),
  - FX/rates as needed.

- For portfolios:
  - Use Portfolio & Risk Engine’s pricing logic to revalue positions under `S_k`.

- For entities:
  - Use proxies for issuer-level impact (e.g., sector/index proxies, CDS spread changes, etc.).

### 6.2 Aggregation into fragility metrics

Compute:

```text
scenario_losses_k = Loss(O | S_k)  # positive = loss

expected_shortfall = ES_alpha over {scenario_losses_k}
worst_case_loss = max_k scenario_losses_k
```

Normalize to [0,1] scale relative to historical distribution or domain thresholds to get `HighFragility(O,t)`.

These fragility metrics **do not** predict when shocks will occur; they quantify how bad it gets if they do.

---

## 7. Soft-Target Classification

Soft targets combine:
- Low stability,
- High fragility,
- Weak fundamentals/profiles,
- Regime-aware context.

Example rule:

```text
if stability_score < s_thresh
   and HighFragility > f_thresh
   and ProfileWeakness > p_thresh:
       SoftTargetClass = SOFT_TARGET
elif stability_score < s_watch
   or HighFragility > f_watch:
       SoftTargetClass = WATCHLIST
else:
       SoftTargetClass = NONE
```

Where thresholds `s_thresh`, `f_thresh`, `p_thresh`, `s_watch`, `f_watch` are calibrated from history by comparing to known crises/defaults.

This classification is **distinct from** Fragility Alpha’s scoring but conceptually aligned; Fragility Alpha will build on these signals to produce tradeable alphas.

---

## 8. Learning Sovereign Contagion Patterns (Backtesting)

To avoid hard-coding crisis narratives, the engine must **learn** sovereign contagion behavior from data as part of the backtesting and research workflow:

- Define a library of historical sovereign/sector crisis episodes (see 045 and 170):
  - e.g., THB devaluation 1997, KRW crisis, IDR/Rupiah collapse, Russia 1998, Argentina 2001, Euro periphery 2010–2012, US 2008, UBS–Credit Suisse 2023.
- For each episode, construct panels of:
  - sovereign-level features (debt metrics, FX regime, Elite Exit Score, RegimeState),
  - entity-level outcomes (drawdowns, vol spikes, default events, credit spread moves) for banks, corporates, sectors, neighbors.
- Fit and validate models that estimate, for a given sovereign/sector state today:
  - the **conditional distribution of impacts** on other entities over specified horizons (e.g., 1M, 3M, 6M),
  - contagion channels (financial linkages, trade, funding, correlation networks).

This learning step is part of the **backtesting/validation loop** (see 180), not a live online learner:
- models are trained on historical data,
- evaluated out-of-sample and across multiple crises/countries,
- versioned as `model_id` and only promoted via Kronos and testing gates.

The resulting contagion models provide inputs to:
- `contagion_component` in `StabilityVector`,
- fragility scenario mappings (how sovereign shocks map to entity-level `Loss(O | S_k)`),
- SoftTarget classification for entities whose fate historically depends heavily on sovereign behavior.

---

## 8. APIs

Module: `prometheus/stability/api.py`

```python
from datetime import date
from typing import List, Dict

class StabilityEngine:
    """Computes stability and fragility metrics for entities and portfolios."""

    def score_entities(
        self,
        entity_type: str,
        entity_ids: List[str],
        as_of_date: date,
    ) -> Dict[str, StabilityVector]:
        """Compute stability vectors for a list of entities.

        Args:
            entity_type: One of {"MARKET", "ISSUER", "SECTOR", "FX"}.
            entity_ids: List of entity identifiers.
            as_of_date: Date of evaluation.
        """

    def score_portfolios(
        self,
        portfolio_ids: List[str],
        as_of_date: date,
    ) -> Dict[str, StabilityVector]:
        """Compute stability vectors for portfolios.
        """

    def fragility_entities(
        self,
        entity_type: str,
        entity_ids: List[str],
        as_of_date: date,
    ) -> Dict[str, FragilityMeasures]:
        """Compute scenario-based fragility metrics for entities.
        """

    def fragility_portfolios(
        self,
        portfolio_ids: List[str],
        as_of_date: date,
    ) -> Dict[str, FragilityMeasures]:
        """Compute scenario-based fragility metrics for portfolios.
        """

    def soft_target_classes(
        self,
        entity_type: str,
        entity_ids: List[str],
        as_of_date: date,
    ) -> Dict[str, str]:
        """Classify entities into soft-target classes.
        """
```

---

## 9. Storage & Integration

### 9.1 Storage tables

**Table:** `stability_vectors`

- `entity_type` (text)
- `entity_id` (text)
- `as_of_date` (date)
- `stability_score` (numeric)
- `components` (jsonb)
- `model_id` (text)
- `metadata` (jsonb)

PK: (`entity_type`, `entity_id`, `as_of_date`, `model_id`).

**Table:** `fragility_measures`

- `entity_type` (text)
- `entity_id` (text)
- `as_of_date` (date)
- `expected_shortfall` (numeric)
- `worst_case_loss` (numeric)
- `scenario_losses` (jsonb)
- `model_id` (text)
- `metadata` (jsonb)

PK: (`entity_type`, `entity_id`, `as_of_date`, `model_id`).

**Table:** `soft_target_classes`

- `entity_type` (text)
- `entity_id` (text)
- `as_of_date` (date)
- `class` (text: `NONE`, `WATCHLIST`, `SOFT_TARGET`)
- `model_id` (text)
- `metadata` (jsonb)

PK: (`entity_type`, `entity_id`, `as_of_date`, `model_id`).

### 9.2 Integration

- **Fragility Alpha (135):**
  - Uses `stability_vectors`, `fragility_measures`, and `soft_target_classes` as inputs.

- **Assessment Engine (130):**
  - Uses stability_socre and components as features/penalties in expected-return models.

- **Universe Engine (140):**
  - Filters out or caps exposure to severe soft targets for certain strategies.

- **Portfolio & Risk (150):**
  - Integrates fragility measures into risk constraints and scenario analysis.

- **Monitoring (200):**
  - Exposes global/market stability indices and counts of soft targets by region.

---

## 10. Configuration

Module: `prometheus/stability/config.py`

```python
from pydantic import BaseModel

class StabilityConfig(BaseModel):
    markets: list[str] = ["US_EQ"]
    window_length_days: int = 63
    stability_model_id: str
    fragility_model_id: str
    scenario_set_id: str
    weights_liquidity: float = 0.3
    weights_vol: float = 0.3
    weights_contagion: float = 0.2
    weights_fundamental: float = 0.2
    soft_target_thresholds: dict = {
        "stability_score": 0.3,
        "high_fragility": 0.7,
        "profile_weakness": 0.7,
        "watch_stability": 0.5,
        "watch_fragility": 0.5,
    }
```

Configs are stored in `engine_configs` with `engine_name="STABILITY"`.

---

## 11. Backtesting & Validation

- Calibrate components and thresholds using historical crises:
  - Check that entities we would intuitively consider fragile pre-crisis show low stability and high fragility.
- Validate that high fragility entities have:
  - higher probability of large drawdowns,
  - worse scenario outcomes.
- Ensure stability scores are not just proxies for raw volatility but capture structural robustness (via profiles and contagion metrics).

---

## 12. Orchestration

The Stability & Soft-Target Engine runs as part of `M_engines_D` DAGs (see 013):

- For each market/region of interest:
  - After ingestion, features, and profiles are updated.
  - Runs `score_entities` and `score_portfolios` for relevant entities/portfolios.
  - Computes fragility and soft-target classes.
  - Persists to `stability_vectors`, `fragility_measures`, `soft_target_classes`.
  - Logs decisions to `engine_decisions` with `engine_name="STABILITY"`.

Intraday variants (optional future):
- Lighter-weight stability scores can be recomputed intra-session for monitoring/alerts without re-running full fragility scenario analysis.