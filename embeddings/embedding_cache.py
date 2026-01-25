# embeddings/embedding_cache.py
import faiss
faiss.omp_set_num_threads(1)

import hashlib
import json
from pathlib import Path
from typing import List, Tuple
import numpy as np

from embeddings.telemetry import log_timer


class EmbeddingCache:
    def __init__(
        self,
        dim: int,
        cache_dir: str = "cache/embeddings",
        logger=None,
    ):
        self.dim = dim
        self.logger = logger
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.index_path = self.cache_dir / "jobs.faiss"
        self.meta_path = self.cache_dir / "jobs_meta.json"

        self.index = faiss.IndexFlatIP(dim)
        self.meta: list[str] = []

        if self.index_path.exists() and self.meta_path.exists():
            self._load()

    def _load(self):
        with log_timer(self.logger, "FAISS load"):
            self.index = faiss.read_index(str(self.index_path))
            self.meta = json.loads(self.meta_path.read_text())

        if self.logger:
            self.logger.info(
                f"[EMBED] Loaded FAISS index with {len(self.meta)} vectors"
            )

    def _save(self):
        with log_timer(self.logger, "FAISS save"):
            faiss.write_index(self.index, str(self.index_path))
            self.meta_path.write_text(json.dumps(self.meta))

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    def lookup(self, texts: List[str]) -> Tuple[List[int], List[int]]:
        found, missing = [], []

        for i, t in enumerate(texts):
            if self._hash(t) in self.meta:
                found.append(i)
            else:
                missing.append(i)

        if self.logger:
            hit_rate = len(found) / max(1, len(texts))
            self.logger.info(
                f"[EMBED] Cache lookup: "
                f"{len(found)} hit / {len(missing)} miss "
                f"(hit-rate={hit_rate:.1%})"
            )

        return found, missing

    def get_vectors(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype="float32")

        hash_to_idx = {h: i for i, h in enumerate(self.meta)}
        out = np.zeros((len(texts), self.dim), dtype="float32")

        for i, t in enumerate(texts):
            h = self._hash(t)
            idx = hash_to_idx.get(h)
            if idx is None:
                raise KeyError(f"Vector not found for hash {h}")
            out[i] = self.index.reconstruct(idx)

        return out

    def add(self, texts: List[str], vectors: np.ndarray):
        new_vecs, new_hashes = [], []

        for t, v in zip(texts, vectors):
            h = self._hash(t)
            if h not in self.meta:
                new_vecs.append(v)
                new_hashes.append(h)

        if not new_vecs:
            if self.logger:
                self.logger.info("[EMBED] No new vectors to add")
            return

        with log_timer(self.logger, f"FAISS add ({len(new_vecs)} vectors)"):
            self.index.add(np.vstack(new_vecs))
            self.meta.extend(new_hashes)

        self._save()