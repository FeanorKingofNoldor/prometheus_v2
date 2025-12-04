# 140 – Universe Selection Engine Specification

## 1. Purpose

The Universe Selection Engine builds **candidate trading universes** per strategy and market, based on:
- Liquidity and data availability.
- Quality and robustness (profiles, risk flags).
- Stability & Soft-Target signals.
- Assessment/alpha scores.

It outputs per-strategy lists of instruments with scores/tiers, which the Portfolio & Risk Engine then uses as the feasible set for optimization.

---

## 2. Scope

- Runs daily (POST_CLOSE) after Assessment and Stability engines have updated their outputs.
- Operates per (`strategy_id`, `market_id`, `as_of_date`).
- Produces:
  - Universe membership `U(strategy, market, as_of_date)`.
  - Optional tiers/buckets (e.g., core, satellite, excluded).

The Universe Engine does not decide position sizes; it defines **where** the strategy is allowed to trade.

---

## 3. Inputs

For each `(strategy_id, market_id, as_of_date)`:

1. **Global constraints**
   - Maximum number of names in universe.
   - Hard exclusions (e.g., blacklists, restricted lists).

2. **Instrument-level data**

From data model and other engines:
- `instruments` and `issuers` tables (for metadata: sector, country, asset_class).
- Liquidity metrics:
  - volume, ADV (average daily volume), turnover, realized spreads.
- Profile data (035):
  - `ProfileSnapshot` and risk flags (quality, leverage, governance, etc.).
- Stability & Soft-Target (110):
  - `StabilityVector` and `SoftTargetClass` (issuer/sector/market).
- Assessment Engine (130):
  - `InstrumentScore` per instrument (expected_return, score, alpha_components).

3. **Strategy-specific preferences**
- Minimum liquidity thresholds.
- Sector/region focuses or exclusions.
- Tolerance for fragility/soft targets (e.g., long-only strategies may avoid them; long/short strategies may include them on the short side only).

---

## 4. Outputs

### 4.1 UniverseEntry

Conceptual structure:

```python
from dataclasses import dataclass
from datetime import date
from typing import Dict

@dataclass
class UniverseEntry:
    strategy_id: str
    market_id: str
    instrument_id: str
    as_of_date: date
    tier: str  # e.g. CORE, SATELLITE, EXCLUDED
    universe_score: float  # overall suitability score
    reasons: Dict[str, float]  # contributions (liquidity, quality, alpha, fragility constraints)
```

### 4.2 Universe snapshot

For a given `(strategy_id, market_id, as_of_date)`, the Universe Engine returns:

```python
Dict[instrument_id, UniverseEntry]
```

The **effective universe** for optimization is the subset with `tier != EXCLUDED`.

---

## 5. Universe Construction Logic

### 5.1 Hard filters

Apply non-negotiable filters:
- Instrument eligibility:
  - asset class matches strategy (e.g., equities only).
  - instrument is `ACTIVE`.
- Liquidity:
  - ADV above threshold.
  - price above minimum (avoid penny stocks, etc.).
- Data coverage:
  - requires adequate history and profile coverage.

### 5.2 Quality and robustness filters

Based on profiles and risk flags:
- Exclude names with extreme governance/legal red flags.
- Exclude names below minimum quality thresholds for certain strategies.

### 5.3 Stability & Soft-Target handling

- For long-only or conservative strategies:
  - Exclude or down-weight `SOFT_TARGET` entities on the long side.
- For long/short strategies:
  - May **include** `SOFT_TARGET` entities in the universe but:
    - flagged for short/fragility trades only,
    - possibly tiered differently.

### 5.4 Alpha/Assessment integration

From `instrument_scores`:
- Rank candidates by Assessment `score` or `expected_return`.
- Optionally use decile/quantile buckets.

Universe selection may:
- Take top N names by score within each sector/region bucket.
- Ensure diversification by capping number of names per sector/country.

### 5.5 Tiering

Assign `tier` based on suitability:
- `CORE` – meets all criteria, high alphas, good liquidity/quality.
- `SATELLITE` – acceptable but lower alpha or higher risk; used to diversify or for tactical trades.
- `EXCLUDED` – fails hard filters or explicitly excluded.

`universe_score` can be a composite of:
- normalized liquidity score,
- quality/robustness score,
- Assessment score,
- penalty for fragility (if applied).

---

## 6. APIs

Module: `prometheus/universe/api.py`

```python
from datetime import date
from typing import List, Dict

class UniverseEngine:
    """Builds and scores trading universes per strategy and market."""

    def build_universe(
        self,
        strategy_id: str,
        market_id: str,
        as_of_date: date,
    ) -> Dict[str, UniverseEntry]:
        """Build and score the universe for a strategy on a given date.

        Args:
            strategy_id: Strategy identifier.
            market_id: Market identifier.
            as_of_date: Date of the universe snapshot.

        Returns:
            Mapping from instrument_id to UniverseEntry.
        """

    def get_effective_universe(
        self,
        strategy_id: str,
        market_id: str,
        as_of_date: date,
    ) -> List[str]:
        """Return the list of instruments in the effective universe (tier != EXCLUDED)."""
```

---

## 7. Storage & Integration

### 7.1 Storage table

**Table:** `universes`

- `strategy_id` (text)
- `market_id` (text)
- `instrument_id` (text)
- `as_of_date` (date)
- `tier` (text: `CORE`, `SATELLITE`, `EXCLUDED`)
- `universe_score` (numeric)
- `reasons` (jsonb)
- `model_id` (text) – universe selection model/version
- `metadata` (jsonb)

PK: (`strategy_id`, `market_id`, `instrument_id`, `as_of_date`, `model_id`).

### 7.2 Integration

- **Assessment Engine (130):**
  - Universe definitions may be used to restrict which instruments are scored.

- **Portfolio & Risk (150):**
  - Uses `get_effective_universe` to constrain optimization.

- **Meta-Orchestrator (160):**
  - Analyzes how universe changes affect performance and risk over time.

- **Monitoring/UI (200):**
  - Shows universe composition, entry/exit changes, and reasons.

---

## 8. Configuration

Module: `prometheus/universe/config.py`

```python
from pydantic import BaseModel
from typing import List, Dict

class UniverseConfig(BaseModel):
    strategy_id: str
    markets: List[str]
    max_universe_size: int
    min_liquidity_adv: float
    min_price: float
    sector_max_names: int
    hard_exclusion_list: List[str] = []  # instrument_ids
    issuer_exclusion_list: List[str] = []  # issuer_ids
    allow_soft_targets_long: bool = False
    allow_soft_targets_short: bool = True
    universe_model_id: str  # model or rule-set governing score computation
```

Configs are stored in `engine_configs` with `engine_name="UNIVERSE"`.

---

## 9. Backtesting & Validation

- Evaluate universes historically:
  - Stability of membership (how often names churn in/out).
  - Liquidity and slippage of names in the universe.
  - Quality and fragility mix (e.g., fraction of names in high-risk buckets).
- Assess impact on strategy performance:
  - Compare portfolio performance under different universe configs (e.g., stricter quality/fragility filters vs looser ones).

---

## 10. Orchestration

- Universe Engine runs in `M_engines_D` DAGs after Assessment and Stability engines:
  - For each `strategy_id` × `market_id`:
    - Build universe snapshot using the latest scores and stability/fragility info.
    - Persist to `universes`.
    - Log decision to `engine_decisions` with `engine_name="UNIVERSE"`.

- Intraday refreshes (optional):
  - Can be triggered when severe stability/fragility changes occur (e.g., many names become soft targets) to tighten universes mid-cycle.