"""Text encoder implementation using Hugging Face transformer models.

This module provides a concrete :class:`TextEmbeddingModel` implementation
that wraps a Hugging Face encoder model (e.g. a sentence-transformer).

It is intended for offline / research use and is **not** wired into the
core daily pipeline by default. Callers are responsible for choosing an
appropriate encoder-only model and installing the required dependencies
(`transformers`, `torch`).
"""

from __future__ import annotations

from typing import List, Optional

import numpy as np
from numpy.typing import NDArray

try:  # pragma: no cover - optional heavy dependency
    import torch
    from transformers import AutoModel, AutoTokenizer
except Exception as exc:  # pragma: no cover - handled at instantiation time
    AutoModel = None  # type: ignore[assignment]
    AutoTokenizer = None  # type: ignore[assignment]
    _IMPORT_ERROR = exc
else:  # pragma: no cover - import success path is exercised in environments with deps
    _IMPORT_ERROR = None

from prometheus.encoders.text import TextDoc, TextEmbeddingModel


class HuggingFaceTextEmbeddingModel(TextEmbeddingModel):
    """TextEmbeddingModel backed by a Hugging Face encoder model.

    This wrapper assumes an encoder-only transformer (e.g. BERT,
    sentence-transformers). It performs mean pooling over token embeddings
    by default and returns L2-normalised vectors.
    """

    def __init__(
        self,
        model_name: str,
        *,
        device: Optional[str] = None,
        pooling: str = "mean",
    ) -> None:
        """Create a new text embedding model.

        Args:
            model_name: Name or path for ``AutoModel.from_pretrained`` and
                ``AutoTokenizer.from_pretrained``.
            device: Optional device string (e.g. "cpu", "cuda"). If not
                provided, selects "cuda" when available, otherwise "cpu".
            pooling: Either ``"mean"`` (default) or ``"cls"`` for CLS-token
                pooling.
        """

        if AutoModel is None or AutoTokenizer is None:  # pragma: no cover
            raise RuntimeError(
                "HuggingFaceTextEmbeddingModel requires transformers + torch; "
                f"import error was: {_IMPORT_ERROR}"
            )

        self._tokenizer = AutoTokenizer.from_pretrained(model_name)
        self._model = AutoModel.from_pretrained(model_name)

        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self._device = device
        self._model.to(self._device)
        self._model.eval()

        if pooling not in {"mean", "cls"}:
            raise ValueError("pooling must be 'mean' or 'cls'")
        self._pooling = pooling

    def embed_batch(self, docs: List[TextDoc]) -> NDArray[np.float_]:  # type: ignore[override]
        texts = [d.text for d in docs]
        if not texts:
            return np.zeros((0, 0), dtype=np.float32)

        enc = self._tokenizer(
            texts,
            padding=True,
            truncation=True,
            return_tensors="pt",
        ).to(self._device)

        with torch.no_grad():  # type: ignore[operator]
            outputs = self._model(**enc)

        # For encoder models, last_hidden_state: [batch, seq_len, hidden]
        hidden = outputs.last_hidden_state

        if self._pooling == "cls":
            embeddings = hidden[:, 0, :]
        else:
            # Mean pooling over non-padding tokens.
            mask = enc["attention_mask"].unsqueeze(-1)  # [batch, seq_len, 1]
            summed = (hidden * mask).sum(dim=1)
            counts = mask.sum(dim=1).clamp(min=1)
            embeddings = summed / counts

        # L2-normalise per vector.
        embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
        vecs = embeddings.cpu().numpy().astype(np.float32)
        return vecs