# 100 – Regime Engine Specification

## 1. Purpose

The Regime Engine identifies and tracks **market regimes** over time, globally and per region/market. It provides:
- Regime labels (e.g., `CARRY`, `CRISIS`, `RECOVERY`, `REFLATION`, etc.).
- Continuous regime embeddings representing the current macro/market state.
- Confidence scores and transition information.

Regime information is consumed by:
- Stability & Soft-Target Engine (110).
- Assessment Engine (130) and Fragility Alpha (135).
- Universe Selection (140).
- Portfolio & Risk (150).
- Meta-Orchestrator (160) for performance slicing and config decisions.

---

## 2. Scope and Definitions

### 2.1 Scope

The Regime Engine:
- Runs daily per `as_of_date` (initially at POST_CLOSE for US_EQ, later global view).
- Provides:
  - a **global regime** view and
  - **regional/market-specific regimes** (e.g., US, EU, JP).
- Is designed to support multiple frequencies in future (e.g., weekly/monthly, or intraday monitoring), but initial focus is daily.

### 2.2 Regime

A **regime** is a qualitative descriptor of the joint behavior of markets and macro variables over a time window, such as:
- `CALM_CARRY` – low vol, supportive macro, carry trades perform.
- `RISK_OFF_CRISIS` – high vol, wide spreads, funding stress.
- `RECOVERY` – improving risk sentiment after crisis.
- `STAGFLATION`, `RECESSIONARY`, etc. (to be defined during calibration).

Internally, regimes are derived from **regime embeddings** via clustering and/or classification.

---

## 3. Inputs

### 3.1 Numeric inputs (per region/market)

From `historical_db` and feature builders:
- Cross-asset returns:
  - equities (indices, sectors),
  - rates (yields, curves),
  - credit (spreads),
  - FX (major pairs),
  - commodities (key benchmarks).
- Volatility metrics:
  - realized vol per asset class,
  - implied vol indices (if available).
- Correlation structures:
  - within and across asset classes (from `correlation_panels`).
- Factor returns:
  - value, momentum, carry, quality, size, etc.

These are aggregated into **numeric window features** over horizons (e.g. 1–3 months) via `build_numeric_window_features` / `NumericWindowEncoder`.

### 3.2 Text/macro inputs

- Macro news and policy statements per region:
  - FOMC/ECB/BOJ communications,
  - major macro events (payrolls, CPI, etc.).
- Aggregated text per regime window:
  - e.g., concatenated or summarized macro headlines and policy texts.

Mapped into embeddings via `TextEncoder` and then projected into joint space via `JointEncoder`.

### 3.3 Joint embeddings

For each window and region/market, we construct:

- `numeric_embedding = NumericWindowEncoder(model_id_num).embed_window("MARKET", market_id, as_of_date, window_length_days)`.
- `text_embedding = JointEncoder(model_id_joint).embed_text([...macro texts...])`.

or directly:

- `joint_embedding = JointEncoder(model_id_joint).embed_numeric_windows("MARKET", [market_id], [as_of_date], window_length_days)`
  plus any text joint embeddings.

These embeddings are the primary representations used for regime identification.

---

## 4. Outputs

### 4.1 RegimeState

Conceptual data structure:

```python
from dataclasses import dataclass
from datetime import date
import numpy as np

@dataclass
class RegimeState:
    as_of_date: date
    region: str  # e.g. "GLOBAL", "US", "EU", "JP"
    regime_label: str  # e.g. "CALM_CARRY", "RISK_OFF_CRISIS"
    regime_embedding: np.ndarray  # vector in R^d
    confidence: float  # 0..1
    metadata: dict  # optional diagnostics (cluster id, distances, drivers)
```

### 4.2 History and transitions

The engine provides:
- Time series of `RegimeState` per region.
- Optionally, transition matrices estimated from historical regime sequences.

---

## 5. Core Algorithms

### 5.1 Windowing and embeddings

For each `as_of_date` and region/market:
- Define a **numeric window** [D - W + 1, D] (e.g., W = 63 trading days).
- Build numeric features and joint embeddings as in Section 3.

### 5.2 Unsupervised regime discovery (offline)

Initial regime structure will be discovered offline on historical data:

1. Collect joint embeddings for many windows across time and regions.
2. Run clustering (e.g., Gaussian Mixture Models, k-means, HDBSCAN) on embeddings to find **regime clusters**.
3. Analyze and label clusters using domain knowledge:
   - inspect average vol, spreads, factor returns, macro context.
   - assign human-readable labels (e.g. `CRISIS`, `RECOVERY`, etc.).
4. Store cluster centers and covariances as regime prototypes.

### 5.3 Online regime assignment

At runtime for each `as_of_date` and region:

- Compute current window embedding `z_t`.
- Compute distances/similarities to regime prototypes.
- Assign regime label as the nearest/most probable cluster, with confidence based on distance or cluster posterior.

