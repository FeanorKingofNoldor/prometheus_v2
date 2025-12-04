# Prometheus v2 – MASTER ARCHITECTURE

Complete end-to-end architecture showing all components, dataflows, and integrations.

## The Complete System

```mermaid
graph TB
    %% ============ EXTERNAL WORLD ============
    subgraph EXT["🌐 EXTERNAL WORLD"]
        IBKR["IBKR Gateway/TWS<br/>(Port 7496 live, 4001 paper)"]
        MKT_DATA["Market Data Providers<br/>(Yahoo, Bloomberg, etc.)"]
        NEWS_FEED["News & Text Feeds<br/>(Reuters, filings, transcripts)"]
        MACRO_DATA["Macro Data<br/>(FRED, ECB, BOJ)"]
    end
    
    %% ============ DATA INGESTION ============
    subgraph INGEST["📥 DATA INGESTION LAYER"]
        direction TB
        INGEST_PRICE["Price Ingestion<br/>(OHLCV, adjustments)"]
        INGEST_TEXT["Text Ingestion<br/>(news, filings, calls)"]
        INGEST_MACRO["Macro Ingestion<br/>(rates, events)"]
        INGEST_BROKER["Broker Data<br/>(positions, fills)"]
    end
    
    %% ============ STORAGE ============
    subgraph STORAGE["💾 STORAGE LAYER"]
        direction TB
        subgraph HIST_DB["historical_db (Postgres)"]
            PRICES["prices_daily<br/>returns_daily<br/>volatility_daily<br/>factors_daily"]
            TEXT_DATA["news_articles<br/>filings<br/>earnings_calls<br/>macro_events"]
            EMBEDDINGS["text_embeddings<br/>numeric_window_embeddings<br/>joint_embeddings"]
        end
        
        subgraph RUN_DB["runtime_db (Postgres)"]
            ENTITIES["markets<br/>issuers<br/>instruments<br/>portfolios<br/>strategies"]
            PROFILES_TBL["profiles"]
            DECISIONS["engine_decisions<br/>executed_actions<br/>decision_outcomes"]
            EXEC_TBL["orders<br/>fills<br/>positions_snapshots"]
            ENGINE_OUT["regimes<br/>stability_vectors<br/>fragility_measures<br/>instrument_scores<br/>universes<br/>target_portfolios"]
            CONFIGS["engine_configs<br/>models"]
        end
        
        FILES["📁 Blob Storage<br/>(embeddings, models,<br/>correlation matrices)"]
    end
    
    %% ============ REPRESENTATION LAYER ============
    subgraph REPR["🧬 REPRESENTATION LAYER"]
        direction TB
        TEXT_ENC["Text Encoders<br/>(transformer-based)"]
        NUM_ENC["Numeric Window Encoders<br/>(LSTM, CNN)"]
        JOINT_ENC["Joint Multi-Entity Encoder<br/>(cross-modal fusion)"]
        PROF_SVC["Profile Service<br/>(ProfileSnapshot builder)"]
    end
    
    %% ============ CORE ENGINES ============
    subgraph ENGINES["⚙️ CORE DECISION ENGINES"]
        direction TB
        REGIME["100 - Regime Engine<br/>→ CRISIS, CARRY, RECOVERY, etc."]
        STAB["110 - Stability & Soft-Target<br/>→ StabilityVector, SoftTargetClass"]
        FRAG["135 - Fragility Alpha<br/>→ SoftTargetScore, bearish ideas"]
        ASSESS["130 - Assessment Engine<br/>→ InstrumentScores (all alpha families)"]
        UNIV["140 - Universe Selection<br/>→ CORE/SATELLITE/WATCHLIST"]
        PORT["150 - Portfolio & Risk<br/>→ target_positions, risk reports"]
        SYN["170 - Synthetic Scenario Engine<br/>→ stress scenarios"]
    end
    
    %% ============ EXECUTION LAYER ============
    subgraph EXEC["🎯 EXECUTION LAYER"]
        direction TB
        ORDER_PLAN["Order Planner<br/>(compute deltas)"]
        BROKER_IF["BrokerInterface<br/>(abstract)"]
        
        subgraph BROKERS["Broker Implementations"]
            LIVE_BROKER["LiveBroker<br/>(IBKR live)"]
            PAPER_BROKER["PaperBroker<br/>(IBKR paper)"]
            BT_BROKER["BacktestBroker<br/>(simulator)"]
        end
        
        subgraph BT_INFRA["Backtesting Infrastructure"]
            TIME_MACHINE["TimeMachine<br/>(time-travel data access)"]
            MKT_SIM["MarketSimulator<br/>(fill modeling, slippage)"]
        end
    end
    
    %% ============ META & ORCHESTRATION ============
    subgraph META["🧠 META & ORCHESTRATION"]
        direction TB
        KRONOS["160 - Meta-Orchestrator (Kronos v2)<br/>→ analytics, experiments, config optimization"]
        ORCH["013 - DAG Orchestrator<br/>→ job scheduling per market state"]
        CAL["012 - TradingCalendar<br/>→ market states, sessions"]
    end
    
    %% ============ MONITORING & UI ============
    subgraph MON["📊 MONITORING & UI"]
        direction TB
        WEB_API["REST/WebSocket API<br/>(status, performance, alerts)"]
        UI["200 - Bloomberg-style UI<br/>(dark theme, multi-window)"]
        KRONOS_CHAT["Kronos Chat<br/>(LLM-powered analytics)"]
    end
    
    %% ============ CONNECTIONS: External → Ingestion ============
    MKT_DATA --> INGEST_PRICE
    NEWS_FEED --> INGEST_TEXT
    MACRO_DATA --> INGEST_MACRO
    IBKR --> INGEST_BROKER
    
    %% ============ CONNECTIONS: Ingestion → Storage ============
    INGEST_PRICE --> PRICES
    INGEST_TEXT --> TEXT_DATA
    INGEST_MACRO --> TEXT_DATA
    INGEST_BROKER --> EXEC_TBL
    
    %% ============ CONNECTIONS: Storage → Representation ============
    TEXT_DATA --> TEXT_ENC
    PRICES --> NUM_ENC
    TEXT_DATA --> PROF_SVC
    ENTITIES --> PROF_SVC
    
    TEXT_ENC --> JOINT_ENC
    NUM_ENC --> JOINT_ENC
    PROF_SVC --> JOINT_ENC
    
    TEXT_ENC --> EMBEDDINGS
    NUM_ENC --> EMBEDDINGS
    JOINT_ENC --> EMBEDDINGS
    PROF_SVC --> PROFILES_TBL
    
    %% ============ CONNECTIONS: Representation → Engines ============
    JOINT_ENC --> REGIME
    JOINT_ENC --> STAB
    JOINT_ENC --> ASSESS
    
    PROFILES_TBL --> STAB
    PROFILES_TBL --> FRAG
    PROFILES_TBL --> ASSESS
    
    PRICES --> REGIME
    PRICES --> STAB
    PRICES --> ASSESS
    PRICES --> SYN
    
    %% ============ CONNECTIONS: Engine → Engine ============
    REGIME --> STAB
    REGIME --> ASSESS
    REGIME --> KRONOS
    
    STAB --> FRAG
    STAB --> ASSESS
    STAB --> KRONOS
    
    FRAG --> ASSESS
    FRAG --> KRONOS
    
    ASSESS --> UNIV
    ASSESS --> KRONOS
    
    UNIV --> PORT
    UNIV --> KRONOS
    
    SYN --> PORT
    SYN --> STAB
    
    PORT --> ORDER_PLAN
    PORT --> KRONOS
    
    %% ============ CONNECTIONS: Engines → Storage (outputs) ============
    REGIME --> ENGINE_OUT
    STAB --> ENGINE_OUT
    FRAG --> ENGINE_OUT
    ASSESS --> ENGINE_OUT
    UNIV --> ENGINE_OUT
    PORT --> ENGINE_OUT
    SYN --> ENGINE_OUT
    
    %% ============ CONNECTIONS: Execution Flow ============
    ORDER_PLAN --> BROKER_IF
    BROKER_IF --> LIVE_BROKER
    BROKER_IF --> PAPER_BROKER
    BROKER_IF --> BT_BROKER
    
    LIVE_BROKER --> IBKR
    PAPER_BROKER --> IBKR
    
    BT_BROKER --> TIME_MACHINE
    BT_BROKER --> MKT_SIM
    TIME_MACHINE --> PRICES
    MKT_SIM --> PRICES
    
    LIVE_BROKER --> EXEC_TBL
    PAPER_BROKER --> EXEC_TBL
    BT_BROKER --> EXEC_TBL
    
    %% ============ CONNECTIONS: Orchestration ============
    CAL --> ORCH
    ORCH --> INGEST
    ORCH --> REPR
    ORCH --> ENGINES
    ORCH --> EXEC
    
    %% ============ CONNECTIONS: Meta & Monitoring ============
    ENGINE_OUT --> KRONOS
    DECISIONS --> KRONOS
    EXEC_TBL --> KRONOS
    CONFIGS --> KRONOS
    
    KRONOS --> CONFIGS
    KRONOS --> WEB_API
    
    ENGINE_OUT --> WEB_API
    EXEC_TBL --> WEB_API
    DECISIONS --> WEB_API
    
    WEB_API --> UI
    WEB_API --> KRONOS_CHAT
    
    %% ============ CONNECTIONS: Decision Logging ============
    REGIME -.->|log decisions| DECISIONS
    STAB -.->|log decisions| DECISIONS
    FRAG -.->|log decisions| DECISIONS
    ASSESS -.->|log decisions| DECISIONS
    UNIV -.->|log decisions| DECISIONS
    PORT -.->|log decisions| DECISIONS
    ORDER_PLAN -.->|log orders| EXEC_TBL
    
    %% ============ STYLING ============
    classDef external fill:#2d3748,stroke:#4a5568,stroke-width:2px,color:#fff
    classDef storage fill:#1a365d,stroke:#2c5282,stroke-width:2px,color:#fff
    classDef engine fill:#742a2a,stroke:#9b2c2c,stroke-width:2px,color:#fff
    classDef meta fill:#44337a,stroke:#5a4ba3,stroke-width:2px,color:#fff
    classDef exec fill:#234e52,stroke:#2c7a7b,stroke-width:2px,color:#fff
    
    class EXT,IBKR,MKT_DATA,NEWS_FEED,MACRO_DATA external
    class STORAGE,HIST_DB,RUN_DB,FILES,PRICES,TEXT_DATA,EMBEDDINGS,ENTITIES,PROFILES_TBL,DECISIONS,EXEC_TBL,ENGINE_OUT,CONFIGS storage
    class ENGINES,REGIME,STAB,FRAG,ASSESS,UNIV,PORT,SYN engine
    class META,KRONOS,ORCH,CAL meta
    class EXEC,ORDER_PLAN,BROKER_IF,BROKERS,LIVE_BROKER,PAPER_BROKER,BT_BROKER,BT_INFRA,TIME_MACHINE,MKT_SIM exec
```

