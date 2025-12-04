# 135 – Fragility Alpha Specification

## 1. Purpose and Scope

Fragility Alpha is a cross-asset signal/component that identifies **soft targets** – entities that are structurally weak and fragile to plausible shocks, yet still priced with some degree of optimism or complacency – and proposes risk-controlled **downside or convex positions**.

Entity `O` can be:
- A **company** (equity, credit, options).
- A **sovereign** (rates, sovereign credit, FX).
- A **sector or index**.
- A **currency** (FX crosses).

The goal is to:
- Quantify `SoftTargetScore(O, t)` and `FragilityAlpha(O, t, horizon)`.
- Map them into instrument-level trade suggestions consistent with the Portfolio & Risk Engine.
- Work across scales: from small capital (~1M) to larger AUM, by adapting instruments and sizing.

Fragility Alpha is implemented as a sub-module within the **Assessment Engine**, using inputs from Profiles, Stability, and Black Swan engines.

---

## 2. Conceptual Overview

A soft target `O` at time `t` is characterized by:

1. **High structural weakness** (`WeakProfile`)
   - High leverage, low coverage, poor profitability.
   - Governance/legal/regulatory flags.
   - For sovereigns: debt/GDP, external funding needs, current account, banking system linkages.

2. **High fragility to shocks** (`HighFragility`)
   - Black Swan Engine scenarios show large tail losses under plausible shocks.
   - Stability Engine shows low resilience (liquidity, vol, contagion metrics).

3. **Complacent pricing** (`ComplacentPricing`)
   - Valuation metrics rich relative to history and peers.
   - Spreads and implied vol not reflecting the above weakness.
   - Market behavior not yet in a crisis regime for this entity.

Fragility Alpha seeks entities where all three align and then proposes **bearish or convex exposures** whose payoff is attractive **if**/when instability resolves (e.g. Greece/Eurozone cases, fragile corporates before a credit event, currencies under unsustainable pegs, etc.).

---

## 3. Inputs and Features

### 3.1 Entity universe

Entities `O` include:
- Corporates (listed companies, major private but with traded instruments).
- Sovereigns (countries with tradable debt and/or FX).
- Sectors/indices (e.g. sector ETFs, regional indices).
- Currencies (FX crosses).

The engine relies on:
- `issuer_id` for companies/sovereigns.
- `sector_id` / `index_id` for sectors/indices.
- `currency_pair_id` for FX.

### 3.2 Profile-derived features (`WeakProfile`)

From `ProfileService` / ProfileSnapshot:
- **Corporates:**
  - Leverage ratios (Debt/EBITDA, Debt/Equity).
  - Interest coverage.
  - Profitability & margins trends.
  - Cash vs short-term obligations.
  - Business model risk flags.

- **Sovereigns:**
  - Debt/GDP, debt service to revenues.
  - External debt vs reserves.
  - Current account balance, fiscal deficit.
  - Banking system size vs GDP.

- **Sectors/indices:**
  - Aggregated corporate metrics weighted by market cap/earnings.

- **Currencies:**
  - External vulnerabilities: balance of payments, FX reserves, dependency on capital inflows.

These are collapsed into a **Profile Weakness Score** per entity:

```text
WeakProfile(O, t) ∈ [0, 1]   # 0 = robust, 1 = extremely weak
```

### 3.3 Stability-derived features (`Instability`)

From Stability Engine:
- Liquidity metrics (spreads, depth, volumes, order book proxies).
- Volatility and correlation metrics.
- Contagion signals (co-movement with stress markets), including **learned sovereign/bank contagion effects** from historical crises.

Produce an **Instability Score**:

```text
Instability(O, t) ∈ [0, 1]   # 0 = stable, 1 = extremely unstable
```

### 3.4 Black Swan-derived features (`Fragility`)

From Stability Engine:
- Liquidity metrics (spreads, depth, volumes, order book proxies).
- Volatility and correlation metrics.
- Contagion signals (co-movement with stress markets).

Produce an **Instability Score**:

```text
Instability(O, t) ∈ [0, 1]   # 0 = stable, 1 = extremely unstable
```

### 3.4 Black Swan-derived features (`Fragility`)

From Black Swan Engine:
- Scenario-based losses under relevant shocks:
  - Corporate: sector crashes, funding freezes, rate/FX shocks.
  - Sovereign: rates/FX/debt rollover scenarios, banking crisis.
  - FX: devaluation vs major currencies, rate differentials shocks.

Compute:

```text
Fragility(O, t) = ES_{scenarios}(loss | shocks)  # normalized

HighFragility(O, t) ∈ [0, 1]   # normalized tail-risk-based fragility
```

