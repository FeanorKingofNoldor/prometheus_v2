# Prometheus v2 Threat Model – Defensive Perspective

## 1. Purpose
This document describes Prometheus v2 from a **defensive** point of view. It identifies:
- What we are trying to protect.
- Classes of adversaries and threats (market and technical).
- How each engine (regime, stability, black swan, assessment, universe, portfolio, meta) should be designed to reduce attack surface and failure modes.

This is a design input for all specs (020 data model, 030 encoders, 100–150 engines, 160 meta, 170 synthetic).

---

## 2. What we are protecting

### 2.1 Assets
- **Capital**: absolute loss, drawdown, tail risk.
- **Liquidity**: ability to adjust positions without catastrophic impact.
- **Information**: our signals, features, models, configs.
- **Operational continuity**: ability to trade and risk-manage during stress.
- **Reputation / compliance**: avoid behaviors that look like manipulation or abuse.

### 2.2 Core invariants
Prometheus v2 should maintain, as much as possible:
- No forced liquidations due to naive leverage or margin design.
- No single point of failure in model or config that can wipe out capital.
- All trading decisions replayable and explainable (for us and for regulators).

---

## 3. Adversary classes (high-level)

We consider adversaries in a **threat-modeling** sense (not necessarily malicious; some are just more powerful participants):

1. **Natural market stress**
   - Crises, liquidity shocks, gaps, correlated drawdowns.
   - No intent, but can wipe out fragile portfolios.

2. **Sophisticated institutional players**
   - Macro funds, HFTs, large banks.
   - May unintentionally be on the other side of our trades, or intentionally trade around visible patterns of others.

3. **Execution predators**
   - Counterparties that detect naive execution patterns and front‑run or fade them.
   - Venues/brokers that internalize flow in ways unfavorable to us.

4. **Data / model integrity threats**
   - Bad data, regime shifts, distribution shifts.
   - Misuse of LLMs to produce plausible but wrong rationales.

5. **Internal mistakes and misconfigurations** (the most common “attacker”) 
   - Wrong config, broken backtest, load of wrong model, etc.

We design engines and processes to be robust to these.

---

## 4. Defensive requirements by layer

### 4.1 Data & Representation Layer

**Threats:**
- Data errors feeding all models.
- Silent changes in vendor data formats.
- Embedding/model version drift.

**Defensive design:**
- Strong schema validation in `020_data_model`.
- Versioned data ingestion with checksums and anomaly detection.
- Model registry for encoders with explicit `model_id`, training metadata, and compat rules.
- Ability to reconstruct any feature/embedding as of date T from raw data + model version.

### 4.2 Regime Engine

**Threats:**
- Misclassifying regime near transitions → wrong configs/universe.
- Overfitting regime definitions to history.

**Defensive design:**
- Use both numeric and text embeddings to detect regime (less fragile than pure returns).
- Provide **confidence scores**; low‑confidence regimes should trigger conservative defaults.
- Backtest robustness: regime labels should be stable under small perturbations and sub‑sampled history.
- Make all downstream engines *gracefully degrade* if regime is uncertain.

### 4.3 Stability Engine

**Threats:**
- Not noticing deterioration in liquidity / volatility until too late.
- Building signals that are themselves fragile to microstructure noise.

**Defensive design:**
- Multiple independent stability components (liquidity, vol, contagion, funding risk), not a single opaque index.
- Conservative calibration: err on the side of "more unstable" when indicators disagree.
- Telemetry: time series of stability scores with alerts on fast changes.
- Use historical mapping: associate high instability states with past drawdown clusters as a sanity check.

### 4.4 Black Swan Engine (Fragility)

**Threats:**
- Underestimating tail risk to plausible shocks.
- Relying on one risk model or one scenario set.

**Defensive design:**
- Scenario library derived from multiple crises, not just one.
- Use **multiple** risk models (e.g., factor model + historical bootstrap) to evaluate shocks.
- Keep shock mapping intentionally conservative: if several models disagree, take the worse outcome for risk management.
- Integrate with leverage and exposure limits directly (not advisory only).

### 4.5 Assessment Engine (Signals)

**Threats:**
- Overfitting historical patterns → fragile alpha.
- Sensitivity to small input noise or data revisions.
- Hidden dependence on a single feature or data vendor.

**Defensive design:**
- Regularization and cross‑validation with strong time‑based splits.
- Feature importance & sensitivity analysis: detect if a model is driven by a single unstable input.
- Use profile/regime/stability features to **penalize trades in fragile contexts**.
- Keep model complexity proportional to data; log all training and evaluation.

### 4.6 Universe Selection Engine

**Threats:**
- Concentration in illiquid or structurally weak names.
- Being overexposed to names that become easy targets for others.

**Defensive design:**
- Hard constraints on liquidity, exchange, listing rules.
- Incorporate stability/fragility and profile quality into universe scores.
- Stress-test universes under synthetic liquidity shocks.

### 4.7 Portfolio & Risk Engine

**Threats:**
- Excess leverage / concentration.
- Missing hidden correlations (crowding, factor exposures).

**Defensive design:**
- Explicit risk model with factor exposures, cross-checks against realized correlations.
- Hard constraints on exposures (per sector, factor, issuer, country).
- Integrate stability and black-swan fragility as **penalties** or **constraints** in optimization.
- Regular stress tests: what‑if exposures under known bad scenarios.

### 4.8 Meta-Orchestrator (Kronos v2)

**Threats:**
- Auto‑tuning that overfits recent history or synthetic worlds.
- LLM-generated configs that look good in text but fail numerically.

**Defensive design:**
- All config changes must:
  - Be versioned.
  - Pass offline backtests, including regime/stability/fragility slices.
  - Have rollback paths.
- LLM suggestions treated as **proposals only**; the numeric pipeline is the authority.
- Decision logs immutable; meta-analytics reproducible from logs.

---

## 5. Monitoring & Alerts

We need a cross-cutting monitoring layer:

- **Data quality dashboards**: missing data, outliers, schema violations.
- **Risk dashboards**: leverage, factor exposures, stability/fragility metrics.
- **Execution dashboards**: realized slippage vs model, volume participation, sign of adverse selection.
- **Model health dashboards**: feature distributions vs training, performance decay, regime coverage.

Alerts should be tied to:
- Sudden deterioration in stability/fragility scores.
- Execution costs > thresholds.
- Unusual model outputs (e.g., all-in bets, sudden regime changes).

---

## 6. Summary

Defensively, Prometheus v2 must:
- Avoid becoming a predictable, forced flow.
- Detect and respond to regime/stability changes early.
- Keep leverage, concentration, and tail exposure under explicit control.
- Treat all LLM and meta-automation as advisory until numerically validated.

This threat model should be referenced by all engine spec authors to ensure defensive concerns are built in rather than bolted on later.