## Key Data Flows

### 1. **Live Trading Flow** (LIVE mode)
```
Market Data → Ingestion → historical_db 
→ Encoders → Engines (Regime → Stability → Fragility → Assessment → Universe → Portfolio) 
→ Order Planner → LiveBroker → IBKR Gateway 
→ Fills → runtime_db 
→ Kronos (analyzes outcomes)
```

### 2. **Backtesting Flow** (BACKTEST mode)
```
Historical Data (time-gated by TimeMachine) 
→ Engines (as above) 
→ Order Planner → BacktestBroker → MarketSimulator 
→ Simulated Fills → backtest results 
→ Kronos (evaluates experiment)
```

### 3. **Paper Trading Flow** (PAPER mode)
```
Same as Live but: PaperBroker → IBKR Paper Account (port 4001)
```

### 4. **Decision Logging Flow**
```
Every Engine → logs decision to engine_decisions table 
→ Order execution → fills logged to fills table 
→ After horizon H → decision_outcomes computed 
→ Kronos analyzes: decision + outcome → performance slice by regime/config 
→ proposes config changes
```

### 5. **Orchestration Flow** (Daily Cycle Example: US_EQ)
```
TradingCalendar detects: US_EQ enters POST_CLOSE state 
→ DAG Orchestrator triggers:
  1. us_eq_ingest_T (prices, events)
  2. us_eq_features_T (returns, vol, embeddings)
  3. us_eq_profiles_T (profile updates)
  4. us_eq_engines_T (all engines run)
  5. us_eq_execution_T (orders sent to broker)
→ Next day PRE_OPEN: quality checks run
```

