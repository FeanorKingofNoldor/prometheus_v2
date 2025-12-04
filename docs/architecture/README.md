# Prometheus v2 - Architecture Documentation

Complete architectural blueprint with detailed diagrams showing every component, function, and dataflow.

## 📚 Documentation Structure

### **Mermaid Diagrams** (High-Level Overviews)
Located in: `docs/architecture/*.md` → rendered to `docs/architecture/generated/*.svg`

1. **00_overview.md** - System overview showing all major components
2. **20_engines.md** - Engine interaction and dataflows
3. **30_database_schema.md** - Complete database ERD with all 37 tables
4. **99_master_architecture.md** - THE MASTER DIAGRAM - everything end-to-end

### **PlantUML Diagrams** (Detailed Blueprints)
Located in: `docs/architecture/plantuml/` → rendered to `docs/architecture/plantuml/generated/*.svg`

#### **Components** (`plantuml/components/`)
- **01_complete_system.puml** - Every package, class, and function prototype
  - All 15 Python packages
  - All public methods with signatures
  - All dataclasses with fields
  - Dependencies between components

#### **Sequences** (`plantuml/sequences/`)
- **live_trading_flow.puml** - Complete daily live trading cycle
  - Market state transitions (PRE_OPEN → SESSION → POST_CLOSE)
  - Every engine execution step
  - IBKR order submission and fill handling
  - Decision logging
  
- **backtesting_flow.puml** - Backtesting with TimeMachine
  - Time-gated data access (no look-ahead)
  - MarketSimulator fill modeling
  - Complete backtest loop day-by-day

---

## 🎯 Quick Start - View All Diagrams

### **Render Everything:**
```bash
# Render Mermaid diagrams
bash scripts/render_mermaid_docs.sh

# Render PlantUML diagrams
bash scripts/render_plantuml.sh

# View all diagrams
bash scripts/view_diagrams.sh  # Opens Mermaid in Firefox
firefox docs/architecture/plantuml/generated/*.svg  # Opens PlantUML
```

### **Watch Mode** (auto-regenerate on file changes):
```bash
# For Mermaid
bash scripts/watch_mermaid_docs.sh

# For PlantUML (manual re-run needed)
# Edit .puml files, then run:
bash scripts/render_plantuml.sh
```

---

## 📊 What Each Diagram Shows

### **99_master_architecture.md** ⭐ START HERE
**The One Diagram to Rule Them All**

Shows:
- External data sources → Ingestion → Storage
- Storage → Encoders → Engines
- Engines → Execution → IBKR/Simulator
- Meta-Orchestrator → Kronos Chat → UI
- All 37 database tables grouped logically
- Complete dataflow paths

**When to use:** First-time overview, explaining system to others, architecture reviews

---

### **01_complete_system.puml** ⭐ FOR IMPLEMENTATION
**Every Function You Need to Write**

Shows:
- **prometheus.core** - Config, Database, Logger, TradingCalendar, IDGenerator
- **prometheus.data** - DataReader, FeatureBuilder, DataWriter
- **prometheus.encoders** - TextEncoder, NumericWindowEncoder, JointEncoder
- **prometheus.profiles** - ProfileService, ProfileSnapshot, ProfileBuilder
- **prometheus.regime** - RegimeEngine, RegimeState, RegimeClassifier
- **prometheus.stability** - StabilityEngine, StabilityVector, SoftTargetClass
- **prometheus.assessment** - AssessmentEngine, FragilityAlphaEngine, InstrumentScore
- **prometheus.universe** - UniverseEngine, Universe
- **prometheus.portfolio** - PortfolioEngine, RiskReport
- **prometheus.execution** - BrokerInterface, LiveBroker, BacktestBroker, MarketSimulator, TimeMachine, OrderPlanner
- **prometheus.meta** - MetaOrchestrator, EnginePerformanceReport, Experiment
- **prometheus.orchestration** - DAGOrchestrator, MarketStateMonitor

**Function signatures include:**
- Parameter names and types
- Return types
- Public methods (+)
- Private methods (-)
- Dataclass fields

**When to use:** 
- Writing code stubs
- Designing interfaces
- Code reviews
- API documentation

---

### **live_trading_flow.puml** ⭐ FOR OPERATIONS
**How the System Runs Every Day**

Timeline:
1. **T-1 Evening** - Market close → Ingestion starts
2. **T Morning PRE_OPEN** - Quality checks
3. **T Day SESSION** - Market trading (monitored, no actions)
4. **T Day POST_CLOSE** - All engines run in sequence
5. **T Day Evening** - Orders sent to IBKR
6. **Async** - Fills processed as they arrive

Shows exact function calls:
- `DAGOrchestrator.schedule_dag("us_eq_engines_T")`
- `RegimeEngine.get_regime(as_of_date=T, region="US")`
- `StabilityEngine.compute_stability_batch(entities, T)`
- `AssessmentEngine.score_strategy_default("main", "US_EQ", T)`
- `PortfolioEngine.optimize("main", T, universe, scores)`
- `LiveBroker.submit_order(order)` → `IBKR.placeOrder()`

**When to use:**
- Understanding daily operations
- Debugging production issues
- Designing monitoring/alerts
- Training operators

---

### **backtesting_flow.puml** ⭐ FOR VALIDATION
**How Backtests Work (No Look-Ahead Bias)**

Key insight: **TimeMachine gates every data access**

