# 150 – Portfolio & Risk Engine Specification

## 1. Purpose

The Portfolio & Risk Engine transforms assessment signals, universes, and risk models into **target portfolios**, and evaluates/monitors portfolio risk.

It provides:
- Optimal target weights `{w_I}` per strategy/portfolio under constraints.
- Risk metrics (volatility, drawdown estimates, scenario P&L, factor exposures).
- Checks against hard risk limits.

It does **not** send orders directly; execution is handled by `prometheus/execution` based on target vs current positions.

---

## 2. Scope

- Runs daily (POST_CLOSE) after Assessment and Universe engines.
- Operates per `portfolio_id` (mapped to one or more strategies/markets).
- Supports multiple portfolio types:
  - long-only, long/short, market-neutral, etc.

Later phases may add intraday re-optimization for large moves or events.

---

## 3. Inputs

For each `portfolio_id` at `as_of_date`:

1. **Portfolio definition**
   - From `portfolios` table: base currency, mandate metadata.
   - Mapping to `strategy_id`s and `market_id`s that feed this portfolio.

2. **Universe and assessment**
   - From Universe Engine (140): effective universe `U(strategy, market, as_of_date)`.
   - From Assessment Engine (130): `InstrumentScore` for instruments in universe(s).

3. **Risk model**
   - Historical covariance/factor model, from:
     - `correlation_panels`,
     - factor exposures (`instrument_factors_daily`),
     - factor returns (`factors_daily`).
   - Liquidity/impact model:
     - ADV, spreads, depth.

4. **Stability & fragility**
   - `StabilityVector` and `FragilityMeasures` for entities/portfolios.
   - `SoftTargetClass` for issuers/sectors.

5. **Current positions**
   - Positions as of `as_of_date`, from runtime DB or execution layer snapshot.

6. **Constraints & limits**
   - From config and/or DB:
     - max gross/net exposure,
     - leverage limits,
     - per-name/sector/country max weights,
     - factor exposure bounds,
     - max turnover and trading cost budgets,
     - limits on exposure to soft targets / fragile entities.

---

## 4. Outputs

### 4.1 TargetPortfolio

Conceptual structure:

```python
from dataclasses import dataclass
from datetime import date
from typing import Dict

@dataclass
class TargetPortfolio:
    portfolio_id: str
    as_of_date: date
    weights: Dict[str, float]  # instrument_id -> target weight in NAV terms
    expected_return: float
    expected_volatility: float
    risk_metrics: Dict[str, float]  # VaR/ES, drawdown estimates, etc.
    factor_exposures: Dict[str, float]
    constraints_status: Dict[str, bool]  # which constraints are binding/active
    metadata: Dict[str, float]
```

### 4.2 RiskReport

```python
@dataclass
class RiskReport:
    portfolio_id: str
    as_of_date: date
    exposures: Dict[str, float]  # by factor, sector, country, currency, fragility bucket
    risk_metrics: Dict[str, float]
    scenario_pnl: Dict[str, float]  # scenario_id -> P&L
    stability_vector: StabilityVector  # from Stability Engine
```

---

## 5. Optimization Problem

The core optimization problem takes the form:

```text
maximize    w^T mu  -  lambda * Risk(w)  -  Cost(w, w_current)
subject to  Constraints(w)
```

Where:
- `w`: vector of target weights for instruments in the effective universe.
- `mu`: vector of expected returns (from Assessment Engine), possibly adjusted for confidences.
- `Risk(w)`: risk measure from covariance/factor model (variance or more complex risk).
- `Cost(w, w_current)`: trading costs and turnover penalties.

### 5.1 Risk models

1. **Covariance-based model**
   - Estimate covariance matrix `Σ` from factor model + idiosyncratic risk.
   - `Risk(w) = w^T Σ w` (variance) or `sqrt(w^T Σ w)` (vol).

2. **Factor model**
   - Factor exposures `B` per instrument.
   - Factor covariance `F` and specific risk `D`.
   - `Σ = B F B^T + D`.

3. **Scenario risk**
   - Use fragility scenarios `S_k` to compute scenario P&L for a candidate `w`.
   - May include scenario-based constraints (e.g., ES under scenarios must be below threshold).

### 5.2 Constraints

Typical constraints include:

- **Budget**: sum of weights = 1 (or 0 for market-neutral).
- **Bounds**:
  - per-instrument min/max weights (e.g., 0 ≤ w_i ≤ w_max for long-only).
  - sector/country/Fx exposure bounds.