## Component Counts

**Python Packages:** ~15 major packages
- core, data, encoders, profiles, regime, stability, assessment, universe, portfolio, meta, synthetic, monitoring, execution, scripts

**Engines:** 7 core decision engines
- Regime (100), Stability (110), Fragility Alpha (135), Assessment (130), Universe (140), Portfolio & Risk (150), Synthetic Scenarios (170)

**Database Tables:** 37 tables total
- historical_db: 13 tables
- runtime_db: 24 tables

**Specs:** 23+ specification documents (000-210)

**External Integrations:**
- IBKR Gateway/TWS (live + paper)
- Market data providers
- News/text feeds
- Macro data sources

## Code Reuse from v1

**Reusable (with adaptation):**
- Core infra (config, logging, DB connections)
- Data ingestion clients
- Monitoring patterns
- Some execution/broker adapter code

**Reference-only (superseded):**
- All v1 engines (regime, stability, assessment, etc.)
- LLM integration patterns

## Critical Path Dependencies

**Before any engine runs:**
1. historical_db populated with prices, events, text
2. Encoders trained and producing embeddings
3. Profiles built for entities
4. TradingCalendar configured for all markets
5. DAG orchestration operational

**Engine dependency chain:**
```
Regime → Stability → Fragility → Assessment → Universe → Portfolio → Execution
```

