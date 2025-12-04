# 170 – Synthetic Scenario Engine Specification

## 1. Purpose

The Synthetic Scenario Engine generates **numeric stress scenarios** for use by:
- Portfolio & Risk Engine (150) – scenario P&L / drawdown / constraint stress tests.
- Stability & Soft-Target Engine (110) and Fragility Alpha (135) – checking how fragile entities behave under shocks.
- Meta-Orchestrator (160) – evaluating robustness of configs beyond realized history.

It produces **panels of returns / shocks** over a horizon `H` for a set of instruments, factors, and macro variables, conditioned on regimes and stability/fragility states.

---

## 2. Scope

- Generates scenarios at **daily** and **multi-day** horizons (e.g. 1–60 days) for now.
- Works on **end-of-day** data first; intraday scenarios can be added later.
- Covers:
  - Instruments (equities, ETFs, FX, futures, etc.).
  - Factors (from factor model in 150).
  - Macro variables (a subset of key series; see 020, 100).
- Does **not** place trades or optimize portfolios; it only provides shocks.

---

## 3. Concepts and Terminology

### 3.1 ScenarioSet

A **ScenarioSet** is a collection of one or more **ScenarioPaths** sharing:
- a common definition (generator, parameters, base sample, regime filters),
- a common horizon `H`,
- a common evaluation purpose.

Examples:
- `US_EQ_BASELINE_BOOTSTRAP_30D_2020ON` – 1,000 bootstrap paths, 30 days, based on 2020+ daily returns.
- `EU_EQ_CRISIS_OVERLAYS_10D` – 200 paths with crisis-style shocks on EU_EQ.
- `GLOBAL_FRAGILITY_ADVERSARIAL_20D_2025Q1` – adversarial paths targeted by Fragility Alpha.

### 3.2 ScenarioPath

A **ScenarioPath** is a time series of shocks for:
- a set of instruments, and/or
- factors/macros.

We represent a path `p` in ScenarioSet `S` as:

- `scenario_set_id` – FK to ScenarioSet.
- `scenario_id` – integer within the set (e.g. 0..N-1).
- `horizon_index` – integer 0..H (0 is baseline/start, 1..H are steps).
- `instrument_id` or `factor_id` or `macro_id`.
- `return` – log or simple return vs baseline.
- `shock_metadata` – JSON for additional fields (e.g. vol, spread, jump flags).

---

## 4. Scenario Types

The engine supports multiple scenario families.

### 4.1 Historical windows (Type A)

- Extract contiguous daily windows from history, optionally conditioned on:
  - regime labels (`regimes` table),
  - stability/fragility buckets (`stability_vectors`, `fragility_measures`),
  - markets/regions.
- Use as **"real but limited"** stress tests (e.g. replay 2008, 2020 COVID crash).

### 4.2 Block bootstrap (Type B)

- Block-bootstrap daily returns to generate many pseudo-historical paths:
  - choose block length `B` (e.g. 5–20 days),
  - sample blocks with replacement from history (optionally within regime buckets),
  - stitch blocks to form a path of length `H`.
- Optionally constrain:
  - marginal distribution per instrument,
  - cross-sectional correlation structure (approximate preservation).

### 4.3 Factor/residual bootstraps (Type C)

- Use the factor model from Portfolio & Risk Engine (150):
  - Decompose instrument returns into factor component + idiosyncratic residual.
- Generate scenarios by:
  - sampling factor returns from historical or parametric distributions,
  - sampling residuals independently or with light correlation,
  - reassembling instrument returns.

Options:
- **Regime-conditional sampling** – sample only from windows where `RegimeState` matches target.
- **Shock scaling** – multiply factor shocks by `k > 1` for stress.
- **Correlation perturbations** – alter factor covariance for stress (e.g. correlation breakdown).

### 4.4 Shock overlays (Type D)

- Take a baseline path (historical or bootstrap) and overlay discrete shocks:
  - one-day market gap (e.g. -15% index move),
  - spread-widening shocks on credit factors,
  - volatility spikes.
- Shocks are parameterized and tagged (e.g. `CRASH_GAP`, `VOL_SPIKE`, `CREDIT_FREEZE`).

### 4.5 Fragility-driven adversarial scenarios (Type E)

Using Fragility Alpha (135) and Stability/Soft-Target (110):

- Identify **entities/instruments with high SoftTargetScore**.
- Construct scenarios that:
  - apply large but plausible shocks to the factors and instruments that hurt these entities,
  - preserve broad market constraints (no impossible arbitrage, plausible macro backdrop),
  - align with offensive/adversary perspectives (210) but used for **defensive testing only**.

Examples:
- "Sovereign funding squeeze" targeting a fragile sovereign and related banks.
- "Sector crash" where a fragile sector is hit disproportionately vs broad market.

### 4.6 Regulatory & named scenarios (Type F)

- Scenarios taken from regulatory frameworks (e.g. CCAR-like, EBA-like) or self-defined named cases.
- Stored as **fixed** ScenarioSets with hand-tuned shocks.

