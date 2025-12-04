# System Stability & Soft Target Detection Engine – Detailed Plan

## 1. Purpose & Scope

Maintain continuous profiles of systemically critical entities (~200 total) to answer four questions:
1. **How stable is X?** (vulnerability scoring)
2. **How attackable is X?** (soft target detection)
3. **What would likely trigger X?** (trigger identification)
4. **If X breaks, who gets hit and how fast?** (contagion mapping)

**This is NOT a trading signal generator.** It's an information layer that feeds into decision-making by:
- Providing entity stability scores and states (Stable/Watch/Fragile/Targetable/Breaker)
- Gating what strategies can do (position limits, entry restrictions)
- Enabling pre-scripted SOPs when entities cross thresholds
- Informing the Market Regime Engine (soft targets elevating = regime transition signal)

**Philosophy:**
- Small, curated universe of entities that matter for global contagion
- Profiles built from historical analysis + ongoing monitoring
- State changes are rare and explainable
- 100 elite actors tracked only to gather narrative context for entity profiles


## 2. Monitored Universe (Curated, Not Exhaustive)

### Tier 1: Systemically Critical Entities (~70)
**G-SIBs (30):** JPM, BAC, Citi, GS, MS, HSBC, DB, BNP, etc.
**Sovereigns (15):** US, China, Japan, Germany, UK, Italy, France, Spain, Brazil, Turkey, etc.
**Chokepoints (10):** Malacca Strait, Suez, Panama, Hormuz, TSMC Taiwan, SWIFT, AWS regions, key pipelines
**Central Banks (6):** Fed, ECB, BoJ, PBoC, BoE, SNB
**Critical Commodities (9):** Oil (Saudi/Russia), Wheat (Ukraine/Russia), Semiconductors, Rare earths, Neon gas

### Tier 2: Secondary Monitoring (~100 elite actors)
**Purpose:** Narrative gathering only—what are key decision-makers saying about Tier 1 entities?
- Heads of state (G20 + key others): 25
- Central bank chairs: 10  
- Finance ministers: 15
- Macro hedge fund managers: 20 (Dalio, Jones, Druckenmiller, etc.)
- CEOs of G-SIBs: 30
- Defense/Intelligence leadership: 10

**Data sources:** Official speeches, central bank minutes, earnings calls, major interviews. NOT every tweet or blog post.

## 3. High-Level Architecture

Modules under `stability/` (renamed from `black_swan/`):

- `entities/` – Entity registry and profile management
  - `registry.py` – Master list of Tier 1 entities with metadata
  - `profiles.py` – Build and maintain entity profiles (vulnerability, network position, historical behavior)
- `monitoring/` – Real-time data collection for entities
  - `market_data.py` – CDS, bond spreads, equity prices, flows
  - `infrastructure.py` – AIS ship tracking, satellite imagery, flow meters
  - `narrative.py` – LLM-powered analysis of news/communications about entities
- `scoring/` – Calculate Soft Target Index and state
  - `vulnerability_scorer.py` – Financial, political, operational fragility
  - `criticality_scorer.py` – Network centrality, systemic importance
  - `attack_surface.py` – Ease of attack, historical precedent
  - `soft_target_index.py` – Composite score → state (Stable/Watch/Fragile/Targetable/Breaker)
- `triggers/` – Threshold definitions and monitoring
  - `threshold_manager.py` – Load and evaluate entity-specific thresholds
  - `persistence_checker.py` – Require N hours/days before state change
  - `confirmation_logic.py` – Cross-domain confirmation rules
- `contagion/` – Model who gets hit if entity breaks
  - `graph.py` – Build and maintain contagion network
  - `cascade_simulator.py` – Estimate spread and timing
- `sop/` – Pre-scripted Standard Operating Procedures
  - `sop_templates.py` – Config-based SOPs per entity + state
  - `sop_evaluator.py` – Calculate what actions apply to current portfolio
  - `sop_executor.py` – Interface to risk/execution systems