### 3.5 Shared-space / crisis-pattern features (optional priors)

Optionally, Fragility Alpha may consume **multi-entity embeddings** and crisis-pattern features (see 030 and 045):
- Entity embeddings from the joint space capturing:
  - similarity to past crisis entities (sovereigns, banks, corporates, chokepoints),
  - proximity to known extraction/collapse archetypes.
- Crisis-pattern indicators (Elite Exit Score, CRE stress, bailout/consolidation metrics).

Use these only as **weak priors/features**:
- They must be validated via backtests across multiple crises and out-of-sample periods.
- They should not be the sole drivers of Fragility Alpha; models should remain robust when these features are ablated.

### 3.6 Pricing/complacency features (`ComplacentPricing`)

Use market pricing vs risk:
- Valuation multiples vs history/peers.
- Credit spreads vs fundamental risk.
- Implied vol vs realized vol and fragility.
- For FX: carry, forward premia, volatility skew.

Define:

```text
ComplacentPricing(O, t) ∈ [0, 1]
# 0 = already priced as distressed, 1 = looks very complacent vs underlying risk
```

---

## 4. Core Scores and Signals

### 4.1 SoftTargetScore

Define a combined soft-target measure:

```text
SoftTargetScore(O, t) = g(WeakProfile(O,t), Instability(O,t), HighFragility(O,t), ComplacentPricing(O,t))

# E.g. weighted geometric mean or max of components
# tuned so that score ~1 for entities that resemble past crisis examples.
```

Properties:
- High only when multiple dimensions align.
- We can calibrate thresholds using known episodes (e.g., pre-Greek crisis, fragile EM FX before devaluations, corporates before defaults).

### 4.2 FragilityAlpha

Fragility Alpha should represent **expected downside return or crash probability over a horizon** `H` given current conditions:

```text
FragilityAlpha(O, t, H) ≈ E[downside_return | O is fragile & pricing complacent, horizon = H]
```

Practically, this will be implemented as a supervised (or semi-supervised) model trained on historical episodes:

- Inputs:
  - `SoftTargetScore` components + raw features (profiles, stability, fragility, pricing).
  - Regime embedding.
- Target:
  - Future tail outcomes over horizon `H`:
    - e.g., conditional expected shortfall, probability of drawdown > X%.

Output:
- A scalar signal:

```text
FragilityAlpha(O, t, H) ∈ R  # positive means attractive to be short/long convex
```

We also export a **classification label**:

```text
FragilityClass(O, t) ∈ {NONE, WATCHLIST, SHORT_CANDIDATE, CRISIS}
```

based on thresholds and historical calibration.

---

## 5. Instrument Mapping and Position Templates

Fragility Alpha works at the **entity** level; the Portfolio & Risk Engine operates on **instruments** `I`. We define mapping rules per type of entity.

### 5.1 Corporates

Instruments:
- Equity: common stock, ADRs.
- Options: puts, put spreads, skew trades.
- Credit: CDS (if accessible), corporate bonds.

Templates:
- Small-capital context (~1M):
  - Use **liquid equity and listed options only**.
  - Bias toward **long puts / put spreads** for convexity.
  - Keep gross short stock exposure limited (squeeze risk).

- Larger capital context:
  - Mix of equity shorts, CDS protection, and options.
  - Relative value: short fragile name vs long robust peer or sector ETF.

### 5.2 Sovereigns

Instruments:
- Sovereign bonds (futures or cash).
- CDS or index CDS (if accessible).
- FX (if currency risk is central to fragility).

Templates:
- Fragile sovereign with currency peg / debt rollover risk:
  - Short local currency vs reserve currency.
  - Long FX vol (if implied vol low).
  - Short duration in sovereign bonds or long CDS.

### 5.3 Currencies

Instruments:
- FX spot/forwards.
- FX options.

Templates:
- Soft target currency (e.g., unsustainable current account + pegged rate):
  - Short the currency vs basket of robust currencies.
  - Long downside FX options (digital/vanilla put structures).
  - Position sizing scaled with liquidity and carry cost.

### 5.4 Sectors / Indices

Instruments:
- Sector/region ETFs.
- Index futures.
- Options on indices/ETFs.

Templates:
- Fragile sector (e.g., overlevered banks in a region):
  - Short sector ETF, long market index (relative value),
  - Or buy puts on sector ETF.

---

## 6. Interfaces

Fragility Alpha is exposed as part of the Assessment Engine.

### 6.1 Entity-level API