Optionally refine with supervised classifiers if/when labeled regimes are available.

### 5.4 Global vs regional regimes

- Regional regimes (US, EU, JP, etc.) are computed from region-specific embeddings.
- Global regime can be:
  - a separate clustering of global embeddings, or
  - an aggregation of regional regimes (e.g., majority or weighted composition).

---

## 6. APIs

Module: `prometheus/regime/api.py`

```python
from datetime import date
from typing import List, Dict

class RegimeEngine:
    """Market regime identification and tracking service."""

    def get_regime(
        self,
        as_of_date: date,
        region: str = "GLOBAL",
    ) -> RegimeState:
        """Infer the current regime for a given region and date.

        Args:
            as_of_date: Date for which to infer the regime.
            region: Region identifier (e.g. "GLOBAL", "US", "EU", "JP").

        Returns:
            RegimeState containing label, embedding, and confidence score.
        """

    def get_history(
        self,
        start_date: date,
        end_date: date,
        region: str = "GLOBAL",
    ) -> List[RegimeState]:
        """Return regime history over a date range for a given region."""

    def get_transition_matrix(
        self,
        region: str = "GLOBAL",
    ) -> Dict[str, Dict[str, float]]:
        """Return estimated regime transition probabilities for a region.

        Returns:
            Nested dict mapping from from_regime -> to_regime -> probability.
        """
```

Implementation details (e.g. storage location of historical assignments) are covered in Section 7.

---

## 7. Storage & Integration

### 7.1 Storage of regime assignments

Create a `regimes` table in `historical_db` or `runtime_db`:

**Table:** `regimes`

- `region` (text)
- `as_of_date` (date)
- `regime_label` (text)
- `model_id` (text) – regime model version
- `embedding_vector_ref` (text, nullable)
- `confidence` (numeric)
- `metadata` (jsonb)

PK: (`region`, `as_of_date`, `model_id`).

This allows:
- Fast retrieval of regime history.
- Backtestable reconstruction of regime sequences under a given model version.

### 7.2 Integration points

- **Stability & Soft-Target Engine (110):**
  - Uses regime label/embedding as context for stability/fragility computations.
  - May adjust thresholds by regime type (e.g., more tolerant of volatility in certain regimes).

- **Assessment & Fragility Alpha (130/135):**
  - Use regime embeddings as input features for expected return and fragility models.

- **Universe Engine (140):**
  - Conditions universe composition on regime (e.g., include more defensives in CRISIS).

- **Portfolio & Risk Engine (150):**
  - Adjusts risk budgets and leverage by regime (e.g., lower gross in CRISIS).

- **Meta-Orchestrator (160):**
  - Slices performance/behavior of configs by regime, to see which configs are robust.

---

## 8. Configuration

Module: `prometheus/regime/config.py`

```python
from pydantic import BaseModel

class RegimeConfig(BaseModel):
    window_length_days: int = 63
    joint_model_id: str
    num_clusters: int
    min_regime_duration_days: int
    smoothing_method: str = "none"  # or "hmm", "moving_mode"
    regions: list[str] = ["GLOBAL", "US"]  # initial regions
```

- `window_length_days`: length of lookback window for embeddings.
- `joint_model_id`: which joint encoder to use.
- `num_clusters`: base number of regime clusters (if using k-means/GMM).
- `min_regime_duration_days`: short regimes can be merged/smoothed to avoid noise.

Configs are stored in `engine_configs` with `engine_name="REGIME"`.

---

## 9. Backtesting & Validation

### 9.1 Historical clustering/labeling

- Run regime discovery on a long historical span.
- Validate that:
  - discovered regimes align with known historical episodes (e.g., 2008, 2010–12, 2013 taper tantrum, 2020 COVID, etc.),
  - cluster characteristics (vol, spreads, factor returns) match intuitive regime descriptions.

### 9.2 Stability

- Check that regime labels are **stable to small perturbations**:
  - change window length slightly,
  - sub-sample instruments,
  - verify that regime sequences don’t flip erratically.

- Apply a **minimum duration** rule to avoid over-fragmentation.

### 9.3 Predictive usefulness

- Test whether regime labels/embeddings improve:
  - risk forecasts,
  - drawdown prediction,
  - performance of assessment models vs regime-agnostic baselines.

These validations inform whether the regime structure is useful, not just descriptive.

---

## 10. Orchestration

The Regime Engine’s daily run is orchestrated as part of `M_engines_D` DAGs (see 013):

- For each region/market of interest (initially US, later EU/JP):
  - After ingestion and features (`M_ingest_D`, `M_features_D`) are complete.
  - Runs `run_regime_engine` for that date and region(s).
  - Persists results to `regimes` table.
  - Logs decisions to `engine_decisions` with `engine_name="REGIME"`.

---

This spec is the reference for implementing `prometheus/regime` in Prometheus v2.