- `elite_tracker/` – Monitor Tier 2 actors for narrative context
  - `speech_analyzer.py` – LLM analysis of key communications
  - `profile_enrichment.py` – Feed insights into entity profiles
- `storage/` – Database operations
  - Writes: `entity_profiles`, `vulnerability_scores`, `entity_states`, `state_transitions`, `contagion_graph`, `sop_rules`, `sop_executions`
- `api/` – External interface
  - `get_entity_profile(entity_id)`
  - `get_soft_target_scores()`
  - `get_entity_state(entity_id)`
  - `get_contagion_map(entity_id)`
  - `get_active_sops()` – What constraints/actions are currently in effect
  - `evaluate_portfolio_exposure()` – Given current holdings, what's at risk?


## 4. Entity Profile Structure

Each Tier 1 entity has a profile containing:

### Static Components (Updated Quarterly)
- **Identity:** entity_id, name, type, region
- **Network Position:** Criticality score (0-100), centrality measures, primary counterparties
- **Historical Behavior:** Past crises, recovery times, intervention patterns
- **Substitutability:** Alternative sources/routes, switching costs, strategic reserves
- **Contagion Paths:** Tier 1 direct exposures, Tier 2 indirect, Tier 3 systemic (with weights and speeds)

### Dynamic Components (Updated Daily/Hourly)
- **Vulnerability Scores:**
  - Financial: Debt ratios, refinancing needs, reserves, funding access
  - Political: Government stability, election proximity, social cohesion, policy flexibility
  - Operational: Infrastructure state, cyber risk, supply chain dependencies
- **Attack Surface:** 
  - Ease of attack (market depth, defensive capacity)
  - Historical attack success rate
  - Current predatory positioning signals (if detectable)
- **Pressure Metrics:** Rate of change in vulnerability indicators
- **Confidence:** Data coverage and cross-source agreement

### Outputs
- **Soft Target Index (0-100):** Composite of criticality × vulnerability × attack surface × (1/resilience)
- **State Classification:**
  - 0-25: Stable (no action)
  - 25-50: Watch (informational)
  - 50-70: Fragile (tighten entry criteria in radius)
  - 70-85: Targetable (reduce exposure caps, tighten stops)
  - 85-100: Breaker (SOP eligible, consider exit/hedge)

## 5. Data Contracts

### 5.1 Inputs

- Historical DB:
  - `macro_time_series` for sovereign/macro indicators
  - Market data feeds for G-SIB/corporate indicators
  - `news_events` for narrative analysis
- Real-time Data:
  - CDS spreads, bond yields, equity prices (market data vendor)
  - AIS ship tracking (MarineTraffic API)
  - Satellite imagery (Sentinel Hub)
  - Flight tracking (ADS-B Exchange)
- Config:
  - Entity registry and metadata
  - Threshold definitions (entity-specific)
  - SOP templates
  - Contagion graph edges

### 5.2 Outputs

- **entity_profiles** (versioned snapshots):
  - entity_id, profile_version, as_of_date
  - static_data (JSON: network position, historical behavior)
  - last_updated

- **vulnerability_scores** (time series):
  - entity_id, timestamp
  - financial_vulnerability (0-1)
  - political_vulnerability (0-1)
  - operational_vulnerability (0-1)
  - attack_surface (0-1)
  - soft_target_index (0-100)
  - confidence (0-1)
  - contributing_factors (JSON)

- **entity_states** (time series):
  - entity_id, timestamp
  - state (Stable/Watch/Fragile/Targetable/Breaker)
  - state_duration_days
  - trigger_conditions (JSON: which thresholds crossed)
  - alert_level (maps to regime engine: GREEN/YELLOW/ORANGE/RED)

- **state_transitions** (events):
  - transition_id, entity_id, timestamp
  - from_state, to_state
  - trigger_metrics (JSON)
  - confidence
  - human_reviewed (boolean)

