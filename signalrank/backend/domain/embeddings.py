# domain/embeddings.py
from __future__ import annotations

import hashlib
import logging
import os
import sys
from pathlib import Path
from typing import List

import numpy as np

logger = logging.getLogger(__name__)
_ENGINE = None


def _embedding_model_source(configured: str) -> str:
    explicit = os.getenv("SIGNALRANK_EMBEDDING_MODEL_PATH", "").strip()
    if explicit:
        return explicit
    bundle_root = getattr(sys, "_MEIPASS", "")
    if bundle_root:
        packaged = Path(bundle_root) / "models" / "all-MiniLM-L6-v2"
        if packaged.is_dir():
            return str(packaged)
    return configured


def fingerprint_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class EmbeddingEngine:
    def __init__(self, cfg):
        if hasattr(self, "model"):
            return

        from sentence_transformers import SentenceTransformer

        emb_cfg = cfg["embeddings"]

        self.model_name = emb_cfg["model_name"]
        model_source = _embedding_model_source(self.model_name)
        self.device = emb_cfg.get("device", "cpu")
        self.normalize = emb_cfg["text"].get("normalize_embeddings", True)

        logger.info(
            "[EMBED] Loading model=%s device=%s normalize=%s",
            self.model_name,
            self.device,
            self.normalize,
        )

        self.model = SentenceTransformer(
            model_source,
            device=self.device,
        )

        logger.info("[EMBED] Model loaded successfully")

    def __new__(cls, cfg):
        global _ENGINE
        if _ENGINE is not None:
            return _ENGINE
        self = super().__new__(cls)
        _ENGINE = self
        return self

    def embed(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 0), dtype="float32")

        logger.info("[EMBED] Encoding %d texts", len(texts))

        batch_size = 64 if self.device == "mps" else 256

        vecs = self.model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=self.normalize,
            show_progress_bar=False,
        )

        return np.asarray(vecs, dtype="float32")


def build_job_embedding_text(
    *,
    title: str,
    description: str,
    canonical_skills: list[str],
    cfg: dict,
) -> str:
    max_chars = cfg["embeddings"]["text"].get("max_chars", 2000)

    title = (title or "").strip()
    desc = " ".join((description or "").split())[:max_chars]
    skills = ", ".join(sorted(canonical_skills)) if canonical_skills else ""

    return f"ROLE: {title}\n" f"RESPONSIBILITIES: {desc}\n" f"REQUIRED_SKILLS: {skills}"


def build_resume_embedding_text(*, resume_text, distilled):
    return distilled or resume_text