**For Kronos to work:**
- All engines logging to engine_decisions
- Fills logging to fills table
- decision_outcomes computed after horizons
- Config versioning in engine_configs

## Modes of Operation

| Mode | Broker | Data Source | Use Case |
|------|--------|-------------|----------|
| LIVE | LiveBroker → IBKR live (7496) | Real-time feeds | Production trading |
| PAPER | PaperBroker → IBKR paper (4001) | Real-time feeds | Strategy dry-run |
| BACKTEST | BacktestBroker → MarketSimulator | historical_db (time-gated) | Strategy validation, Kronos experiments |

## Fail-Safe & Monitoring

**Pre-execution checks:**
- Data quality gates (QC tasks in DAGs)
- Engine decision validation
- Risk limit checks before order submission

**Live monitoring:**
- Real-time pipeline status (per market state)
- Alert system (high-severity for ingestion/execution failures)
- UI showing current regime, stability, portfolio risk

**Kronos oversight:**
- Performance tracking by regime, config, market
- Automatic detection of degraded configs
- Experiment proposals (human-approved before promotion)

## Scale Targets

**Phase 1 (Initial):**
- Universe: S&P 500 (~500 instruments)
- Markets: US_EQ primary, US_FUT secondary
- Horizon: EOD execution
- Infrastructure: Single beefy machine (32 cores, 128GB RAM, 1 GPU optional)

**Phase 2 (Expansion):**
- Universe: US + EU + JP equities (~2000 instruments)
- Markets: US_EQ, EU_EQ, JP_EQ, FX_GLOB
- Horizon: Intraday capability
- Infrastructure: Distributed (multi-node orchestration)

**Phase 3 (Full System):**
- Universe: Global multi-asset (equities, futures, FX, credit)
- Markets: All major regions
- Horizon: Real-time regime/stability monitors
- Infrastructure: Cloud + on-prem hybrid
