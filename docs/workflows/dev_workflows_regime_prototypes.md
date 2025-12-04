# Dev workflow: numeric regime prototypes from embeddings

This document describes how to compute **numeric regime prototypes**
(e.g. NEUTRAL, CRISIS) from stored regime embeddings in the `regimes`
table and how to use them to initialise `NumericRegimeModel`.

The goal is to tighten the semantics of `NumericRegimeModel` by using
cluster centres derived from real data instead of purely synthetic
centres.

## 1. Prerequisites

- Regime Engine has been run for the desired `region` over at least two
  distinct market environments, so that `runtime_db.regimes` contains
  `regime_embedding` rows for those periods.
- The numeric encoder used by the Regime Engine is
  `num-regime-core-v1` (384-dim), so all embeddings live in `R^384`.

## 2. Compute regime prototypes with CLI

Use the `compute_regime_prototypes` script to derive mean embeddings for
chosen calibration windows.

Example: calibrate NEUTRAL on a calm year and CRISIS on a stress period
for region `US`:

```bash
python -m prometheus.scripts.compute_regime_prototypes \
  --region US \
  --neutral-start 2018-01-01 \
  --neutral-end   2018-12-31 \
  --crisis-start  2020-03-01 \
  --crisis-end    2020-04-30 \
  --output regime_prototypes_US.json
```

This will:

- Query `regimes` for `region = 'US'` in the specified windows.
- Compute mean `regime_embedding` vectors per window.
- Write a JSON file like:

```json
{
  "embedding_dim": 384,
  "prototypes": {
    "CRISIS": {
      "center": [0.01, -0.02, ...],
      "l2_norm": 12.34,
      "window": {
        "end_date": "2020-04-30",
        "start_date": "2020-03-01"
      }
    },
    "NEUTRAL": {
      "center": [0.00, 0.01, ...],
      "l2_norm": 10.11,
      "window": {
        "end_date": "2018-12-31",
        "start_date": "2018-01-01"
      }
    }
  },
  "region": "US"
}
```

## 3. Using prototypes to initialise NumericRegimeModel

You can load the JSON file and convert its entries into
`RegimePrototype` objects for `NumericRegimeModel`.

Example Python snippet (e.g. in a notebook or small script):

```python
import json
import numpy as np

from prometheus.core.config import get_config
from prometheus.core.database import DatabaseManager
from prometheus.core.time import TradingCalendar, TradingCalendarConfig, US_EQ
from prometheus.data.reader import DataReader
from prometheus.encoders import NumericWindowBuilder, NumericEmbeddingStore, NumericWindowEncoder
from prometheus.encoders.models_simple_numeric import PadToDimNumericEmbeddingModel
from prometheus.regime import NumericRegimeModel, RegimePrototype, RegimeLabel

# Load prototypes JSON
with open("regime_prototypes_US.json", "r", encoding="utf-8") as f:
    proto_cfg = json.load(f)

# Build RegimePrototype objects. This assumes that the JSON keys
# (e.g. "NEUTRAL", "CRISIS") match RegimeLabel enum names.
prototypes = []
for name, info in proto_cfg["prototypes"].items():
    label = RegimeLabel[name]  # e.g. RegimeLabel.NEUTRAL, RegimeLabel.CRISIS
    center = np.array(info["center"], dtype=np.float32)
    prototypes.append(RegimePrototype(label=label, center=center))

# Wire up a numeric encoder consistent with num-regime-core-v1.
config = get_config()
db_manager = DatabaseManager(config)
reader = DataReader(db_manager=db_manager)
calendar = TradingCalendar(TradingCalendarConfig(market=US_EQ))

builder = NumericWindowBuilder(reader, calendar)
store = NumericEmbeddingStore(db_manager=db_manager)
model = PadToDimNumericEmbeddingModel(target_dim=384)
encoder = NumericWindowEncoder(builder=builder, model=model, store=store, model_id="num-regime-core-v1")

# Construct a NumericRegimeModel using the calibrated prototypes.
regime_model = NumericRegimeModel(
    encoder=encoder,
    region_instruments={"US": "AAPL.US"},  # choose representative instrument per region
    window_days=63,
    prototypes=prototypes,
    temperature=1.0,
)
```

With this setup, calling `regime_model.classify(as_of_date, "US")` will
compare fresh embeddings against the NEUTRAL/CRISIS centres derived from
historical behaviour, instead of synthetic vectors.

## 4. Notes

- You can extend `compute_regime_prototypes` to include additional
  windows (e.g. RISK_OFF, CARRY) by adding more windows and mapping
  their names to `RegimeLabel` members.
- Prototype JSON files can be checked into `configs/` or a similar
  directory and versioned along with the code.
- For live use, you can later add a small factory/helper that reads a
  prototype config from disk or the `models` table and returns a
  fully-initialised `NumericRegimeModel`.
