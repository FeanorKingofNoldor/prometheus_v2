# Shared Encoder & Joint Embedding Use Cases – Planning Notes

This document lists concrete, high‑value use cases for the v0 encoder and
joint embedding layer. It is intended as a planning aid for future
experiments and engine integrations.

## 1. Text Encoders

### 1.1 `text-fin-general-v1`

- News/macro retrieval:
  - Find historical news similar to a current headline or macro
    narrative.
  - Cluster news by regime, sector, or risk topic for diagnostics.
- Regime/episode context:
  - Build daily NEWS context vectors feeding `REGIME_CONTEXT_V0` and
    `EPISODE_V0` joint spaces.
- Assessment features:
  - Recent text context branch in `ASSESSMENT_CTX_V0` for sentiment/
    narrative conditioning.

### 1.2 `text-profile-v1`

- Profile similarity search:
  - "Find issuers whose qualitative risk profile looks like X".
  - Cluster issuers by business/risk narrative for universe design.
- Joint profiles:
  - Text branch in `PROFILE_CORE_V0` to balance structural numeric
    features.

### 1.3 `text-macro-v1`

- Regime+macro diagnostics:
  - Joint `REGIME_MACRO_V0` context for macro‑driven regime
    interpretation.
  - Compare macro narratives across cycles (e.g. tightening vs easing
    episodes).
- Scenario design:
  - Retrieve historical dates whose macro text context matches a
    candidate scenario description.

## 2. Numeric Encoders

### 2.1 `num-regime-core-v1`

- Regime engine core:
  - Primary numeric branch for regime clustering and state prototypes.
- Joint regime spaces:
  - Numeric branch in `REGIME_CONTEXT_V0` and `REGIME_MACRO_V0`.
- Episode embeddings:
  - Behaviour branch in `EPISODE_V0` to characterise crisis/event
    windows.

### 2.2 `num-stab-core-v1`

- STAB engine core:
  - Instrument‑level stability vectors (vol, drawdown, liquidity, etc.).
- Joint STAB:
  - Main numeric branch in `STAB_FRAGILITY_V0` for entity‑level risk
    context.

### 2.3 `num-profile-core-v1`

- Structural risk factors:
  - Numeric fundamentals/behaviour features per issuer/instrument.
- Joint profiles:
  - One branch of `PROFILE_CORE_V0` alongside regime behaviour and profile
    text.

### 2.4 `num-scenario-core-v1`

- Scenario clustering:
  - Group synthetic/historical scenarios by path shape and cross‑section.
- STAB + scenarios (future):
  - Scenario branch in a scenario‑level STAB joint space for fragility
    analysis.

### 2.5 `num-portfolio-core-v1`

- Portfolio state comparison:
  - Compare current vs historical portfolio risk/exposure profiles.
- Meta/Monitoring (future):
  - Input branch for `joint-portfolio-core-v1` and for config/outcome
    analytics in Meta.

## 3. Joint Spaces – Regimes & Episodes

### 3.1 `REGIME_CONTEXT_V0` / `joint-regime-core-v1`

- Regime labelling & prototypes:
  - Map daily market states into a shared space for clustering and
    qualitative labelling.
- Episode similarity:
  - Input to `find_similar_episodes_to_regime` to answer
    "what historical episodes look like today?".
- Assessment context:
  - Regime branch in `ASSESSMENT_CTX_V0`.

### 3.2 `REGIME_MACRO_V0` / `joint-regime-core-v1`

- Macro narrative alignment:
  - Compare macro‑heavy regimes (policy shifts, crises) across time.
- Scenario selection:
  - Pick historical periods whose macro+numeric joint context matches
    scenario design targets.

### 3.3 `EPISODE_V0` / `joint-episode-core-v1`

- Crisis/event library:
  - Maintain an embedding library of hand‑defined episodes (GFC, taper
    tantrum, COVID crash, etc.).
- Regime‑to‑episode retrieval:
  - Given current `REGIME_CONTEXT_V0`, retrieve most similar episodes for
    stress‑testing and narrative framing.
- Scenario conditioning:
  - Seed Synthetic Scenario Engine with episode‑like paths for fragility
    tests.

## 4. Joint Spaces – Profiles & Stability

### 4.1 `PROFILE_CORE_V0` / `joint-profile-core-v1`

- Cross‑issuer similarity:
  - Find issuers with similar structural + behavioural + text profiles
    for peer analysis.
- Universe design:
  - Identify clusters of profiles to diversify/exclude in sleeve
    construction.
- STAB & Assessment features:
  - Profile context branch in STAB state construction and
    `ASSESSMENT_CTX_V0`.

### 4.2 `STAB_FRAGILITY_V0` / `joint-stab-fragility-v1`

- Stability state atlas:
  - Map instruments into a stability/fragility space as of a date for
    cross‑sectional risk views.
- Fragility modelling:
  - Use as features for Fragility Alpha models and soft‑target classes.
- Scenario‑aware STAB (future):
  - Extend with scenario branch for instrument×scenario fragility scores.

## 5. Joint Spaces – Assessment Context

### 5.1 `ASSESSMENT_CTX_V0` / `joint-assessment-context-v1`

- Expected‑return models:
  - Use `z_assessment` as a compact feature vector for per‑instrument
    Assessment models (trees/MLPs or linear models).
- Regime‑aware diagnostics:
  - Track how Assessment signals move in the joint context space across
    regimes/stability states.
- Simplified feature sharing:
  - Reuse the same context space across multiple Assessment strategies
    and horizons instead of bespoke feature sets per model.

## 6. Joint Spaces – Meta Config+Env

### 6.1 `META_CONFIG_ENV_V0` / `joint-meta-config-env-v1`

- Similar‑config search:
  - Given a backtest run, retrieve past runs with similar config+env+
    outcome patterns for comparison.
- Meta analysis dashboards:
  - Plot experiments in this space to understand which regions of config
    space are robust vs fragile.
- Proposal vetting:
  - When Kronos or a human proposes a new config, locate nearest
    neighbours in this space to:
    - sanity‑check expected behaviour,
    - identify regimes/universes where similar configs failed.

## 7. Joint Spaces – Portfolio (future)

### 7.1 `joint-portfolio-core-v1` (design target)

- Portfolio history retrieval:
  - For a given portfolio state, find historically similar portfolios and
    inspect subsequent performance and risk.
- Monitoring & alerts:
  - Flag when the live portfolio enters a region of the space associated
    with poor outcomes historically.
- Meta linkage:
  - Use portfolio joint embeddings alongside `META_CONFIG_ENV_V0` to
    relate config decisions to realised portfolio states.

## 8. Cross‑Space Use Cases

- Cross‑regime fragility studies:
  - Combine `REGIME_CONTEXT_V0`, `STAB_FRAGILITY_V0`, and scenario/joint
    spaces to study how fragility profiles evolve across regimes.
- Explainability tools:
  - For a given Assessment or Portfolio decision, surface nearest
    neighbours in joint spaces (profiles, regimes, meta) to provide
    qualitative explanations.
- Offline research workflows:
  - Use joint spaces as the "data layer" for notebooks exploring:
    - new regimes and episode definitions,
    - robustness of strategies across scenarios,
    - config optimisation guided by the Meta joint space.

These use cases should guide where to focus future work: training
non‑trivial projection heads, building k‑NN search tools, and wiring
joint spaces into engine DAGs for real‑time decision support.