# Prometheus v2 – System Overview

High-level architecture and dataflow map for Prometheus v2.

## 1. Top-Level Dataflow

```mermaid
graph LR
    %% Groups / subgraphs
    subgraph EXTERNAL["External World"]
        MKT["Market & Macro Data Providers"]
        NEWS["News / Filings / Transcripts"]
        ALT["Alt-Data / Execution Feeds"]
    end

    subgraph STORAGE["Data Warehouse (DB and Files)"]
        DB_HIST["historical_db - Postgres"]
        DB_RUNTIME["runtime_db - Postgres"]
        FILES["Parquet / Blob Storage"]
    end

    subgraph ENCODERS["Representation Layer"]
        ENC_TEXT["Text Encoders (030)"]
        ENC_NUM["Numeric Window Encoders (030)"]
        ENC_JOINT["Joint Multi-Entity Encoder (030)"]
        PROFILES["Profiles Service (035)"]
    end

    subgraph ENGINES["Core Engines"]
        REGIME["Regime Engine (100)"]
        STAB["Stability & Soft-Target (110)"]
        FRAG["Fragility Alpha (135)"]
        ASSESS["Assessment Engine (130)"]
        UNIV["Universe Engine (140)"]
        PORT["Portfolio & Risk Engine (150)"]
        SYN["Synthetic Scenario Engine (170)"]
    end

    subgraph META["Meta & Monitoring"]
        KRONOS["Meta-Orchestrator (Kronos v2, 160)"]
        MON["Monitoring & UI (200)"]
    end

    subgraph ORCH["Orchestration"]
        CAL["Calendars & Schedules (012)"]
        DAG["DAG Orchestrator (013)"]
    end

    EXTERNAL -->|Ingestion Jobs| DB_HIST
    EXTERNAL -->|Execution / Fills| DB_RUNTIME
    EXTERNAL -->|Raw Files| FILES

    DB_HIST --> ENC_TEXT
    DB_HIST --> ENC_NUM
    DB_HIST --> PROFILES

    ENC_TEXT --> ENC_JOINT
    ENC_NUM --> ENC_JOINT
    PROFILES --> ENC_JOINT

    ENC_JOINT --> REGIME
    ENC_JOINT --> STAB
    ENC_JOINT --> ASSESS

    DB_HIST --> REGIME
    DB_HIST --> STAB
    DB_HIST --> SYN

    REGIME --> ASSESS
    STAB --> FRAG
    STAB --> ASSESS
    FRAG --> ASSESS

    ASSESS --> UNIV
    UNIV --> PORT
    SYN --> PORT

    PORT --> DB_RUNTIME
    PORT --> KRONOS

    DB_RUNTIME --> KRONOS
    DB_RUNTIME --> MON

    REGIME --> KRONOS
    STAB --> KRONOS
    ASSESS --> KRONOS
    UNIV --> KRONOS
    PORT --> KRONOS

    KRONOS -->|Config Experiments| DB_RUNTIME
    KRONOS --> MON

    CAL --> DAG
    DAG -->|Run| EXTERNAL
    DAG -->|Run| ENGINES
    DAG -->|Run| ENCODERS
    DAG -->|Run| SYN
    DAG -->|Run| KRONOS
```

This diagram is a bird’s-eye view:
- **External**: data providers, news, execution.
- **Storage**: historical/runtime DBs plus file stores.
- **Encoders**: text/numeric/joint, and profile service.
- **Engines**: regime, stability & soft-target, fragility alpha, assessment, universe, portfolio & risk, synthetic scenarios.
- **Meta**: Kronos and monitoring/UI.
- **Orchestration**: calendars and DAG runner that triggers everything.

The more detailed engine-to-engine flows live in `20_engines.md`.