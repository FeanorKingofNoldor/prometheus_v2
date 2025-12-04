# System Stability & Soft Target Detection Engine - Rewrite Progress

**Status**: Core implementation COMPLETE ✅  
**Next**: Database migrations → Assessment Engine integration → Monitoring UI

---

## Completed Components

### 1. Storage Layer ✅
**File**: `prometheus/stability/storage.py`

- All table operations (profiles, scores, states, transitions)
- Query helpers for Assessment Engine integration
- Monitoring/dashboard endpoints
- Schema documented inline (8 tables total)

### 2. Entity Registry ✅
**File**: `prometheus/stability/entities.py`

- **70 Tier-1 entities defined**:
  - 30 G-SIBs (US, Europe, Asia banks)
  - 15 Sovereigns (US, China, EU, etc.)
  - 10 Chokepoints (Malacca, Hormuz, Suez, SWIFT, etc.)
  - 6 Central Banks (Fed, ECB, BOJ, PBOC, etc.)
  - 9 Critical Commodities (Oil, Gas, Semiconductors, etc.)
- Each entity has: ID, name, type, region, tier, centrality, stability baseline
- Registry operations: lookup by ID, type, region
- **Planned extension (Phase 2)**: add `POSITION` entities representing key institutional roles (e.g., US_PRESIDENT, FED_CHAIR, ECB_PRESIDENT), with a separate data layer mapping each role to the current occupant over time. This avoids hard-coding specific people while still tracking the right decision-makers at each date.

### 3. Vulnerability Scoring ✅
**File**: `prometheus/stability/scoring.py`

- **4 vulnerability dimensions** (0-1 scores):
  - Financial: CDS, leverage, liquidity (entity-type specific)
  - Political: regime stability, sanctions, unrest
  - Operational: dependencies, single points of failure
  - Attack Surface: short interest, geopolitical exposure
- **Soft Target Index** (0-100): weighted composite
- Explainability: breakdown dict for every score
- Entity-type-specific thresholds (G-SIBs ≠ sovereigns ≠ commodities)

### 4. State Classification ✅
**File**: `prometheus/stability/classification.py`

- **5 entity states**:
  - Stable (STI < 30)
  - Watch (30-45)
  - Fragile (45-60)
  - Targetable (60-75)
  - Breaker (>75)
- **Persistence requirements**: 1-5 consecutive days above threshold
- **Confirmation checks**: ≥2 dimensions elevated for high-risk states
- Alert level mapping: GREEN/YELLOW/ORANGE/RED (regime-compatible)

### 5. Engine Orchestration ✅
**File**: `prometheus/stability/engine.py`

- Daily computation pipeline:
  1. Fetch metrics (placeholder - will connect to data layer)
  2. Score vulnerabilities
  3. Classify states (with persistence/confirmation)
  4. Persist scores + states
  5. Log transitions
- `initialize_entity_profiles()`: one-time DB seeding
- CLI entrypoint for testing

### 6. Public API ✅
**File**: `prometheus/stability/api.py`

- **`get_stability_context_for_assessment()`**: main integration point
  - Returns: current states, top soft targets, recent transitions
- Monitoring helpers: `list_current_states()`, `list_recent_transitions()`, `get_entity_details()`

### 7. Package Init ✅
**File**: `prometheus/stability/__init__.py`

- Clean public exports for Assessment Engine

---

## TODO (Next Steps)

### A. Database Migrations (Alembic) ✅
**Status**: COMPLETE

Created migrations:
- **0007_regime_engine.py**: 4 tables for Market Regime Detection Engine
  - regime_state, indicator_readings, regime_transitions, transition_probabilities
- **0008_stability_engine.py**: 8 tables for System Stability Engine
  - entity_profiles, vulnerability_scores, entity_states, state_transitions
  - contagion_graph, entity_thresholds, sop_rules, sop_executions (Phase 2)