- **contagion_graph** (edges, versioned):
  - from_entity, to_entity, version
  - channel (financial/trade/political/narrative)
  - strength (0-1)
  - transmission_speed (hours/days/weeks)
  - last_updated

- **entity_thresholds** (config-driven):
  - entity_id, metric_name
  - stable_threshold, watch_threshold, fragile_threshold, targetable_threshold, breaker_threshold
  - persistence_required (hours/days)
  - confirmation_required (boolean)

- **sop_rules** (config-driven, versioned):
  - entity_id, state, version
  - constraints (JSON: max exposure, banned sectors, tightened stops)
  - actions (JSON: exits, hedges, defensive tilts)
  - human_override_required (boolean)

- **sop_executions** (audit log):
  - execution_id, timestamp
  - entity_id, state_transition_id
  - portfolio_before (snapshot)
  - portfolio_after (snapshot)
  - actions_taken (JSON)
  - human_approved (boolean)
  - outcome (post-mortem classification)

API:
- `get_entity_profile(entity_id, as_of_date=None)` → Full profile
- `get_soft_target_rankings(top_n=10)` → Current highest-risk entities
- `get_entity_state(entity_id)` → Current state + duration + triggers
- `get_contagion_map(entity_id, max_depth=3)` → Who gets hit if this breaks
- `get_most_likely_triggers(entity_id)` → Ranked list with probabilities
- `get_active_sops()` → Currently-in-effect constraints/actions
- `evaluate_portfolio_exposure(entity_id)` → Our current direct/indirect exposure


## 6. Daily Monitoring & Scoring Flow

### 6.1 Data Collection (Continuous)
1. **Market data:** CDS spreads, bond yields, equity prices, options flows (every 5 minutes)
2. **Infrastructure:** AIS ship transits, satellite imagery, traffic flows (hourly or real-time where available)
3. **Narrative:** News scraping, elite communications (hourly)
4. **Macro:** Economic releases, central bank actions (as published)

### 6.2 Vulnerability Scoring (Daily)
For each Tier 1 entity:
1. **Load latest data** for all relevant metrics
2. **Calculate component scores:**
   - Financial: debt/GDP, reserves vs. obligations, funding stress
   - Political: stability indices, election calendars, social unrest
   - Operational: infrastructure health, cyber incidents, supply chain
3. **Calculate attack surface:**
   - Market depth/liquidity
   - Historical attack success
   - Current positioning signals (if detectable)
4. **Calculate resilience:**
   - Policy space (fiscal/monetary)
   - Alliances and backstops
   - Alternative routes/sources
5. **Compute Soft Target Index:**
   ```
   STI = (Criticality × Vulnerability × Attack_Surface) / Resilience
   Bounded 0-100
   ```
6. **Write to `vulnerability_scores` table**

### 6.3 Threshold Evaluation (Continuous)
For each entity:
1. **Load thresholds** from config
2. **Compare current metrics** to thresholds
3. **Check persistence:** Has metric been above threshold for required duration?
4. **Check confirmation:** Are corroborating indicators from different domains also triggering?
5. **Determine state:** Stable/Watch/Fragile/Targetable/Breaker
6. **If state changed:** Log transition, calculate trigger evidence bundle

### 6.4 Contagion Mapping (On State Change)
When entity enters Fragile+ state:
1. **Query contagion graph** for downstream entities
2. **Calculate cascade probabilities** and timing
3. **Identify fallout radius:**
   - Tier 1 (direct): Who holds their debt, derivative exposures
   - Tier 2 (indirect): Trade partners, supply chain dependents
   - Tier 3 (systemic): Confidence effects, safe-haven flows
4. **Store fallout map** for use by other systems

### 6.5 SOP Evaluation (On State Change to Targetable/Breaker)
When entity crosses critical threshold:
1. **Load SOP template** for entity + state
2. **Evaluate current portfolio:**
   - Direct exposure to entity?
   - Exposure to contagion radius?
   - Hedges already in place?
