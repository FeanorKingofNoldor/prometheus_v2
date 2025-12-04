# 041 – Latent State Spaces & Math

This document specifies the **spaces**, **embeddings**, **attention
mechanics**, and **update equations** for applying the Latent State
Engine (LSE) pattern in Prometheus v2.

It is intended as the technical reference for implementing
IssuerStateEngine, RegimeStateEngine, BookStateEngine, and related
components.

## 1. Notation

- `i` – issuer index.
- `r` – region/market index.
- `b` – book/strategy index.
- `t` – discrete time index (e.g. trading date).
- `h_i(t)` – state vector for entity `i` at time `t`.
- `x_j` – event vector for event `j`.
- `E` – set of events relevant to a given entity/time.

Linear algebra:

- Vectors are column vectors in `R^d`.
- `·` – dot product.
- `‖·‖` – L2 norm.
- `σ(·)` – logistic sigmoid.
- `softmax_k(z_k)` – standard softmax over k.

## 2. State Spaces

We define separate state spaces for different families. Exact dimensions
can be tuned; below are initial recommendations.

### 2.1 Issuer state space `R^d_issuer_state`

- Dimension: `d_issuer_state = 64` (initial), configurable.
- Each issuer `i` has a state vector:

  - `h_i(t) ∈ R^d_issuer_state`.

- Interpretation:

  - Components are not directly interpretable individually; they encode
    a compressed representation of:
    - Price-based features.
    - News/text information.
    - Structural/fundamental signals (later).

### 2.2 Regime state space `R^d_regime_state`

- Dimension: `d_regime_state = 32` or `64`.
- For each region `r` (e.g. US, EU, ASIA) we maintain:

  - `h_r(t) ∈ R^d_regime_state`.

- Encodes macro regime (risk-on/off, liquidity, volatility state, etc.).

### 2.3 Book state space `R^d_book_state`

- Dimension: `d_book_state = 32`.
- For each book/strategy `b` we maintain:

  - `h_b(t) ∈ R^d_book_state`.

- Encodes the performance and risk history of a trading book.

### 2.4 Other spaces (later)

- `R^d_network_state` for graph/contagion nodes.
- `R^d_crossasset_state` for instruments across asset classes.

## 3. Event Spaces & Projections

Events may originate in different modalities and intermediate spaces.
We define projections from these spaces into the relevant state spaces.

### 3.1 Text event space → issuer state space

- Raw text (headline + body excerpt) is encoded by a text encoder:

  - `z_text ∈ R^d_text` (e.g. `d_text = 768` for BERT-like models).

- Projected into issuer state space using a learned linear (or small
  MLP) projection:

  - `x_text = g_text_to_issuer(z_text) ∈ R^d_issuer_state`.

- `g_text_to_issuer` is parameterised as:

  - Linear: `x_text = W_text z_text + b_text`, or
  - MLP: `x_text = W2 φ(W1 z_text + b1) + b2`.

### 3.2 Numeric event space → issuer state space

- Price/volume windows are encoded by an existing numeric encoder:

  - `z_num ∈ R^d_num` (e.g. via convolution or MLP on windows).

- Projected into issuer state space:

  - `x_num = g_num_to_issuer(z_num) ∈ R^d_issuer_state`.

- `g_num_to_issuer` is defined analogously to `g_text_to_issuer`.

### 3.3 Macro event spaces → regime state space

- Macro time series windows, cross-asset returns, and macro text are
  encoded into intermediate spaces and projected:

  - `z_macro_series ∈ R^d_macro_series`.
  - `z_crossasset ∈ R^d_crossasset`.
  - `z_macro_text ∈ R^d_macro_text`.

- Projected into regime state space:

  - `x_macro_series = g_series_to_regime(z_macro_series) ∈ R^d_regime_state`.
  - `x_crossasset = g_crossasset_to_regime(z_crossasset) ∈ R^d_regime_state`.
  - `x_macro_text = g_text_to_regime(z_macro_text) ∈ R^d_regime_state`.

### 3.4 Book event spaces → book state space

