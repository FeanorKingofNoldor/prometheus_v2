# 030 – Encoders and Embeddings Specification

## 1. Purpose

Define the encoder layer for Prometheus v2:
- Text encoders for unstructured text (news, filings, transcripts, macro).
- Numeric time-series encoders for windows of market and factor data.
- Joint text+numeric embedding space for regimes/episodes.
- Public APIs and model registry hooks.

Encoders are **representation** components only; they do not make trading decisions.

---

## 2. Text Encoders

### 2.1 Goals

- Convert text documents into dense vectors that capture semantic meaning relevant to:
  - issuer profiles,
  - macro regimes,
  - event similarity,
  - retrieval and clustering.
- Provide stable, versioned embeddings for use by Profiles, Regime, Assessment, Meta, etc.

### 2.2 Base models

- Use encoder-only transformer models (BERT/derivatives, sentence-transformers) fine-tuned for:
  - general semantic similarity, and
  - finance/macroeconomic subdomains where needed.

For v0 of Prometheus v2 we standardise on:
- **Embedding dimension** `d = 384` for text encoders.
- A small, efficient encoder-only transformer (MiniLM/sentence-transformer
  class) as the base model family.

We maintain multiple `model_id`s, e.g.:
- `"text-fin-general-v1"` – general financial text encoder, 384-dim,
  mean-pooled, L2-normalised embeddings for news/macro/corporate text.
- `"text-profile-v1"` – 384-dim encoder initialised from the same base as
  `text-fin-general-v1`, with optional future fine-tuning on filings,
  earnings call transcripts, and profile narratives.
- `"text-macro-v1"` – 384-dim encoder for macro policy/news text, sharing
  the same tokenizer and base architecture as the other text models.

### 2.3 API

Module: `prometheus/encoders/text_encoder.py`

```python
from typing import List
import numpy as np

class TextEncoder:
    """Service for embedding text documents.

    TextEncoder instances are stateless wrappers around underlying models.
    Model selection is done via model_id, which is resolved in the model registry.
    """

    def __init__(self, model_id: str):
        """Initialize a text encoder.

        Args:
            model_id: Identifier of the underlying encoder model.
        """

    def embed_batch(self, docs: List[str]) -> np.ndarray:
        """Embed a batch of text documents.

        Args:
            docs: List of raw text documents.

        Returns:
            2D array of shape (batch_size, embedding_dim) with L2-normalized embeddings.
        """
```

Guidelines:
- All embeddings returned are L2-normalized vectors in `R^d`.
- `model_id` is logged with embeddings and stored in `text_embeddings` table when persisted.

### 2.4 Integration with Data Model

- When embeddings are persisted:
  - Insert into `historical_db.text_embeddings` with `source_type`, `source_id`, `model_id`, and `vector` or `vector_ref`.
- Engines that need embeddings should:
  - Either compute on the fly via `TextEncoder`, or
  - Load precomputed ones via data access layer if available.

---

## 3. Numeric Time-Series Encoders

### 3.1 Goals

- Convert windows of numeric market data and factors into fixed-length feature vectors suitable for:
  - regime detection,
  - stability analysis,
  - assessment models,
  - joint embedding with text.

### 3.2 Window feature construction

Module: `prometheus/encoders/numeric_features.py`

Key function:

```python
import numpy as np
from datetime import date

def build_numeric_window_features(
    entity_type: str,
    entity_id: str,
    as_of_date: date,
    window_length_days: int,
) -> np.ndarray:
    """Build engineered numeric features for an entity window.

    Args:
        entity_type: One of {"INSTRUMENT", "ISSUER", "SECTOR", "MARKET"}.
        entity_id: Identifier matching the entity_type.
        as_of_date: Last date in the window (inclusive).
        window_length_days: Number of trading days to include.

    Returns:
        1D feature vector for the numeric window, including returns, vol, factor
        exposures, and other engineered statistics.
    """
```

Responsibilities:
- Pull data from `historical_db`:
  - `prices_daily`, `returns_daily`, `factors_daily`, `instrument_factors_daily`, `volatility_daily`.
- Aggregate into features:
  - time series of returns,
  - realized vol,
  - drawdowns,
  - rolling correlations vs benchmarks,
  - factor exposures and factor returns.

Exact feature set is specified in engine-level specs (e.g., Regime, Stability, Assessment) but constructed through this shared function or family of functions.

### 3.3 Numeric encoders

For numeric encoders we also fix the default embedding dimension to
`d = 384` so that text, numeric, and joint spaces are compatible by
construction. Concrete numeric encoder `model_id`s include:

- `"num-regime-core-v1"` – numeric window encoder used by the Regime
  Engine for cross-asset return/vol/correlation windows.
- `"num-stab-core-v1"` – numeric window encoder for Stability/STAB
  features (liquidity, volatility, drawdowns, etc.).
- `"num-profile-core-v1"` – numeric encoder for profile-related
  fundamentals windows.
- `"num-scenario-core-v1"` – numeric encoder for synthetic/historical
  scenario shock patterns.
- `"num-portfolio-core-v1"` – encoder for portfolio-level feature
  vectors (weights, factor exposures, risk metrics).

Exact architectures can evolve (linear/MLP/transformer), but all expose a
consistent 384-dim interface.

Module: `prometheus/encoders/numeric_encoder.py`

```python
class NumericWindowEncoder:
    """Encodes numeric windows into dense embeddings."""

    def __init__(self, model_id: str):
        """Initialize a numeric window encoder.

        Args:
            model_id: Identifier of the underlying encoder model.
        """

    def embed_window(
        self,
        entity_type: str,
        entity_id: str,
        as_of_date: date,
        window_length_days: int,
    ) -> np.ndarray:
        """Encode a numeric window into an embedding.

        This function internally calls `build_numeric_window_features` and then
        applies a learned mapping to R^d.
        """
```

`model_id` here points to an entry in `models` with `type = "NUMERIC_ENCODER"`.

### 3.4 Integration with Data Model

When embeddings are persisted, they are stored in `numeric_window_embeddings` with:
- `entity_type`, `entity_id`, `as_of_date`, `window_spec`, `model_id`, and `vector`/`vector_ref`.

---

## 4. Joint Multi-Entity Embedding Space

Joint spaces are also defined in `R^384` and are built on top of the text
and numeric encoders above using small projection heads. Representative
`model_id`s include:

- `"joint-regime-core-v1"` – shared space for regime numeric windows and
  macro/news text.
- `"joint-stab-fragility-v1"` – shared space for stability/fragility
  states, entities, and scenarios.
- `"joint-profile-core-v1"` – cross-modal issuer/country profile space
  combining fundamentals, behavior, and text.
- `"joint-episode-core-v1"` – embeddings for crisis/event windows.
- `"joint-assessment-context-v1"` – compact context vectors for
  Assessment (profile + regime + stability + recent text).
- `"joint-meta-config-env-v1"` – config+environment+outcome space for
  Meta-Orchestrator analysis.
- `"joint-portfolio-core-v1"` – portfolio-level embedding space for
  comparing current vs historical portfolio states.

### 4.1 Goals

Extend the joint embedding idea to a **multi-entity shared space** for:
- Sovereigns,
- Banks and major financial institutions,
- Corporates (issuers),
- Chokepoints (critical infrastructure, key indices, clearing houses),
- Optionally, influential people (as text-centric entities) via their statements and actions.

The space should:
- Map text and numeric windows into a shared representation where:
  - text describing an event/regime/crisis is close to numeric windows & entities exhibiting it,
  - entities that historically behaved similarly under stress are near each other,
- Provide richer context for:
  - Regime & Stability engines,
  - Fragility Alpha,
  - Synthetic Scenario Engine,
  - Kronos analytics.

Embeddings here are **representations**, not crisis predictions; downstream engines will learn how (and whether) to use them.

### 4.2 Training data

Positive pairs `(text_i, numeric_window_i)` are constructed as:
- Same `issuer_id` / `sovereign_id` / `entity_id` and **aligned time window**, e.g.:
  - news about a bank or sovereign at date D ↔ numeric window [D-5, D+5] for that entity.
- Same `country` + macro event window, e.g.:
  - FOMC/ECB statement ↔ US/EU rates/FX window around the event.
- Regime/episode windows with aggregated text vs numeric features for markets/sectors.

Negative pairs are formed by mismatched (text, numeric_window) from different entities or time periods.

We may optionally incorporate simple supervision (e.g., default/crisis labels) only as **auxiliary tasks** to shape the space, not as a direct "crisis classifier".

### 4.3 Architecture and loss

- Use two encoders:
  - `f_text_joint(text) -> R^d` – built on top of TextEncoder, optionally with a small projection head.
  - `f_num_joint(window_features) -> R^d` – built on top of NumericWindowEncoder, with its own projection.

Loss: CLIP-style contrastive infoNCE loss over minibatches:

```text
L = L_text_to_num + L_num_to_text

Where L_text_to_num encourages matching text→numeric pairs to have
high dot-product similarity vs others in the batch, and vice versa.
```

The same joint space is used across entity types; entity type can be provided as an additional input feature.

### 4.4 Joint embedding API

Module: `prometheus/encoders/joint_encoder.py`

```python
class JointEncoder:
    """Maps text and numeric windows into a shared multi-entity embedding space."""

    def __init__(self, model_id: str):
        """Initialize a joint encoder.

        Args:
            model_id: Identifier of the joint embedding model.
        """

    def embed_text(self, docs: List[str]) -> np.ndarray:
        """Embed a batch of text documents into joint space."""

    def embed_numeric_windows(
        self,
        entity_type: str,
        entity_ids: List[str],
        as_of_dates: List[date],
        window_length_days: int,
    ) -> np.ndarray:
        """Embed a batch of numeric windows into joint space."""
```

### 4.5 Storage

- Persist joint embeddings used for regimes/episodes/entities into `joint_embeddings` with `joint_type`, `entity_scope`, `entity_type`, `entity_id`, `as_of_date`, `model_id`, `vector`.

---

## 5. Model Registry Hooks

### 4.1 Goals

- Map text and numeric windows into a **shared space** where:
  - text describing an event/regime is close to numeric windows exhibiting it,
  - numeric episodes can retrieve relevant text (news, macro narratives),
  - used by Regime Engine, Stability/Soft-Target Engine, Fragility Alpha, Meta.

### 4.2 Training data

Positive pairs `(text_i, numeric_window_i)` are constructed as:
- Same `issuer_id` and **aligned time window**, e.g.:
  - news about company X at date D ↔ numeric window [D-5, D+5] for X.
- Same `country` + macro event window, e.g.:
  - FOMC statement ↔ US rates/FX window around the event.
- Regime/episode windows with aggregated text vs numeric features.

Negative pairs are formed by mismatched (text, numeric_window) from different entities or time periods.

### 4.3 Architecture and loss

- Use two encoders:
  - `f_text_joint(text) -> R^d` – built on top of TextEncoder, optionally with a small projection head.
  - `f_num_joint(window_features) -> R^d` – built on top of NumericWindowEncoder, with its own projection.

Loss: CLIP-style contrastive infoNCE loss over minibatches:

```text
L = L_text_to_num + L_num_to_text

Where L_text_to_num encourages matching text→numeric pairs to have
high dot-product similarity vs others in the batch, and vice versa.
```

### 4.4 Joint embedding API

Module: `prometheus/encoders/joint_encoder.py`

```python
class JointEncoder:
    """Maps text and numeric windows into a shared embedding space."""

    def __init__(self, model_id: str):
        """Initialize a joint encoder.

        Args:
            model_id: Identifier of the joint embedding model.
        """

    def embed_text(self, docs: List[str]) -> np.ndarray:
        """Embed a batch of text documents into joint space."""

    def embed_numeric_windows(
        self,
        entity_type: str,
        entity_ids: List[str],
        as_of_dates: List[date],
        window_length_days: int,
    ) -> np.ndarray:
        """Embed a batch of numeric windows into joint space."""
```

### 4.5 Storage

- Persist joint embeddings used for regimes/episodes into `joint_embeddings` with `joint_type`, `entity_scope`, `as_of_date`, `model_id`, `vector`.

---

## 5. Model Registry Hooks

Encoders depend on a model registry entry in `runtime_db.models`:

- `model_id`: unique string.
- `engine_name`: `ENCODERS` or specific engine if fine-tuned.
- `type`: `TEXT_ENCODER`, `NUMERIC_ENCODER`, `JOINT_ENCODER`.
- `artifact_ref`: path/URI to model weights.
- `training_data_spec`: JSON describing training corpus and sampling.
- `metrics`: evaluation metrics (e.g., retrieval accuracy, clustering quality).

A helper in `prometheus/core/models.py` will:
- Resolve `model_id` → artifact.
- Instantiate the correct encoder class.

---

## 6. Logging & Backtestability

- All encoder APIs used inside engines should:
  - Log `model_id`, `as_of_date`, `entity_id`/`source_id` as part of decision context.
  - Where possible, persist embeddings with clear model/version tags.

- For backtests:
  - Encoders must be deterministic given the same `model_id` and inputs.
  - If models are updated, `model_id` changes; older decisions always refer to the old `model_id`.

This spec defines the common representation layer. Engine specs (100–170) will specify which encoders and models they use, and how they interpret embeddings for their tasks.