3. **Calculate required actions:**
   - Exits (prioritized by risk)
   - Constraint changes (exposure caps, stop tightening)
   - Hedge recommendations
4. **Determine automation level:**
   - Targetable: Auto-apply constraints, recommend actions
   - Breaker: Execute SOPs (with human confirm if configured)
5. **Write to `sop_executions`** (proposed or executed)

### 6.6 Narrative Enrichment (Weekly Batch)
1. **Scan Tier 2 elite communications:**
   - Central bank minutes/speeches
   - Finance minister statements  
   - Major earnings calls
   - Hedge fund letters/interviews
2. **LLM extraction:**
   - What are they saying about Tier 1 entities?
   - Tone: confident/concerned/alarmed?
   - Positioning signals?
3. **Enrich entity profiles:**
   - Add narrative context
   - Adjust confidence scores based on information quality
   - Flag anomalies (e.g., "Everyone says Italy is fine but CDS is widening")


## 7. Integration with Other Components

### 7.1 Market Regime Engine
**Input TO Regime:**
- If multiple Tier 1 entities enter Fragile/Targetable → increase regime transition probability to Risk-Off
- If any entity enters Breaker → can override regime to Risk-Off / Panic

**Input FROM Regime:**
- In Risk-Off regimes, all vulnerability scores get pessimistic adjustment (liquidity dries up, correlations rise)
- In Risk-On / Low Vol, threshold for state changes can be higher (system has buffers)

### 7.2 Risk Management
**Consumes:**
- Entity states for portfolio radius ("Are we exposed to any Targetable/Breaker entities?")
- SOP constraints (max exposure caps, banned regions/sectors)

**Actions:**
- Tighten stops on positions in contagion radius
- Block new entries in affected regions/sectors
- Force position sizing reduction

### 7.3 Assessment Engine
**Context enrichment:**
- Company profiles include exposure to Tier 1 entities ("Siemens depends on China + EU banks")
- Decision prompts include: "Italy is Fragile state, reduce eurozone enthusiasm"
- Higher bar for companies in Targetable entity radius

### 7.4 Universe Selection
**Gating:**
- States gate what enters universes
- Fragile: Reduce weight of companies in radius
- Targetable: Exclude companies in direct radius
- Breaker: Shrink universe to defensive sectors only

### 7.5 Execution
**Order handling:**
- Targetable/Breaker states → more aggressive execution (accept slippage to get out)
- Normal states → optimize for execution quality

### 7.6 Meta Orchestrator
**Post-mortem analysis:**
- Did state transitions predict actual events?
- Were SOPs effective?
- Update thresholds and SOP templates based on outcomes


## 8. Human Oversight & Controls

### 8.1 Dashboard Views
- **Entity Health Heatmap:** All Tier 1 entities, color-coded by state, sortable by Soft Target Index
- **State Transition Log:** Recent changes, with trigger evidence
- **Contagion Map Visualizer:** Click entity → see downstream cascade
- **Portfolio Exposure Report:** Our current holdings mapped to entity states
- **Active SOPs:** What constraints are in effect right now
- **Elite Narrative Summary:** Weekly digest of key communications

### 8.2 Manual Overrides
- Force entity state (override automatic classification)
- Approve/reject SOP execution (for Breaker-level SOPs)
- Adjust thresholds temporarily ("I know Italy CDS is high but I think it's noise")
- Mark false positive ("System said Targetable but nothing happened, tune down")

### 8.3 Alert Routing
- Watch → Silent (dashboard only)
- Fragile → Email summary (daily)
- Targetable → Slack alert (immediate)
- Breaker → SMS + Slack + Email (immediate, requires human action within 30 min)

### 8.4 Post-Mortem Workflow
After every state transition to Breaker (and quarterly review of Targetable):
1. Was the state change correct? (True positive / False positive)
2. Was timing right? (Too early / Just right / Too late)
3. Did SOPs help? (Preserved capital / Neutral / Cost us money)
4. What should change? (Thresholds / Contagion map / SOP template)
5. Update documentation


