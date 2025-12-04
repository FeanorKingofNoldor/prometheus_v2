"""Prometheus v2 – Encoders package.

This package contains text, numeric, and joint embedding encoders used
throughout the system. The initial implementation focuses on numeric
window encoders and their persistence layer.
"""

from prometheus.encoders.numeric import (
    NumericWindowSpec,
    NumericWindowBuilder,
    NumericEmbeddingModel,
    NumericEmbeddingStore,
    NumericWindowEncoder,
)
from prometheus.encoders.models_simple_numeric import (
    FlattenNumericEmbeddingModel,
    PadToDimNumericEmbeddingModel,
)
from prometheus.encoders.text import (
    TextDoc,
    TextEmbeddingModel,
    TextEmbeddingStore,
    TextEmbeddingService,
)
# NOTE: concrete text models such as HuggingFaceTextEmbeddingModel live in
# dedicated modules (e.g. ``prometheus.encoders.models_text_hf``) to avoid
# importing heavy ML dependencies by default.
from prometheus.encoders.joint import (
    JointExample,
    JointEmbeddingModel,
    JointEmbeddingStore,
    JointEmbeddingService,
)