- Book events include:

  - PnL, vol, drawdown features.
  - Exposure vectors (factors, regions, sectors).

- Encoded as simple numeric vectors `z_book_event ∈ R^d_book_event`.

- Projected into book state space:

  - `x_book_event = g_event_to_book(z_book_event) ∈ R^d_book_state`.

## 4. Similarity, Retrieval, and Attention

### 4.1 Similarity function

We use cosine similarity or scaled dot-product as the basic similarity
between a state vector and an event vector.

- Cosine similarity:

  - `sim_cos(h, x) = (h · x) / (‖h‖ ‖x‖ + ε)`.

- Dot-product similarity:

  - `sim_dot(h, x) = h · x`.

For simplicity we start with **dot-product similarity** on
`L2`-normalised vectors (i.e. effectively cosine similarity).

### 4.2 kNN retrieval

Given a state vector `h` and an event collection (e.g. news), we
retrieve a **small** set of events `E` via approximate nearest
neighbours (ANN):

1. Filter events by time window `[t − Δt, t]` (e.g. last 1–7 days).
2. Optionally filter by region, language, or hard links (explicit
   ticker/issuer matches).
3. Use ANN index to get top-`k` events `x_j` maximising `sim(h, x_j)`.

We typically choose small `k` (e.g. `k = 10–50`) for efficiency.

### 4.3 Attention weights

For a given entity state `h(t)` and retrieved events `{x_j}`:

1. Compute raw scores:

   - `s_j = sim(h(t), x_j)`.

2. Compute attention weights via softmax:

   - `α_j = exp(s_j) / Σ_k exp(s_k)`.

3. Optional: mask out events with `s_j` below some threshold
   (`s_j < s_min`), then renormalise.

### 4.4 Aggregated message

The aggregated message vector for an entity at time `t` is:

- `m(t) = Σ_j α_j x_j`.

Depending on the use case, we may split by polarity or type (e.g.
positive vs negative news, macro vs idiosyncratic), but the core
aggregation remains the same.

## 5. State Update Equations

We specify two update families: a **simple gated EMA** and a **GRU-like
update**. Implementations should be modular, with the choice controlled
by configuration.

### 5.1 Simple gated EMA update

Given state `h(t)` and message `m(t)`:

1. Compute a gating scalar or vector:

   - Scalar gate:
     - `g = σ(w_g^T [h(t); m(t)] + b_g)`.
   - Vector gate:
     - `g = σ(W_g [h(t); m(t)] + b_g)` with `g ∈ (0, 1)^d`.

2. Update state:

   - `h(t+1) = (1 − g) ⊙ h(t) + g ⊙ m(t)`.

Where `⊙` denotes element-wise multiplication.

This is analogous to an exponential moving average with a learned,
content-dependent step size.

### 5.2 GRU-like update

For richer dynamics we can use a GRU-style update:

1. Concatenate state and message: `u = [h(t); m(t)]`.

2. Compute gates:

   - Reset gate:
     - `r = σ(W_r u + b_r)`.
   - Update gate:
     - `z = σ(W_z u + b_z)`.

3. Candidate state:

   - `h_tilde = φ(W_h [r ⊙ h(t); m(t)] + b_h)`,
   - where `φ` is a nonlinearity (e.g. `tanh` or `ReLU` + layer norm).

4. Final update:

   - `h(t+1) = (1 − z) ⊙ h(t) + z ⊙ h_tilde`.

This allows the model to selectively overwrite parts of the state based
on the incoming message.

### 5.3 Initialisation

At the first time step `t0` for an entity, we can initialise `h(t0)` as:

- Zero vector: `h(t0) = 0`.
- Or projection of a static embedding (e.g. current profile embedding):

  - `h(t0) = W_init e_profile`.

The latter is generally preferred so that the initial state already
reflects structural information.

## 6. Storage Schema Sketch

Exact migrations will be added as needed. At a high level:

### 6.1 Issuer state embeddings

Runtime or historical DB (depending on use case):