**To apply**: `alembic -x db=historical upgrade head`

**Note**: Contagion + SOP tables are defined but not yet used (Phase 2).

### B. Data Layer Integration
**Priority**: MEDIUM  
**Effort**: 2-3 hours

Replace `fetch_entity_metrics()` placeholder with real queries:
- Financial: CDS spreads, balance sheet ratios (from market data)
- Political: regime stability scores (vendor API or internal model)
- Operational: capacity metrics, dependencies (config + live data)
- Attack surface: short interest, news sentiment (alternative data)

### C. Assessment Engine Integration
**Priority**: HIGH  
**Effort**: 1 hour

Wire `get_stability_context_for_assessment()` into Assessment Engine:
- Feed top soft targets into portfolio construction
- Use entity states as risk gates (e.g., avoid Targetable/Breaker entities)
- Use recent transitions as early warning signals

### D. Contagion Mapping (Phase 2)
**Priority**: MEDIUM  
**Effort**: 3-4 hours

Build contagion graph:
- Define edges: who gets hit if X breaks
- Channels: financial/trade/political/narrative
- Strength (0-1) + transmission speed (hours/days/weeks)
- Use in Assessment Engine: "If Deutsche Bank goes Breaker, exit these 5 companies"

### E. SOP Framework (Phase 2)
**Priority**: MEDIUM  
**Effort**: 3-4 hours

Pre-scripted Standard Operating Procedures:
- Per entity + state: what to do when JPM goes Fragile?
- Constraints: max exposure, banned sectors
- Actions: exits, hedges, cash raises
- Human override required for Breaker states

### F. Monitoring UI/Dashboards
**Priority**: MEDIUM  
**Effort**: 2-3 hours

Build monitoring endpoints/dashboards:
- Entity state heatmap (by region, type)
- Top 10 soft targets (real-time)
- Recent state transitions (alerts)
- Vulnerability trends (time series)

---

## File Structure Summary

```
prometheus/stability/
├── __init__.py           # Public exports
├── api.py                # Assessment Engine + monitoring APIs
├── storage.py            # Database operations (8 tables)
├── entities.py           # 70 Tier-1 entity registry
├── scoring.py            # Vulnerability scoring (4 dimensions → STI)
├── classification.py     # State classification (5 states, persistence, confirmation)
└── engine.py             # Daily orchestration pipeline
```

---

## Integration Points

### Assessment Engine
```python
from prometheus.stability import get_stability_context_for_assessment

context = get_stability_context_for_assessment(top_k=10)
# Use context["top_soft_targets"] to avoid vulnerable entities
# Use context["recent_transitions"] as early warning
```

### Monitoring/UI
```python
from prometheus.stability import list_current_states, list_recent_transitions

states = list_current_states()  # Dashboard heatmap
transitions = list_recent_transitions(limit=20)  # Alert feed
```

---

## Key Architectural Decisions

1. **~70 Tier-1 entities** (not thousands) - prioritization matters
2. **Soft Target Index (0-100)** - explainable composite score
3. **5 states with persistence/confirmation** - avoid false positives
4. **Alert levels** (GREEN/YELLOW/ORANGE/RED) - compatible with Regime Engine
5. **Dormant 95% of time** - only acts when multiple dimensions confirm danger
6. **Information layer, not trade signals** - feeds Assessment Engine, doesn't trade directly

---

## Testing Strategy

1. **Unit tests**: scoring functions, classification logic
2. **Integration tests**: full pipeline with mock data
3. **Backtesting**: run on historical data (2008, 2020, 2022 crises)
4. **Live monitoring**: deploy in shadow mode alongside Assessment Engine

---

## Notes

- Contagion and SOP frameworks are defined but not implemented (Phase 2)
- Current scoring uses placeholder thresholds - tune after backtesting
- ~100 elite actors for narrative tracking NOT included (later iteration)
- Persistence/confirmation thresholds are conservative - may need tuning
