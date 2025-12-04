# Algorithms & Model Landscape – Plan

This document sketches the main algorithm families we may use in each subsystem. It is not a commitment to any particular method, but a menu of options we want the architecture to support.

---

## 1. Macro Regime Service

Possible approaches:

- **Rule-based indicator thresholds** (baseline):
  - Use z-scores and thresholds on credit spreads, yield curve slope, vol indices, etc.
- **Markov switching / Hidden Markov Models (HMMs):**
  - Fit regime-switching models to macro feature vectors.
  - Provide regime probabilities instead of hard labels.
- **Clustering-based regimes:**
  - k-means, Gaussian mixtures, or spectral clustering on macro features.
  - Label clusters post-hoc (e.g. expansion, contraction, crisis).

Design implication: the regime engine (`regime_model.py`) should expose a common interface so implementations can be swapped without changing callers.

---

## 2. Universe Selection

Possible approaches:

- **Cross-sectional factor models:**
  - Fama-French style factors + custom quality/growth/value factors.
  - Rank stocks by composite factor scores within regimes.
- **Bayesian ranking / scorecards:**
  - Use logistic/ordinal models or Bayesian scorecards for inclusion probabilities.
- **Robust portfolio selection for base weights:**
  - Penalize concentration, emphasize diversification across sectors/styles.

Design implication: the universe builder should treat scoring as a pluggable component operating on profile + factor inputs.

---

## 3. Profiles & Scoring

Possible approaches:

- **Heuristic score aggregation:**
  - Weighted sums of normalized ratios (ROE, margins, growth, leverage).
- **Bayesian updates over time:**
  - Treat quality/growth scores as latent variables updated each quarter based on fundamentals.
- **ML-based classifiers for risk flags:**
  - Use historical outcomes and profile attributes to predict governance or event risk (if data available).

Design implication: `structured_json` in profiles must be stable and rich enough to support multiple scoring methods; scoring itself should be versioned and configurable.

---

## 4. Risk Management

Possible approaches:

- **Simple risk budgets + caps** (baseline):
  - Max position size, sector caps, gross/net limits.
- **Kelly-inspired sizing:**
  - Use risk-adjusted edge estimates with conservative caps.
- **CVaR / Expected Shortfall constraints:**
  - Estimate tail risk per portfolio and restrict exposure accordingly.
- **Regime-dependent risk budgets:**
  - Allocate higher risk in favorable regimes, lower in adverse regimes.

Design implication: risk engine should support multiple sizing and constraint policies via config, not hard-coded formulas.

---

## 5. Assessment Engine v2

Possible approaches:

- **Rule + LLM hybrid:**
  - Use rules for mechanical filters and LLMs for qualitative trade-offs.
- **Scenario-style prompts:**
  - Ask LLMs to consider multiple scenarios (bull/base/bear) and aggregate.
- **Ranking-based decisions:**
  - Let agents output scores; orchestrator converts them to ranks and thresholds.

Design implication: the orchestrator must be able to combine agent outputs in different ways (weighted averages, voting, thresholds) configurable via `agent_graph_config`.

---

## 6. Meta Orchestrator (Kronos v2)

Possible approaches:

- **Multi-armed bandits:**
  - Treat strategy configs or prompt variants as arms; allocate more weight to winners.
- **Bayesian optimization:**
  - Tune continuous parameters (thresholds, weights) based on backtest/live performance.
- **RL-style adaptation:**
  - View the system as an agent making config choices under regimes; reward is long-term risk-adjusted performance.

Design implication: config proposals should be generic (key/value diffs) and reversible, so different learners can write them.

---

## 7. Black Swan Emergency Engine

Possible approaches:

- **Heuristic rules + thresholds:**
  - Spike detection in volatility, spreads, and news volumes.
- **Anomaly detection:**
  - Statistical outlier detection on macro and cross-asset signals.
- **Topic clustering + LLM classification:**
  - Cluster news events and use LLMs to label cluster types (war, pandemic, systemic crisis).

Design implication: the event detector should allow mixing rule-based, statistical, and LLM-based detectors, each contributing to an overall severity/confidence score.

---

## 8. Monitoring & Diagnostics

- **Drift detection:**
  - Detect drift in data distributions or model outputs (e.g. regime frequencies, decision patterns).
- **Stability analysis:**
  - Track how sensitive decisions are to profile/regime changes.

Design implication: monitoring should log rich enough metrics to support later statistical diagnostics.

---

This landscape is a reference to guide future algorithm choices; the current architecture and plans are intentionally flexible so that we can plug in any of these methods without changing high-level interfaces.