## 9. Safeguards Against Overreaction

### 9.1 Persistence Requirements
- Most thresholds require metric to stay above threshold for N hours/days (not just spike)
- Example: Italy CDS > 300bps for 5 consecutive days, not 1 hour

### 9.2 Confirmation Logic
- Require corroboration from different data domains
- Example: Can't go Targetable on CDS alone; need bond yields OR political stress OR funding issues

### 9.3 Cool-Off Timers
- After state downgrade, require M hours before another downgrade (unless Breaker-level evidence)
- Prevents whipsaw from noisy data

### 9.4 Rate Limits
- Max N state changes per entity per month (except hard Breaker triggers)
- If hitting this limit, thresholds are too sensitive

### 9.5 Human Attestation
- Thresholds locked at quarterly reviews
- Ad-hoc changes require justification and change log
- Prevents "let's just tweak it" drift

### 9.6 Confidence-Based Gating
- Low confidence scores (sparse data) reduce state severity
- Example: If we only have 50% confidence on Pakistan, cap at Watch state even if metrics say Fragile

### 9.7 Separation of Concerns
- Scoring and states inform risk; they don't directly place trades
- Only Breaker state can unlock SOPs
- This prevents overtrading on every state wiggle

## 10. Implementation Phases

### Phase 1 (Month 1): Entity Registry & Profiles
- Define Tier 1 entity list (~70 entities)
- Build profile templates
- Historical analysis: collect 10 years of data per entity
- Establish baseline vulnerability/criticality scores

### Phase 2 (Month 2): Data Pipelines
- Wire up market data feeds (CDS, bonds, equity)
- Implement infrastructure monitoring (AIS, satellite if feasible)
- News ingestion for Tier 1 entities
- Store in `vulnerability_scores` time series

### Phase 3 (Month 3): Scoring & States
- In the current v1 Prometheus implementation, soft-target state
  assignments and their empirical transitions are also summarized into a
  simple Markov-chain based `StabilityStateChangeForecaster`. This
  forecaster exposes `SoftTargetChangeRisk` objects which provide
  multi-step probabilities of worsening (e.g. moving towards TARGETABLE
  or BREAKER). Downstream engines can consume the scalar
  `risk_score` in [0, 1] as a generic fragility indicator without
  committing to any specific SOP or contagion logic yet.
- In the current v1 Prometheus implementation, soft-target state
  assignments and their empirical transitions are also summarized into a
  simple Markov-chain based `StabilityStateChangeForecaster`. This
  forecaster exposes `SoftTargetChangeRisk` objects which provide
  multi-step probabilities of worsening (e.g. moving towards TARGETABLE
  or BREAKER). Downstream engines can consume the scalar
  `risk_score` in [0, 1] as a generic fragility indicator without
  committing to any specific SOP or contagion logic yet.
- Implement vulnerability scoring algorithms
- Define thresholds (entity-specific, from historical analysis)
- Implement state classification logic
- Persistence and confirmation checks
- Test on historical crises (2008, 2011 Euro, 2020, etc.)

### Phase 4 (Month 4): Contagion Mapping
- Build contagion graph (research-intensive)
- Implement cascade simulator
- Validate against historical events (Greece → Spain/Italy, Lehman → global)

### Phase 5 (Month 5): SOP Framework
- Define SOP templates for key entities + states
- Build portfolio exposure calculator
- Wire SOPs into risk management constraints
- Implement human approval workflow

### Phase 6 (Month 6): Elite Tracker & Narrative
- Implement Tier 2 monitoring (official communications only)
- LLM-based narrative extraction
- Profile enrichment pipeline

