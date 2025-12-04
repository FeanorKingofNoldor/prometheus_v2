# Pattern Discovery Principles in Prometheus v2

This document summarizes how Prometheus v2 should discover and use patterns in large historical datasets (e.g. full US equity tape 1997–2025), especially when we do not start with a precise hypothesis.

## 1. Goals

- Find structure in markets without overfitting to anecdotes.
- Separate **representation learning** (encoders) from **pattern discovery** (clustering/factors/anomalies) and **trading decisions** (Assessment/Universe/Portfolio).
- Make discovered patterns reusable by other engines via stable interfaces (regime labels, profile traits, stability components, etc.).

## 2. Inputs and Representations

We never run pattern discovery directly on raw prices or text. Instead, we:

- Build per-(instrument, date) features over windows (returns, vol, drawdowns, liquidity, simple ratios).
- Use encoders to map these features into dense vectors:
  - `numeric_window_embedding(instrument, window)`.
  - `profile_embedding(issuer, as_of_date)`.
  - `joint_embedding` for aligned text+numeric windows where available.
- Treat the resulting vectors as points in high-dimensional state spaces:
  - Cross-sectional: many instruments on a single date.
  - Temporal: many dates for a single instrument, or overlapping windows over time.

These state spaces are the substrate for both regime detection and issuer-style clustering.

## 3. Unsupervised Pattern Discovery Methods

Prometheus v2 should use a small set of standard unsupervised tools on these embeddings:

### 3.1 Clustering

- Cluster **time windows** of market-level embeddings to discover regimes.
- Cluster **instruments/issuers** on profile/behavior embeddings to discover styles or latent sectors.
- Clustering outputs:
  - Discrete labels (e.g. regime IDs, style clusters).
  - Cluster centroids for use in similarity queries and distance-based features.

### 3.2 Dimensionality Reduction and Factors

- Apply PCA / autoencoders / NMF to cross-sectional return panels and embeddings.
- Interpret leading components as **latent factors** (e.g. market, value/momentum-like, quality, carry).
- Expose factor loadings and time-series of factor returns as explicit inputs to Assessment and Portfolio engines.

### 3.3 Anomaly and Outlier Detection

- Learn a "normal" manifold of behavior (e.g. via autoencoders or density models) and flag points with:
  - High reconstruction error, or
  - Low likelihood / large distance from cluster centers.
- Use these anomalies to:
  - Identify candidate crisis episodes and microstructural accidents.
  - Provide features to Stability/Black Swan engines ("this name/state is unlike anything normal").

### 3.4 Temporal Motifs and Regime Transitions

- On time-series of discovered regime/style labels, estimate transition matrices and dwell-time distributions.
- Identify common transition paths (e.g. CARRY → STRESS → CRISIS → RECOVERY) and typical horizons.
- Use these as priors in Regime Engine and as scenario generators in Synthetic Scenario Engine.

## 4. Guardrails Against Noise

To avoid overfitting and spurious patterns, we enforce:

- **Time-based splits:** discover structure on an older period, validate on newer periods.
- **Stability checks:** clusters/factors/regimes discovered on one period should reappear with similar shape and behavior on held-out data.
- **Economic sanity:** patterns that completely contradict basic risk/return intuition require extra skepticism or explicit documentation.
- **Scale awareness:** prefer coarse, large-scale patterns that survive many instruments and years over hyper-specific micro-patterns.

Any pattern that does not pass basic stability and intuition checks may still be logged for research but should not feed live trading logic.

## 5. Integration into Engines

Discovered patterns become first-class inputs to other engines via typed interfaces:

- **Regime Engine:**
  - Uses clustering/dim-reduction on market embeddings to define regime labels and embeddings.
  - Exposes `RegimeState(as_of_date)` with label, embedding, and confidence.
- **Profiles:**
  - Attach style/behavior cluster IDs and factor loadings to `ProfileSnapshot` as additional traits.
- **Stability and Black Swan Engines:**
  - Use anomaly scores and distances to crisis-like clusters as features for stability/fragility measures.
- **Assessment Engine:**
  - Consume regime embeddings, style traits, and stability vectors as part of `(p, r, s, ...)` when predicting forward returns.
- **Universe Engine:**
  - Bias universe construction toward issuers and styles that have shown robust performance across regimes and synthetic scenarios.

By routing unsupervised discoveries through these engines rather than directly into execution logic, Prometheus keeps a clean separation between "this looks like a pattern" and "this is a tradable edge".