```python
class FragilityAlphaService:
    """Computes soft-target and fragility alpha scores for entities."""

    def compute_scores(
        self,
        entity_ids: list[str],
        as_of_date: date,
        horizon_days: int,
    ) -> dict[str, "FragilityAlphaResult"]:
        """Compute fragility scores for a list of entities.

        Args:
            entity_ids: Issuer/sovereign/sector/currency entity IDs.
            as_of_date: Date of evaluation.
            horizon_days: Horizon over which fragility is assessed.

        Returns:
            Mapping from entity_id to FragilityAlphaResult, containing:
                - soft_target_score
                - fragility_alpha
                - fragility_class
                - feature diagnostics (optional)
        """
```

`FragilityAlphaResult` structure:

```python
@dataclass
class FragilityAlphaResult:
    entity_id: str
    as_of_date: date
    horizon_days: int
    soft_target_score: float  # 0..1
    fragility_alpha: float
    fragility_class: str  # NONE/WATCHLIST/SHORT_CANDIDATE/CRISIS
    components: dict[str, float]  # WeakProfile, Instability, HighFragility, ComplacentPricing, etc.
```

### 6.2 Instrument suggestion API

A second layer maps entity-level fragility signals to instrument candidates:

```python
class FragilityPositionSuggester:
    """Suggests instrument-level trades based on fragility alpha signals."""

    def suggest_positions(
        self,
        fragility_results: dict[str, FragilityAlphaResult],
        as_of_date: date,
        capital_scale: float,
    ) -> list["PositionTemplate"]:
        """Suggest short/convex positions for fragile entities.

        Args:
            fragility_results: Entity-level fragility scores.
            as_of_date: Date of evaluation.
            capital_scale: Approximate total capital the strategy is allowed to deploy, 
                used to scale notionals and choose instrument complexity.

        Returns:
            A list of PositionTemplate objects describing:
                - instrument_id
                - direction (long/short)
                - position_type (stock, future, option, etc.)
                - notional_hint / max_allocation
                - rationale metadata
        """
```

`PositionTemplate` is a lightweight structure that Portfolio & Risk Engine can refine:

```python
@dataclass
class PositionTemplate:
    entity_id: str
    instrument_id: str
    as_of_date: date
    direction: str  # "LONG" or "SHORT"
    kind: str  # "EQUITY", "FUTURE", "OPTION", "CDS", "FX"
    notional_hint: float  # fraction of capital or raw notional
    horizon_days: int
    rationale: dict[str, Any]  # links back to fragility components
```

The Portfolio & Risk Engine then:
- Takes these templates along with other alphas.
- Applies constraints, diversification, and optimization.
- Decides final sizes `{w_I}`.

---

## 7. Training and Backtesting

### 7.1 Labeling historical episodes

To train and calibrate Fragility Alpha, we:

1. Identify known crisis/near-crisis episodes:
   - Sovereign: Greece/Eurozone crisis, EM debt crises, currency devaluations.
   - Corporate: major defaults or distress events.
   - Sectoral: banking crises, commodity busts.

2. For each entity and date `t` leading up to an event:
   - Build features (`WeakProfile`, `Instability`, `HighFragility`, `ComplacentPricing`).
   - Label outcomes over horizons (e.g., 1/3/6 months):
     - drawdown magnitude,
     - ES, indicator of stress event.

3. Train models to predict:
   - Tail outcomes or event probabilities from current features.

### 7.2 Backtesting

- Backtest strategies that:
  - Screen entities by `SoftTargetScore` and `FragilityClass`.
  - Take positions using the `FragilityPositionSuggester` templates.
  - Plug suggestions into full Portfolio & Risk Engine.

- Evaluate:
  - P&L and risk over time.
  - Hit rate of windfall events vs bleed from premiums/shorts.
  - Behavior by regime and by crisis type.

- Robustness:
  - Simulate using Synthetic Scenario Engine, especially stress worlds where many entities are fragile.

---

## 8. Integration into Prometheus v2

- **Assessment Engine (130 spec):**
  - Fragility Alpha is a sub-component generating one family of signals, to be combined with other alpha sources.

- **Stability & Soft-Target Engine (110):**
  - Provides inputs and, in return, can use FragilityClass to:
    - refine its alerts,
    - highlight entities where fragility has become tradeable.

- **Universe (140):**
  - Tag entities/instruments as `SHORT_CANDIDATE` based on FragilityClass.
  - Allow strategies that explicitly include/exclude such candidates.

- **Portfolio & Risk (150):**
  - Enforce constraints on total exposure to fragility shorts and options.
  - Use Black Swan Engine to ensure portfolio-level tail risk remains acceptable.

By treating fragility as a first-class alpha source across companies, countries, sectors, and currencies, Prometheus v2 can systematically position on the right side of structural breaks and stress events, while keeping exposure controlled and backtestable.