---

## 5. Storage Design

New tables extending 020:

### 5.1 `scenario_sets`

- `scenario_set_id` (PK, uuid)
- `name` (text)
- `description` (text)
- `category` (text; enum-like: `HISTORICAL`, `BOOTSTRAP`, `FACTOR_BOOTSTRAP`, `SHOCK_OVERLAY`, `FRAGILITY_ADVERSARIAL`, `REGULATORY`, `CUSTOM`)
- `horizon_days` (int)
- `num_paths` (int)
- `base_universe_filter` (jsonb) – criteria for included instruments (markets, asset classes, liquidity filters).
- `base_date_range` (daterange) – historical window used for calibration.
- `regime_filter` (text[]) – allowed regime labels, if any.
- `generator_spec` (jsonb) – parameters for generator (block size, factor model id, shock types, etc.).
- `created_at` (timestamptz)
- `created_by` (text) – user or "system".
- `tags` (text[])
- `metadata` (jsonb)

### 5.2 `scenario_paths`

- `scenario_set_id` (uuid, FK → scenario_sets.scenario_set_id)
- `scenario_id` (int) – index within set
- `horizon_index` (int) – 0..H
- `instrument_id` (text, FK → instruments.instrument_id, nullable if factor/macro path)
- `factor_id` (text, nullable)
- `macro_id` (text, nullable)
- `return` (numeric) – shock as return vs baseline
- `price` (numeric, nullable) – optional price level
- `shock_metadata` (jsonb)

PK: (`scenario_set_id`, `scenario_id`, `horizon_index`, `instrument_id`, `factor_id`, `macro_id`).

Indexes:
- (`scenario_set_id`, `scenario_id`)
- (`scenario_set_id`, `instrument_id`, `horizon_index`)

We can store instrument-level and factor-level shocks in the same table; only one of `instrument_id`/`factor_id`/`macro_id` is non-null per row.

### 5.3 Linking to Risk & Meta

No new tables are strictly required beyond `scenario_sets`/`scenario_paths`:
- Portfolio & Risk Engine (150) will read from these tables when computing scenario risk.
- Meta-Orchestrator (160) can use scenario-based risk metrics stored in `portfolio_risk_reports` and annotate them with `scenario_set_id` in its own views.

---

## 6. APIs

Module: `prometheus/synthetic/api.py`

### 6.1 Scenario request & generation

```python
from dataclasses import dataclass
from datetime import date
from typing import List, Optional


@dataclass
class ScenarioRequest:
    name: str
    description: str
    category: str  # e.g. "BOOTSTRAP", "FRAGILITY_ADVERSARIAL"
    horizon_days: int
    num_paths: int
    markets: List[str]  # market_ids like "US_EQ", "EU_EQ"
    base_date_start: Optional[date] = None
    base_date_end: Optional[date] = None
    regime_filter: Optional[List[str]] = None
    universe_filter: Optional[dict] = None
    generator_spec: Optional[dict] = None


@dataclass
class ScenarioSetRef:
    scenario_set_id: str
    name: str
    category: str
```

```python
class SyntheticScenarioEngine:
    """Generate and manage synthetic scenario sets for risk and robustness testing."""

    def generate_scenario_set(self, request: ScenarioRequest) -> ScenarioSetRef:
        """Generate a new ScenarioSet and persist it to the DB."""

    def list_scenario_sets(
        self,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[ScenarioSetRef]:
        """List available ScenarioSets, optionally filtered by category/tags."""

    def get_scenario_set_metadata(self, scenario_set_id: str) -> dict:
        """Return metadata and generator_spec for a ScenarioSet."""
```

### 6.2 Integration with Portfolio & Risk

Portfolio & Risk Engine (150) will expose APIs such as:

```python
class PortfolioRiskEngine:
    def scenario_risk_report(
        self,
        portfolio_id: str,
        scenario_set_id: str,
    ) -> "ScenarioRiskReport":
        ...
```

The Synthetic Scenario Engine does **not** compute portfolio P&L; it only supplies shocks. Risk computes:
- scenario P&L distributions,
- drawdowns,
- constraint violations under scenarios.

---

## 7. Generator Implementations (Sketch)

### 7.1 Historical window generator

- Inputs:
  - `base_date_start`, `base_date_end`.
  - `regime_filter` (optional).
- Algorithm:
  - Fetch historical returns panel for selected instruments.
  - Identify all contiguous windows of length `H` within the date range where `RegimeState` is in `regime_filter` (if provided).
  - If `num_paths` ≤ available windows: sample without replacement.
  - Otherwise: sample with replacement.

### 7.2 Block bootstrap generator

- Inputs:
  - block length `B`, horizon `H`, num_paths `N`.
- Algorithm:
  - For each path, sample blocks of length `B` from historical returns (per instrument) until reaching `H` days.
  - Optionally enforce regime consistency (sample blocks from the same or similar regimes).
  - Stitch blocks; optionally smooth transitions at block boundaries.

