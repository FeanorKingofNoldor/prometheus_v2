# Joint Embedding / Shared Space – Use Cases
This document captures potential uses of multi-encoder shared embedding spaces in Prometheus v2 for future phases.

## 1. Regime Engine – Numeric + Macro/Text Joint Space
Purpose:
- Represent market regimes as points in a joint space combining numeric windows and macro/text context.

Space and models:
- Joint space in `R^384`.
- Numeric encoder: `num-regime-core-v1` (384-dim).
- Text encoder: `text-macro-v1` (384-dim, same tokenizer family as
  other text encoders).
- Joint model: `joint-regime-core-v1` projecting both branches into the
  shared space.

Encoders:
- NumericWindowEncoder for cross-asset returns, vol, correlations.
- TextEncoder for macro news, policy statements, major news flows.

Use cases:
- Unsupervised discovery of regime clusters in joint space.
- Measuring similarity of current state to past regimes or pre-crisis episodes.
- Conditioning other engines (Assessment, Universe, Stability) on regime embeddings.

## 2. Stability and Black Swan – Fragility Pattern Space
Purpose:
- Represent stability/fragility states and shock scenarios in a common space.

Space and models:
- Joint space in `R^384`.
- Stability numeric encoders: `num-stab-core-v1`.
- Scenario encoder: `num-scenario-core-v1`.
- Optional profile branch: profile embeddings from `joint-profile-core-v1`.
- Joint model: `joint-stab-fragility-v1`.

Encoders:
- Stability encoder over microstructure, liquidity, contagion metrics.
- Scenario encoder over standardized shock vectors or stress paths.
- Optional profile/issuer encoder over structural risk features.

Use cases:
- Cluster high-fragility states to identify typical failure modes.
- Find which entities or portfolios live near historically dangerous regions.
- Measure how similar a new scenario is to past stress episodes.

## 3. Issuer and Country Profiles – Cross-Modal Profile Space
Purpose:
- Represent issuers and countries by combining fundamentals, text, and market behavior.

Space and models:
- Joint space in `R^384`.
- Text encoder: `text-profile-v1`.
- Numeric fundamentals encoder: `num-profile-core-v1`.
- Behavior encoder: `num-regime-core-v1` (or a tuned variant).
- Joint model: `joint-profile-core-v1`.

Encoders:
- Structured fundamentals encoder (ratios, leverage, growth, quality metrics).
- Text encoder for filings, earnings call segments, governance commentary.
- Numeric encoder for medium-horizon return/vol/factor windows.

Use cases:
- Find “profile neighbors” that behaved similarly under past regimes.
- Support Universe and Assessment with robustness/quality context beyond simple ratios.
- Identify clusters of fragile or robust issuers in joint space.

## 4. Event and Episode Embeddings
Purpose:
- Represent crisis and event windows as single objects combining text and numeric signals.

Space and models:
- Joint space in `R^384`.
- Numeric encoder: `num-regime-core-v1` over event windows.
- Text encoder: `text-fin-general-v1` over aggregated event text.
- Joint model: `joint-episode-core-v1`.

Encoders:
- Numeric window encoder over multi-asset returns and vol around events.
- Text encoder over event-related news, policy statements, transcripts.

Use cases:
- Build a library of historical episodes (crises, interventions, dislocations).
- Measure similarity of current conditions to specific past events.
- Drive episode-aware backtests or scenario selection in the Synthetic Scenario Engine.

## 5. Universe Selection – Robustness-Oriented Space
Purpose:
- Bias universe construction toward entities that live in historically robust regions of joint space.

Space and models:
- Joint space in `R^384`.
- Profile embeddings: `joint-profile-core-v1`.
- Stability embeddings: `joint-stab-fragility-v1` or direct `num-stab-core-v1`.

Encoders:
- Profile and stability encoders as above.

Use cases:
- Score candidates by distance to robust clusters vs fragile clusters.
- Regime-conditional universes: choose names that were robust in similar regimes.
- Build exclusion lists based on proximity to known problematic profiles.

## 6. Assessment Context Space
Purpose:
- Provide compact, expressive context vectors as features for expected-return models.

Space and models:
- Joint space in `R^384`.
- Inputs:
  - Profile embedding from `joint-profile-core-v1`.
  - Regime embedding from `joint-regime-core-v1`.
  - Stability embedding from `joint-stab-fragility-v1`.
  - Recent text embedding from `text-fin-general-v1`.
- Joint model: `joint-assessment-context-v1`.

Encoders:
- Joint encoder over profile, regime, stability, and recent text for an instrument.

Use cases:
- Use joint embeddings as inputs to classical models (trees, MLPs) in Assessment.
- Share a common representation across multiple horizons or strategies.
- Reduce feature engineering burden by letting the encoder learn interactions.

## 7. Meta-Orchestrator – Config and Environment Similarity
Purpose:
- Represent “config + environment + outcome summary” points for config search and analytics.

Space and models:
- Joint space in `R^384`.
- Config encoder: `num-config-core-v1`.
- Environment encoder: `num-env-core-v1`.
- Outcome encoder: `num-outcome-core-v1`.
- Joint model: `joint-meta-config-env-v1`.

Encoders:
- Config encoder for numeric and categorical hyperparameters of engines.
- Environment encoder for regime, stability, and universe characteristics.
- Outcome encoder for backtest metrics (Sharpe, drawdown, turnover, etc.).

Use cases:
- Retrieve past configs that worked in similar environments.
- Cluster configs by behavior and robustness rather than raw parameter values.
- Suggest candidate configs by nearest neighbors in this joint space (still validated via backtests).

## 8. Synthetic Scenario Engine – Scenario Coverage Space
Purpose:
- Map synthetic and historical scenarios into one space to reason about coverage and gaps.

Space and models:
- Joint space in `R^384`.
- Scenario encoder: `num-scenario-core-v1`.
- Optional linkage to `joint-episode-core-v1` for episode similarity.

Encoders:
- Scenario encoder over numeric shock patterns and path shapes.
- Optional encoder linking scenarios to episodes or macro text descriptions.

Use cases:
- Ensure scenario libraries cover diverse regions of the space (not all near the same pattern).
- Find real episodes closest to a given synthetic scenario for validation.
- Group scenarios into families for reporting and testing.

## 9. Portfolio-Level Embedding Space
Purpose:
- Represent whole portfolios as points in a space informed by holdings and risk characteristics.

Space and models:
- Joint space in `R^384`.
- Portfolio encoder: `num-portfolio-core-v1`.
- Joint model: `joint-portfolio-core-v1`.

Encoders:
- Portfolio encoder over weights, factor exposures, stability/fragility features.

Use cases:
- Compare current portfolio to past portfolios that experienced large drawdowns or strong performance.
- Support risk dashboards with “distance to historical bad states” measures.
- Provide compact context vectors to Meta-Orchestrator when evaluating config changes.

## Notes and Constraints
- All shared spaces should be built from encoder-style models with numeric outputs; no generative LLMs in the core daily pipeline.
- Training and fine-tuning of joint spaces should be performed offline using logged data and backtests.
- Outputs are primarily features and similarity metrics; all trading decisions remain numeric and backtestable via the existing engines.