- `issuer_state_embeddings`:
  - `issuer_id` (string, FK to `issuers`).
  - `as_of_date` (date).
  - `encoder_version` (string).
  - `state_vector` (BYTEA, float32[d_issuer_state]).
  - `metadata` (JSONB).

Composite PK/unique index: `(issuer_id, as_of_date, encoder_version)`.

### 6.2 News articles

Historical DB:

- `news_articles`:
  - `article_id` (string / bigserial).
  - `ts` (timestamptz).
  - `trade_date` (date, for TimeMachine gating).
  - `source`, `region`, `language`.
  - `headline`, `body_excerpt`.
  - `tickers` (array) / `issuer_ids` (array), nullable.
  - `metadata` (JSONB).

- `news_article_embeddings`:
  - `article_id`.
  - `trade_date`.
  - `encoder_version`.
  - `vector` (BYTEA, float32[d_text] or projected directly to
    `d_issuer_state`).
  - `vector_space` (enum: `TEXT_ISSUER`, `TEXT_REGIME`, etc.).
  - `metadata`.

### 6.3 Regime, book, and other state tables

Analogous tables can be defined for regime and book states:

- `regime_state_embeddings(region, as_of_date, encoder_version, vector, metadata)`.
- `book_state_embeddings(book_id, as_of_date, encoder_version, vector, metadata)`.

## 7. Pseudocode for IssuerStateEngine

A high-level pseudocode outline for a single-step issuer state update:

```python path=null start=null
def update_issuer_states(as_of_date: date, config: IssuerStateConfig) -> None:
    # 1. Load previous states h_i(t)
    states = load_h_issuer_previous(as_of_date, config)

    # 2. Load or encode new events (e.g. news)
    events = load_news_events(as_of_date, config)
    event_embeddings = ensure_news_embeddings(events, config.encoder_version)

    # 3. Build or open ANN index over event embeddings
    index = build_or_open_event_index(event_embeddings)

    updated_states = {}

    for issuer_id, h_t in states.items():
        # 4. Retrieve candidate events (hard links + ANN)
        hard_events = events_linked_to_issuer(issuer_id, as_of_date)
        ann_events = index.query(h_t, k=config.k_neighbors)
        candidate_events = merge_and_deduplicate(hard_events, ann_events)

        if not candidate_events:
            # Optionally carry forward state unchanged
            updated_states[issuer_id] = h_t
            continue

        x_list = [e.vector for e in candidate_events]

        # 5. Compute attention weights
        scores = [similarity(h_t, x) for x in x_list]
        alphas = softmax(scores)

        # 6. Aggregate message
        m_t = sum(alpha * x for alpha, x in zip(alphas, x_list))

        # 7. Update state
        h_tp1 = update_rule(h_t, m_t, config)
        updated_states[issuer_id] = h_tp1

    # 8. Persist updated states for as_of_date
    save_h_issuer(as_of_date, updated_states, config.encoder_version)
```

This structure generalises to `RegimeStateEngine` and `BookStateEngine`
by changing the entity set, event sources, and projection functions.

## 8. Build on Current Code or Start from Scratch?

The equations and spaces above are designed to **extend** the existing
Prometheus v2 architecture, not replace it.

- Existing engines (Regime, Profiles v1, STAB v1, Universe v1) already
  provide clean separation between:
  - Data access.
  - Feature building.
  - Model/engine logic.
  - Persistence.
- The LSE pattern simply adds new:
  - State tables (`*_state_embeddings`).
  - Encoders/projections for events.
  - State engines (`IssuerStateEngine`, `RegimeStateEngine`,
    `BookStateEngine`).

We **should not** start from scratch:

- Doing so would duplicate working infra without changing the
  mathematical core.
- The current codebase provides exactly the hooks LSE needs:
  - Profiles and STAB are natural early consumers.
  - Universe and later Assessment/Meta engines can adopt state-based
    features incrementally.

Instead, we implement LSE **on top** of the existing project, using
iterations and backtests to refine encoders, update rules, and how
strongly each engine leans on these state vectors.
