# domain/embeddings.py
from __future__ import annotations

import hashlib
import logging
from typing import Dict, Iterable, List

import numpy as np

logger = logging.getLogger(__name__)


def fingerprint_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class EmbeddingEngine:
    def __init__(self, cfg):
        # 🚫 Hard guard: never allow this in Streamlit
        if "streamlit" in __import__("sys").modules:
            raise RuntimeError("EmbeddingEngine must not be used inside Streamlit UI")

        from sentence_transformers import SentenceTransformer

        emb_cfg = cfg["embeddings"]

        self.model_name = emb_cfg["model_name"]
        self.device = emb_cfg.get("device", "cpu")
        self.normalize = emb_cfg["text"].get("normalize_embeddings", True)

        logger.info(
            "[EMBED] Loading model=%s device=%s normalize=%s",
            self.model_name,
            self.device,
            self.normalize,
        )

        self.model = SentenceTransformer(
            self.model_name,
            device=self.device,
        )

        logger.info("[EMBED] Model loaded successfully")

    def embed(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 0), dtype="float32")

        logger.info("[EMBED] Encoding %d texts", len(texts))

        vecs = self.model.encode(
            texts,
            normalize_embeddings=self.normalize,
            show_progress_bar=False,
        )

        return np.asarray(vecs, dtype="float32")


class EmbeddingCache:
    """
    DuckDB-backed embedding cache (read/write via Store).

    RULES:
    - keyed by (text_fp, cfg_fp, user, use_case)
    - deterministic lookup
    """

    def __init__(self, store, ctx):
        self.store = store
        self.ctx = ctx

    def fetch(self, text_fps: Iterable[str]) -> Dict[str, List[float]]:
        if not text_fps:
            return {}

        rows = self.store.con.execute(
            """
            SELECT text_fp, vector
            FROM embeddings
            WHERE
              text_fp IN ?
              AND cfg_fp = ?
              AND user = ?
              AND use_case = ?
            """,
            [
                list(text_fps),
                self.ctx.config_fp,
                self.ctx.user,
                self.ctx.use_case,
            ],
        ).fetchall()

        return {k: v for k, v in rows}

    def store_vectors(self, rows: List[tuple[str, List[float]]]):
        if not rows:
            return

        import pandas as pd

        df = pd.DataFrame(
            rows,
            columns=["text_fp", "vector"],
        )
        df["cfg_fp"] = self.ctx.config_fp
        df["user"] = self.ctx.user
        df["use_case"] = self.ctx.use_case

        self.store.con.execute("""
            INSERT INTO embeddings
            SELECT
              text_fp,
              cfg_fp,
              vector,
              user,
              use_case
            FROM df
            ON CONFLICT (text_fp, cfg_fp, user, use_case)
            DO NOTHING
            """)


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


def build_resume_embedding_text(
    *,
    resume_text: str,
    distilled: dict | None,
    cfg: dict,
    use_case: str,
) -> str:
    resume_cfg = cfg.get("resume", {})

    embedding_cfg = resume_cfg.get("embedding", {})
    sep = embedding_cfg.get("separator", " ")
    mode = embedding_cfg.get("mode", "prefix_plus_skills")
    if mode not in {"prefix_only", "skills_only", "prefix_plus_skills"}:
        mode = "prefix_plus_skills"

    prefix = resume_cfg.get("embedding_prefix", "")
    overrides = resume_cfg.get("embedding_prefix_by_use_case", {})
    if isinstance(overrides, dict):
        prefix = overrides.get(use_case, prefix)

    if not distilled:
        return (prefix + sep + resume_text[:1500]).strip()

    bits = (
        distilled.get("primary_focus", [])
        + distilled.get("core_capabilities", [])
        + distilled.get("secondary_skills", [])
    )
    bits = [b.strip() for b in bits if isinstance(b, str)]

    if mode == "prefix_only":
        return prefix.strip()

    if mode == "skills_only":
        return sep.join(bits)

    # default: prefix_plus_skills
    return (prefix + sep + sep.join(bits)).strip()


def get_or_create_resume_embedding(ctx, engine):
    import json

    from job_ranker.domain.embeddings import fingerprint_text

    resume_fp = fingerprint_text(ctx.resume_text)
    store = ctx.store

    row = store.con.execute(
        """
        SELECT payload
        FROM resume_distillations
        WHERE resume_fp = ? AND user = ? AND use_case = ?
        """,
        [resume_fp, ctx.user, ctx.use_case],
    ).fetchone()

    if row:
        return np.array(json.loads(row[0]), dtype="float32")

    emb = engine.embed([ctx.resume_text])[0]

    store.con.execute(
        """
        INSERT OR REPLACE INTO resume_distillations
        (resume_fp, user, use_case, payload, created_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        [resume_fp, ctx.user, ctx.use_case, json.dumps(emb.tolist())],
    )

    return emb
