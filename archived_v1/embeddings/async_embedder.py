# embeddings/async_embedder.py
from typing import List

import numpy as np
from embeddings.telemetry import log_timer
from sentence_transformers import SentenceTransformer


class AsyncEmbedder:
    """
    NOTE:
    This is intentionally synchronous.
    Async + ThreadPool + Streamlit + FAISS causes segfaults on macOS.
    """

    def __init__(
        self,
        model_name: str,
        max_workers: int = 1,  # ignored, kept for compatibility
        device: str | None = None,
        logger=None,
    ):
        self.logger = logger

        self.model = SentenceTransformer(
            model_name,
            device="cpu",
        )

        if logger:
            logger.info(f"[EMBED] Loaded model {model_name} (cpu, single-thread)")

    def embed(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.zeros(
                (0, self.model.get_sentence_embedding_dimension()), dtype="float32"
            )

        with log_timer(self.logger, f"Encode batch ({len(texts)})"):
            vecs = self.model.encode(
                texts,
                normalize_embeddings=True,
                show_progress_bar=False,
            )

        return vecs.astype("float32")