### Phase 7 (Month 7+): Integration & Live Monitoring
- Wire into Market Regime Engine (bidirectional)
- Wire into Risk/Assessment/Universe systems
- Build dashboards
- Paper trade mode (monitor states, don't execute SOPs)
- Tune thresholds based on false positive rate

### Phase 8 (Month 10+): Live Operation
- Enable SOP execution for select entities
- Gradual rollout (start with non-financial entities, lower stakes)
- Quarterly reviews and threshold recalibration
- Post-mortem every Breaker event

---

## 11. Implementation Status (current pass - legacy)

- Implemented a minimal **package core** under `prometheus.black_swan`:
  - `storage.py` with helpers for `black_swan_events`, `black_swan_state_history`,
    and `black_swan_sop_actions`.
  - `state_manager.py` with a simple NORMAL/ELEVATED_RISK/EMERGENCY state
    machine and history logging.
  - `sop_engine.py` with basic SOP templates for EMERGENCY state (tighten risk
    limits, shrink universes, reduce execution aggressiveness).
  - `api.py` exposing:
    - `get_black_swan_state()`
    - `get_active_black_swan_event()`
    - `propose_emergency_actions()`
    - `register_manual_black_swan_event()` which records an event, updates
      state, and logs SOP actions as `PROPOSED`.
- Added unit tests on in-memory SQLite to validate event/state/SOP storage and
  the manual event registration helper.
- Added `dev_workflows/PHASE12_BLACK_SWAN.md` documenting how to register manual
  events, inspect state, and query SOP actions.

### Migration from Legacy Black Swan Implementation

The current minimal black_swan package is event-based (detect sudden crises, trigger EMERGENCY state). The new system is profile-based (continuous monitoring of entity stability).

**Migration path:**
1. Rename package: `black_swan/` → `stability/`
2. Preserve existing state_manager/sop_engine as-is for backward compatibility
3. Build new entity-based system alongside
4. Gradually migrate: event-based emergency triggers become "if entity enters Breaker, generate event"
5. Eventually deprecate old event-centric model once profile system proven

### Deferred TODOs for Later Passes

- **Mathematical tail and dependence modelling (v3/v4)**
  - Use extreme-value tools (GEV, Hill estimators, Student-t or
    generalized hyperbolic fits) on entity-related return and spread
    series to calibrate and periodically revalidate SoftTargetIndex
    thresholds.
  - Introduce simple copula/tail-dependence summaries between entities
    (and between entities and broad markets) to refine contagion graphs
    and to quantify how likely "everything breaks together" scenarios
    really are.
  - Where intraday/order-flow data becomes available, consider Hawkes
    process-style models for clustering of stress events to better
    distinguish transient spikes from true regime/fragility shifts.

- **Advanced attack pattern detection:**
  - Options flow analysis for predatory positioning
  - Coordinated narrative campaign detection (social media)
  - Elite behavioral signals (private jet tracking, insider sales)
  - This is valuable but secondary to core vulnerability monitoring

- **Machine learning enhancements:**
  - Train models on historical entity states → outcomes
  - Improve trigger prediction beyond rule-based thresholds
  - Only pursue if rule-based system proves insufficient

- **Real-time infrastructure monitoring:**
  - Satellite imagery analysis (port congestion, military movements)
  - Cyber threat intelligence feeds
  - Power grid / internet traffic monitoring
  - Expensive data sources, defer until core system validated

- **Expanded universe:**
  - Add more sovereigns, regional banks, sector-specific chokepoints
  - Only after Tier 1 monitoring (~70 entities) is stable and useful

- **Automated SOP execution for all states:**
  - Currently require human approval for Breaker SOPs
  - As confidence grows, allow auto-execution
  - But maintain human oversight for years before full automation

## Future: Fragility pattern embedding space

A later phase will map stability/fragility states, scenarios, and entities
into a joint embedding space to cluster typical failure modes and to measure
similarity between current conditions and past stress episodes, as described
in the "Stability and Black Swan – Fragility Pattern Space" use case in
`docs/new_project_plan/joint_embedding_shared_spaces_plan.md`.
