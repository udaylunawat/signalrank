# match_engine.py
import json
import re
from pathlib import Path
import time
import math
from datetime import datetime, timezone

import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

from company_scoring import CompanyScorer
from profiles import Profile
from llm.normalize_skills import normalize_skills_batch
from llm.distill_resume import distill_resume
from llm.classify_functional_role import classify_functional_roles_batch
from embeddings.embedding_cache import EmbeddingCache
from config import MIN_SEMANTIC_SCORE, YOE_MISMATCH_PENALTY

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_DIM = 384
RECENCY_HALF_LIFE_DAYS = 21

# --------------------------------------------------
# HARD SENIORITY BLOCK (AUTHORITATIVE)
# --------------------------------------------------
TITLE_BLOCK_RE = re.compile(
    r"\b(?:"
    r"principal|"
    r"manager|"
    r"director|"
    r"head|"
    r"vp|vice president|"
    r"lead"
    r")\b",
    re.IGNORECASE,
)

# --------------------------------------------------
# HARD FUNCTIONAL BLOCK
# --------------------------------------------------
BLOCKED_FUNCTIONAL_ROLES = {
    "security",
    "sre",
}

# --------------------------------------------------
# HELPERS
# --------------------------------------------------
def recency_weight(date_posted: str | None) -> float:
    if not date_posted:
        return 1.0
    try:
        posted = datetime.fromisoformat(date_posted.replace("Z", "+00:00"))
        age_days = (datetime.now(timezone.utc) - posted).days
        return math.exp(-age_days / RECENCY_HALF_LIFE_DAYS) if age_days >= 0 else 1.0
    except Exception:
        return 1.0


def extract_max_yoe(text: str) -> int | None:
    matches = re.findall(r"(\d+)\s*\+?\s*years", text.lower())
    if not matches:
        return None
    return min(max(map(int, matches)), 20)


# --------------------------------------------------
# MAIN
# --------------------------------------------------
def rank_jobs(
    *,
    resume_text: str,
    jobs_df: pd.DataFrame,
    preferences: dict,
    profile: Profile,
    logger,
    allow_embedding: bool = True,
    embedding_cache_dir: str | None = None,
):
    t0 = time.time()

    if jobs_df.empty:
        return jobs_df.assign(final_score=[])

    jobs_df = jobs_df.copy()
    logger.info(f"[RANK] Starting ranking on {len(jobs_df)} jobs")

    # --------------------------------------------------
    # HARD TITLE FILTER (FIRST LINE OF DEFENSE)
    # --------------------------------------------------
    before = len(jobs_df)
    jobs_df = jobs_df[
        ~jobs_df["title"].fillna("").str.contains(TITLE_BLOCK_RE)
    ]
    dropped = before - len(jobs_df)

    if dropped and logger:
        logger.info(
            f"[FILTER] Dropped {dropped} Principal/Manager/Director roles (hard block)"
        )

    if jobs_df.empty:
        logger.warning("[RANK] All jobs filtered by title seniority")
        return jobs_df.assign(final_score=[])

    # --------------------------------------------------
    # Resume distillation
    # --------------------------------------------------
    workspace = Path(profile.workspace_dir)
    workspace.mkdir(parents=True, exist_ok=True)

    distilled_path = workspace / "resume_distilled.json"
    embed_path = workspace / "resume_embedding.npy"

    if distilled_path.exists():
        distilled = json.loads(distilled_path.read_text())
    else:
        distilled = distill_resume(resume_text)
        distilled_path.write_text(json.dumps(distilled, indent=2))

    resume_caps = distilled.get("core_capabilities", [])

    resume_text_embed = (
        "Agentic AI, LLM systems, inference, evaluation, orchestration. "
        + ", ".join(resume_caps)
    )

    embedder = SentenceTransformer(MODEL_NAME, device="cpu")

    if embed_path.exists():
        r_emb = np.load(embed_path)
    else:
        r_emb = embedder.encode(
            [resume_text_embed],
            normalize_embeddings=True,
        ).astype("float32")
        np.save(embed_path, r_emb)

    # --------------------------------------------------
    # FUNCTIONAL ROLE CLASSIFICATION (HARD FILTER)
    # --------------------------------------------------
    role_texts = (
        jobs_df["title"].fillna("") + " " +
        jobs_df["description"].fillna("").str[:800]
    )

    jobs_df["functional_role"] = classify_functional_roles_batch(
        role_texts.tolist(), logger=logger
    )

    before = len(jobs_df)
    jobs_df = jobs_df[
        ~jobs_df["functional_role"].isin(BLOCKED_FUNCTIONAL_ROLES)
    ]
    dropped = before - len(jobs_df)

    if dropped and logger:
        logger.info(
            f"[FILTER] Dropped {dropped} security/SRE roles (hard block)"
        )

    if jobs_df.empty:
        logger.warning("[RANK] All jobs filtered by functional role")
        return jobs_df.assign(final_score=[])

    # --------------------------------------------------
    # Skill extraction
    # --------------------------------------------------
    jobs_df["__skills"] = normalize_skills_batch(
        jobs_df["description"].fillna("").tolist(),
        logger=logger,
    )

    job_texts = [" ".join(s) for s in jobs_df["__skills"]]

    # --------------------------------------------------
    # Embedding lookup
    # --------------------------------------------------
    cache = EmbeddingCache(
        dim=EMBED_DIM,
        cache_dir=embedding_cache_dir or "cache/embeddings",
        logger=logger,
    )

    found, missing = cache.lookup(job_texts)

    if missing and not allow_embedding:
        raise RuntimeError(
            f"[RANK] {len(missing)} embeddings missing in read-only mode."
        )

    vectors = np.zeros((len(job_texts), EMBED_DIM), dtype="float32")

    if found:
        vectors[found] = cache.get_vectors([job_texts[i] for i in found])

    if missing:
        logger.info(f"[RANK] Embedding {len(missing)} new jobs")
        texts = [job_texts[i] for i in missing]
        vecs = embedder.encode(
            texts,
            normalize_embeddings=True,
        ).astype("float32")
        vectors[missing] = vecs
        cache.add(texts, vecs)

    # --------------------------------------------------
    # Scoring
    # --------------------------------------------------
    jobs_df["semantic_score"] = cosine_similarity(r_emb, vectors)[0]
    jobs_df = jobs_df[jobs_df["semantic_score"] >= MIN_SEMANTIC_SCORE]

    scorer = CompanyScorer(
        preferred=preferences.get("preferred", []),
        deprioritized=preferences.get("deprioritized", []),
    )

    jobs_df["company_weight"] = jobs_df["company"].apply(scorer.score)
    jobs_df["max_yoe"] = jobs_df["description"].apply(extract_max_yoe)

    jobs_df.loc[
        jobs_df["max_yoe"].fillna(0) >= 12,
        "semantic_score",
    ] *= YOE_MISMATCH_PENALTY

    jobs_df["recency_weight"] = jobs_df["date_posted"].apply(recency_weight)

    jobs_df["final_score"] = (
        jobs_df["semantic_score"]
        * jobs_df["company_weight"]
        * jobs_df["recency_weight"]
    )

    ranked = jobs_df.sort_values("final_score", ascending=False).reset_index(drop=True)

    logger.info(
        f"[RANK] Completed in {time.time() - t0:.1f}s → {len(ranked)} jobs"
    )

    return ranked