- **Leverage**:
  - gross exposure ≤ L_max.
- **Factor exposures**:
  - |factor_exposure_f| ≤ limit_f.
- **Turnover costs**:
  - implicit via cost function, or explicit constraint on total turnover.
- **Fragility/soft-target limits**:
  - sum of |w_i| over soft targets ≤ fragility_budget.

### 5.3 Solvers

Depending on the objective/constraints:
- **QP (Quadratic Programming)** where `Risk(w)` is quadratic and constraints are linear.
- **LP/SOCP** for more complex risk or where linear risk approximations are used.

Implementation detail is flexible; spec requires:
- Deterministic behavior given inputs and config.
- Numeric stability and logging of failures.

---

## 6. APIs

Module: `prometheus/portfolio/api.py`

```python
from datetime import date
from typing import Dict

class PortfolioEngine:
    """Portfolio construction and risk evaluation engine."""

    def optimize(
        self,
        portfolio_id: str,
        as_of_date: date,
    ) -> TargetPortfolio:
        """Compute target portfolio weights under current signals and constraints.

        Args:
            portfolio_id: Portfolio identifier.
            as_of_date: Date of optimization.
        """

    def risk_report(
        self,
        portfolio_id: str,
        as_of_date: date,
        weights: Dict[str, float] | None = None,
    ) -> RiskReport:
        """Generate a risk report for a portfolio.

        Args:
            portfolio_id: Portfolio identifier.
            as_of_date: Date of evaluation.
            weights: Optional custom weight vector. If None, use current or target
                portfolio as appropriate.
        """
```

---

## 7. Storage & Integration

### 7.1 Storage tables

**Table:** `target_portfolios`

- `portfolio_id` (text)
- `as_of_date` (date)
- `instrument_id` (text)
- `target_weight` (numeric)
- `model_id` (text) – optimization/risk model version
- `metadata` (jsonb)

PK: (`portfolio_id`, `as_of_date`, `instrument_id`, `model_id`).

**Table:** `portfolio_risk_reports`

- `portfolio_id` (text)
- `as_of_date` (date)
- `risk_metrics` (jsonb)
- `exposures` (jsonb)
- `scenario_pnl` (jsonb)
- `model_id` (text)
- `metadata` (jsonb)

PK: (`portfolio_id`, `as_of_date`, `model_id`).

### 7.2 Integration

- **Execution layer** (`prometheus/execution`):
  - Compares current positions vs `target_portfolios` to generate orders.

- **Monitoring/UI (200):**
  - Uses `RiskReport` for Portfolio & Risk panel.

- **Meta-Orchestrator (160):**
  - Analyzes how different optimization/risk configs perform over time.

---

## 8. Configuration

Module: `prometheus/portfolio/config.py`

```python
from pydantic import BaseModel
from typing import List, Dict

class PortfolioConfig(BaseModel):
    portfolio_id: str
    strategies: List[str]  # strategy_ids feeding this portfolio
    markets: List[str]
    base_currency: str
    risk_model_id: str  # reference into models table
    optimizer_type: str  # e.g., "QP", "SOCP"
    risk_aversion_lambda: float
    leverage_limit: float
    gross_exposure_limit: float
    per_instrument_max_weight: float
    sector_limits: Dict[str, float]
    country_limits: Dict[str, float]
    factor_limits: Dict[str, float]
    fragility_exposure_limit: float
    turnover_limit: float
    cost_model_id: str
```

Configs are stored in `engine_configs` with `engine_name="PORTFOLIO"`.

---

## 9. Backtesting & Validation

- Run historical portfolio simulations using Assessment + Universe + Portfolio engines.
- Check:
  - realized vs predicted risk (vol, drawdown).
  - adherence to constraints (factor exposures, sector limits, soft-target exposure).
  - robustness under scenario shocks (from Stability & Soft-Target scenarios).
- Tune `risk_aversion_lambda`, exposure limits, and fragility budgets accordingly.

---

## 10. Orchestration

- Portfolio & Risk Engine runs in `M_engines_D` DAGs after Universe selection:
  - For each `portfolio_id`:
    - Build target portfolio via `optimize`.
    - Persist to `target_portfolios`.
    - Generate `portfolio_risk_reports`.
    - Log decision to `engine_decisions` with `engine_name="PORTFOLIO"`.

- Intraday re-optimization (optional future):
  - Triggered by large moves or stability/fragility changes, with throttling to respect turnover/cost limits.

This spec is the reference for implementing `prometheus/portfolio` and associated risk modeling in Prometheus v2.