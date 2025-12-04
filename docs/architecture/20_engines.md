# Prometheus v2 – Engine Dataflows

This document zooms into how the core engines interact and what they read/write.

## 1. Engine Interaction Overview

```mermaid
graph TD
    %% Data and representations
    subgraph DATA["Data & Representations"]
        DB_HIST["historical_db"]
        DB_RUNTIME["runtime_db"]
        ENC_JOINT["Joint Encoders (030)"]
        PROFILES["Profiles (035)"]
    end

    %% Engines
    subgraph E_REGIME["Regime Engine (100)"]
        REGIME
    end

    subgraph E_STAB["Stability & Soft-Target (110)"]
        STAB
    end

    subgraph E_FRAG["Fragility Alpha (135)"]
        FRAG
    end

    subgraph E_ASSESS["Assessment Engine (130)"]
        ASSESS
    end

    subgraph E_UNIV["Universe Engine (140)"]
        UNIV
    end

    subgraph E_PORT["Portfolio & Risk (150)"]
        PORT
    end

    subgraph E_SYN["Synthetic Scenario Engine (170)"]
        SYN
    end

    subgraph META["Meta-Orchestrator (160)"]
        KRONOS
    end

    %% Data sources for engines
    DB_HIST --> REGIME
    DB_HIST --> STAB
    DB_HIST --> ASSESS
    DB_HIST --> SYN

    ENC_JOINT --> REGIME
    ENC_JOINT --> STAB
    ENC_JOINT --> ASSESS

    PROFILES --> ASSESS
    PROFILES --> STAB

    %% Engine outputs to DB
    REGIME -->|regimes table| DB_HIST
    STAB -->|stability_vectors, soft_target_classes| DB_HIST
    FRAG -->|fragility_signals| DB_HIST
    ASSESS -->|instrument_scores| DB_HIST
    UNIV -->|universes| DB_HIST
    PORT -->|target_portfolios, risk_reports| DB_RUNTIME
    SYN -->|scenario_sets, scenario_paths| DB_HIST

    %% Engine-to-engine dependencies
    REGIME -->|"RegimeState"| STAB
    REGIME -->|"RegimeState"| ASSESS

    STAB -->|"StabilityVector, SoftTargetClass"| FRAG
    STAB -->|"StabilityVector/SoftTargetClass"| ASSESS

    FRAG -->|"SoftTargetScore, FragilityAlpha"| ASSESS

    ASSESS -->|"InstrumentScores"| UNIV

    UNIV -->|"EffectiveUniverse"| PORT

    SYN -->|"ScenarioSets"| PORT

    %% Meta-Orchestrator inputs
    REGIME -->|engine_decisions| KRONOS
    STAB -->|engine_decisions| KRONOS
    FRAG -->|engine_decisions| KRONOS
    ASSESS -->|engine_decisions| KRONOS
    UNIV -->|engine_decisions| KRONOS
    PORT -->|engine_decisions, executed_actions, decision_outcomes| KRONOS
    SYN -->|experiment_scenarios| KRONOS

    DB_RUNTIME -->|decision_outcomes, configs| KRONOS
```

## 2. Engine Roles (Summary)

- **Regime Engine (100)**
  - Reads: historical DB, joint embeddings.
  - Writes: `regimes` table.
  - Feeds: Stability, Assessment, Kronos.

- **Stability & Soft-Target Engine (110)**
  - Reads: historical DB, RegimeState, Profiles, joint embeddings.
  - Writes: `stability_vectors`, `fragility_measures`, `soft_target_classes`.
  - Feeds: Fragility Alpha, Assessment, Kronos.

- **Fragility Alpha (135)**
  - Reads: Stability outputs, Profiles, Black Swan scenarios (via Synthetic).
  - Writes: `fragility_signals` / `soft_target_scores`.
  - Feeds: Assessment, Kronos.

- **Assessment Engine (130)**
  - Reads: Regime, Stability, Fragility, Profiles, encoders, market/fundamental data.
  - Writes: `instrument_scores`.
  - Feeds: Universe, Portfolio, Kronos.

- **Universe Engine (140)**
  - Reads: Assessment scores, Stability/Profiles, risk/constraint config.
  - Writes: `universes`.
  - Feeds: Portfolio & Risk, Kronos.

- **Portfolio & Risk Engine (150)**
  - Reads: universes, instrument scores, risk models, scenarios, constraints.
  - Writes: `target_portfolios`, `portfolio_risk_reports`, execution orders.
  - Feeds: execution/external world, Kronos.

- **Synthetic Scenario Engine (170)**
  - Reads: historical returns, factor models, regimes, crisis templates.
  - Writes: `scenario_sets`, `scenario_paths`.
  - Feeds: Portfolio & Risk, Meta-Orchestrator, Stability/Fragility testing.

- **Meta-Orchestrator (160)**
  - Reads: decision logs (`engine_decisions`), executed actions, outcomes, configs, scenario risk.
  - Writes: config proposals, experiments, experiment results.
  - Feeds: humans (via UI), backtest schedulers, engines via updated configs.

These diagrams are intended to be your “wiring diagram” for engine interactions. The city-map you draw later can sit on top of this as a more visual metaphor.