Shows:
- `TimeMachine.set_date(current_date)` before each day
- All engines call `TimeMachine.get_data(table, filters)`
- TimeMachine enforces: `WHERE date <= current_date`
- MarketSimulator simulates fills at EOD using day's OHLCV
- Slippage, volume constraints modeled

Flow per day:
1. Set current date in TimeMachine
2. Run all engines (exactly like live, but with time-gated data)
3. Submit orders to BacktestBroker (queued)
4. Process fills via MarketSimulator at EOD
5. Update positions and cash
6. Log snapshot
7. Advance to next trading day

**When to use:**
- Validating strategies before live
- Understanding why backtests != live results
- Designing slippage/impact models
- Kronos experiment validation

---

### **30_database_schema.md**
**All 37 Tables with Column Details**

**Runtime DB (24 tables):**
- Core entities: markets, issuers, instruments, portfolios, strategies
- Profiles: profiles
- Decision logging: engine_decisions, executed_actions, decision_outcomes
- Configs: engine_configs, models
- Execution: orders, fills, positions_snapshots
- Engine outputs: regimes, stability_vectors, fragility_measures, soft_target_classes, instrument_scores, universes, target_portfolios, portfolio_risk_reports
- Scenarios: scenario_sets, scenario_paths

**Historical DB (13 tables):**
- Market data: prices_daily, returns_daily, factors_daily, instrument_factors_daily, volatility_daily, correlation_panels
- Text & events: news_articles, news_links, filings, earnings_calls, macro_events
- Embeddings: text_embeddings, numeric_window_embeddings, joint_embeddings

**When to use:**
- Writing Alembic migrations
- Designing data access patterns
- Query optimization
- Database capacity planning

---

## 🔧 Modifying Diagrams

### **Mermaid** (high-level overviews)
1. Edit `.md` files in `docs/architecture/`
2. Run `bash scripts/render_mermaid_docs.sh`
3. View in browser: `bash scripts/view_diagrams.sh`

**Syntax:** https://mermaid.js.org/

### **PlantUML** (detailed blueprints)
1. Edit `.puml` files in `docs/architecture/plantuml/`
2. Run `bash scripts/render_plantuml.sh`
3. View: `firefox docs/architecture/plantuml/generated/*.svg`

**Syntax:** https://plantuml.com/

---

## 📏 Scale & Estimates

**Components:**
- 15 Python packages
- 7 core engines
- 37 database tables
- 23+ specification documents

**Code Estimate:**
- **~100,000-120,000 lines of Python**
- ~18,000 lines of tests
- ~5,000 lines of SQL
- ~2,000 lines of YAML configs

**Timeline Estimate (2 developers):**
- Phase 1 (Foundations): 2-3 months
- Phase 2 (Engines): 4-6 months  
- Phase 3 (Execution): 2-3 months
- Phase 4 (Meta & Polish): 2-3 months
- **Total: 10-15 months**

---

## 🗂️ Files Generated

```
docs/architecture/
├── README.md                           ← You are here
├── 00_overview.md                      ← Mermaid source
├── 20_engines.md                       ← Mermaid source
├── 30_database_schema.md               ← Mermaid source
├── 99_master_architecture.md           ← Mermaid source (THE BIG ONE)
├── generated/                          ← Rendered Mermaid SVGs
│   ├── 00_overview.md
│   ├── 00_overview_assets/
│   │   └── 00_overview-1.svg
│   ├── 20_engines.md
│   ├── 20_engines_assets/
│   │   └── 20_engines-1.svg
│   ├── 30_database_schema.md
│   ├── 30_database_schema_assets/
│   │   └── 30_database_schema-1.svg
│   ├── 99_master_architecture.md
│   └── 99_master_architecture_assets/
│       └── 99_master_architecture-1.svg
└── plantuml/                           ← PlantUML sources
    ├── components/
    │   └── 01_complete_system.puml     ← Every class & function
    ├── sequences/
    │   ├── live_trading_flow.puml      ← Daily operations
    │   └── backtesting_flow.puml       ← Backtest with TimeMachine
    └── generated/                       ← Rendered PlantUML SVGs
        ├── 01_complete_system.svg
        ├── live_trading_flow.svg
        └── backtesting_flow.svg
```

---

## 🚀 Next Steps

1. **Review the master diagram** - `firefox docs/architecture/generated/99_master_architecture_assets/*.svg`
2. **Study component details** - `firefox docs/architecture/plantuml/generated/01_complete_system.svg`
3. **Understand daily operations** - `firefox docs/architecture/plantuml/generated/live_trading_flow.svg`
4. **Learn backtesting flow** - `firefox docs/architecture/plantuml/generated/backtesting_flow.svg`
5. **Start coding** - Use component diagram as your implementation checklist

---

## 📖 Specification Documents

All detailed specs in: `docs/specs/`

Key specs:
- `000_repo_audit_and_reuse.md` - v1 → v2 migration
- `010_foundations.md` - Tech stack, package layout, conventions
- `015_execution_and_backtesting.md` - IBKR integration, market simulator ⭐ NEW
- `020_data_model.md` - Database schemas
- `030_encoders_and_embeddings.md` - ML models
- `100_regime_engine.md` through `170_synthetic_scenarios.md` - Engine specs
- `180_testing_and_validation.md` - Quality gates
- `200_monitoring_and_ui.md` - Bloomberg-style UI

---

**You now have the complete blueprint to build Prometheus v2.**

Every function, every class, every dataflow - documented and visualized.

Ready to code! 🔨