### 7.3 Factor bootstrap generator

- Inputs:
  - factor model id (link to model registry),
  - sample window and regime filters,
  - shock scaling.
- Algorithm:
  - For each path:
    - Sample factor returns over horizon from historical or parametric distributions.
    - Sample idiosyncratic residuals.
    - Reconstruct instrument returns.

### 7.4 Fragility-driven adversarial generator

- Inputs:
  - snapshot time `as_of_date`,
  - target markets,
  - target buckets: e.g. top-k by SoftTargetScore.
- Algorithm (high level):
  - Query Stability & Soft-Target Engine (110) and Fragility Alpha (135) for most fragile entities.
  - Identify factor/macro exposures that hurt those entities.
  - Construct shocks on those drivers, constrained by:
    - plausible macro outcomes,
    - bounds from threat model docs (defensive spec 200, offensive perspectives 210).
  - Translate driver shocks into instrument returns via factor model.

Result:
- ScenarioSets tagged `FRAGILITY_ADVERSARIAL`, clearly marked as **defensive tests**.

---

## 8. Orchestration

Synthetic scenarios are generated on scheduled DAGs and on-demand:

- `synthetic_monthly_M` per market family (US_EQ, EU_EQ, etc.):
  - Refresh baseline bootstrap ScenarioSets.
  - Refresh regulatory / named ScenarioSets if definitions changed.

- `synthetic_fragility_daily_T`:
  - After Stability/Fragility engines run, generate or update small adversarial ScenarioSets focused on current soft targets.

- On-demand via API:
  - For ad-hoc what-if analysis from UI or Kronos Chat.

DAGs run after end-of-day data pipelines.

---

## 9. Integration with Meta-Orchestrator and UI

### 9.1 Meta-Orchestrator (160)

- Meta-Orchestrator uses scenario-based risk metrics to judge **robustness** of configs, not just their realized P&L.
- For each engine config, Portfolio & Risk can compute scenario risk for relevant ScenarioSets; results feed into:
  - config comparison views,
  - experiment evaluation.

### 9.2 Monitoring & UI (200)

The Monitoring/UI spec (200) can expose:
- Scenario library browser:
  - list ScenarioSets, categories, tags, metadata.
- Scenario results views:
  - portfolio-level scenario P&L distributions,
  - per-instrument/extreme-loss tables,
  - comparison across ScenarioSets (e.g. baseline vs adversarial).
- Hooks from Kronos Chat:
  - "Generate 50-day adversarial fragility scenarios for US_EQ and run them on Portfolio X".

---

## 10. Safety and Governance

- Synthetic scenarios are used **only** for risk and robustness analysis, not for designing manipulative strategies.
- Adversarial / fragility-driven scenarios are framed as "what could an attacker do?" but their sole role is:
  - to evaluate capital resilience,
  - to inform conservative risk limits and monitoring.
- All ScenarioSets are:
  - versioned and tagged,
  - reproducible via stored `generator_spec`,
  - documented sufficiently for audit (especially regulatory/named scenarios).

## 11. Future mathematical enrichments for generators

To avoid locking into a single simplistic scenario family, the engine will
incrementally incorporate additional mathematical tools:

- **v2 – Tail-aware distributions and EVT hooks**
  - Allow generator specs to request Student-t or similar heavy-tailed
    parametric fits for factor or residual shocks, instead of pure
    Gaussian assumptions.
  - Provide simple hooks to plug in extreme-value metrics (e.g. Hill
    tail indices, GEV fits) computed elsewhere as sanity checks on
    scenario severity.
- **v3 – Dependence and copula-based structures**
  - Support optional copula-based sampling for multi-asset scenarios so
    that tail co-movement and diversification breakdown can be expressed
    more realistically than with simple correlation matrices.
- **v3/v4 – Temporal and spectral structure**
  - Expose options in `generator_spec` to condition block/Factor
    bootstraps on basic spectral or wavelet characteristics (e.g.
    trend-dominated vs choppy vs oscillatory regimes) when selecting
    historical windows.
- **v4+ – Scenario-space diagnostics**
  - Provide simple coverage diagnostics to Meta/Risk (e.g. how scenario
    sets cover combinations of tail index, dependence structure, and
    spectral type) without changing the core API of the scenario engine.

- Synthetic scenarios are used **only** for risk and robustness analysis, not for designing manipulative strategies.
- Adversarial / fragility-driven scenarios are framed as "what could an attacker do?" but their sole role is:
  - to evaluate capital resilience,
  - to inform conservative risk limits and monitoring.
- All ScenarioSets are:
  - versioned and tagged,
  - reproducible via stored `generator_spec`,
  - documented sufficiently for audit (especially regulatory/named scenarios).

This spec, combined with the data model (020), risk engine (150), threat models (200/210), and meta-orchestrator (160), defines how synthetic scenarios become a first-class tool for making Prometheus robust to both historical and unforeseen stresses.