# Revised Plans Summary

## Changes Made (2025-11-21)

### 1. Market Regime Detection Engine (formerly Macro Regime Service)

**Key Changes:**
- **Focus shifted from coincident to forward-looking** indicators that lead equity moves by 1-6 months
- **15 specific indicators** across 5 categories (Credit, Rates, Internals, Flows, Macro) instead of generic "macro indicators"
- **6 regime classifications** with clear definitions (Risk-On Low/High Vol, Transition, Risk-Off Grinding/Panic, Policy Recovery)
- **Hierarchical decision tree** classification instead of weighted scoring (explainable, debuggable)
- **Warning cluster logic** (GREEN/YELLOW/ORANGE/RED alerts based on cross-domain confirmation)
- **Strategy parameter adaptation** - not just position sizing, but entry bars, stop distances, strategy mix
- **Philosophy: Dormant 95% of time** - only acts when multiple domains confirm danger
- **Backtesting framework** with clear success metrics (lead time, false positive rate, Sharpe improvement)
- **Minimal LLM use** - one focused task (corporate guidance sentiment) instead of heavy LLM dependency

**Implementation:**
- Phased rollout over 6 months
- Start with 5 easiest indicators, add complexity gradually
- Must prove >0.3 Sharpe improvement or >10% drawdown reduction vs. baseline

---

### 2. System Stability & Soft Target Detection Engine (formerly Black Swan Emergency)

**Key Changes:**
- **Renamed and reframed:** Not event detection, but continuous entity stability monitoring
- **Curated universe:** ~70 Tier 1 entities (G-SIBs, sovereigns, chokepoints, central banks) + ~100 elite actors for narrative
- **Four questions answered:** How stable? How attackable? What triggers? Who gets hit?
- **Information layer, not trading signals:** Feeds into decision-making via gating rules and SOPs
- **Entity profiles:** Static (network position, historical) + Dynamic (vulnerability scores, attack surface)
- **Soft Target Index (0-100)** → 5 states (Stable/Watch/Fragile/Targetable/Breaker)
- **Thresholds with persistence and confirmation** - prevents whipsaw from noisy data
- **Contagion mapping:** Model cascade paths and timing if entity breaks
- **Pre-scripted SOPs:** Config-driven responses per entity + state, not reactive improvisation
- **Elite tracker:** Tier 2 actors monitored only for narrative context about Tier 1 entities

**Implementation:**
- Phased rollout over 10 months
- Start with entity registry and profiles (historical analysis)
- Build data pipelines, scoring, contagion, SOPs incrementally
- Paper trade mode before live execution
- Human approval required for Breaker SOPs initially

---

## Integration Between Systems

**Bidirectional:**
- Stability Engine → Regime: Entity states elevating → increase Risk-Off transition probability
- Regime → Stability: Risk-Off regime → all vulnerability scores get pessimistic adjustment

**Both systems inform (not dictate):**
- Risk Management (constraints)
- Assessment Engine (context)
- Universe Selection (gating)
- Strategy parameters (adaptation)

---

## Philosophy: Simplicity Over Cathedral

Both systems designed to:
- **Start simple** (5-10 indicators, basic logic)
- **Prove value** (backtesting, paper trading)
- **Add complexity only when needed** (based on evidence)
- **Be dormant most of the time** (rare state changes, infrequent alerts)
- **Avoid overtrading** (persistence, confirmation, rate limits)
- **Maintain explainability** (decision trees, not black boxes)

**Success criteria:**
- Lead time on regime transitions (30-90 days)
- False positive rate (<30%)
- Sharpe improvement (+0.3) or drawdown reduction (-10%+)
- Post-mortem accuracy (state changes predicted real events)

---

## What Was Removed

**From Regime Engine:**
- 50+ indicator complexity
- Weighted scoring systems (too brittle)
- Heavy LLM dependency
- Real-time tick-by-tick monitoring
- Complex ML models (deferred until rule-based proven insufficient)

**From Stability Engine:**
- Event-centric "something just happened" detection
- Trying to monitor entire world (1000s of entities)
- Attack pattern detection without data (options flow, positioning - can't see it with lag)
- Automated trading on every alert
- Social media monitoring at scale (noise)

**Why removed:** These add complexity without proportional edge. Build foundation first, add cathedral later if needed.
