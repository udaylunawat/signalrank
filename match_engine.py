# match_engine.py
import json
import re
from pathlib import Path
from typing import List
import time

import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from company_scoring import CompanyScorer
from profiles import Profile
from llm.normalize_skills import normalize_skills_batch
from llm.distill_resume import distill_resume
from llm.classify_functional_role import classify_functional_roles_batch
from llm.explain_match import explain_matches_batch

from embeddings.embedding_cache import EmbeddingCache
from sentence_transformers import SentenceTransformer

from config import (
    MIN_SEMANTIC_SCORE,
    YOE_MISMATCH_PENALTY,
    TOP_K_EXPLAIN,
)

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_DIM = 384

ROLE_WEIGHT = {
    "ai_ml_core": 1.0,
    "agentic_systems": 1.0,
    "mlops_llmops": 0.95,
    "data_science": 0.85,
    "software_general": 0.65,
    "platform_devops": 0.4,
    "sre": 0.35,
    "security": 0.25,
}


def _empty_with_score(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["final_score"] = []
    return df


def extract_max_yoe(text: str) -> int | None:
    matches = re.findall(r"(\d+)\s*\+?\s*years", text.lower())
    if not matches:
        return None

    y = max(map(int, matches))

    # hard cap: anything above 20 years is noise
    if y > 20:
        return 20

    return y


def binary_job_quality(row: pd.Series) -> float:
    return 0.85 if len(row["description"]) < 800 else 1.0


def rank_jobs(
    resume_text: str,
    jobs_df: pd.DataFrame,
    preferences: dict,
    profile: Profile,
    logger,
):
    t0 = time.time()

    if jobs_df.empty:
        logger.info("Ranking skipped: no jobs")
        return _empty_with_score(jobs_df)

    jobs_df = jobs_df.copy()
    logger.info(f"[RANK] Starting ranking on {len(jobs_df)} jobs")

    # ---------- Resume distillation ----------
    logger.info("[RANK] Resume distillation")
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
    non_focus = set(distilled.get("non_focus", []))

    resume_embed_text = (
        "Agentic AI, LLM systems, inference, evaluation, orchestration. "
        + ", ".join(resume_caps)
    )

    logger.info("[RANK] Loading embedding model")
    embedder = SentenceTransformer(MODEL_NAME, device="cpu")

    if embed_path.exists():
        r_emb = np.load(embed_path)
    else:
        logger.info("[RANK] Embedding resume")
        r_emb = embedder.encode(
            [resume_embed_text],
            normalize_embeddings=True,
        ).astype("float32")
        np.save(embed_path, r_emb)

    # ---------- Functional role ----------
    logger.info("[RANK] Functional role classification")
    role_texts = (
        jobs_df["title"].fillna("") + " " +
        jobs_df["description"].fillna("").str[:800]
    )

    jobs_df["functional_role"] = classify_functional_roles_batch(
        role_texts.tolist(),
        logger=logger,
    )

    jobs_df = jobs_df[
        ~jobs_df["functional_role"].isin({"security", "sre"})
    ]
    assert len(jobs_df["functional_role"]) == len(jobs_df)
    logger.info(f"[RANK] After role filter: {len(jobs_df)} jobs")

    if jobs_df.empty:
        return _empty_with_score(jobs_df)

    # ---------- Skills ----------
    logger.info("[RANK] Skill extraction")
    descriptions = jobs_df["description"].fillna("").tolist()
    job_skills = normalize_skills_batch(descriptions, logger=logger)
    jobs_df["__skills"] = job_skills

    job_texts = [" ".join(s) for s in job_skills]

    # ---------- Embeddings ----------
    logger.info(f"[RANK] FAISS lookup for {len(job_texts)} jobs")
    cache = EmbeddingCache(dim=EMBED_DIM, logger=logger)
    found_idx, missing_idx = cache.lookup(job_texts)

    vectors = np.zeros((len(job_texts), EMBED_DIM), dtype="float32")

    if found_idx:
        vectors[found_idx] = cache.get_vectors(
            [job_texts[i] for i in found_idx]
        )

    if missing_idx:
        logger.info(f"[RANK] Embedding {len(missing_idx)} new jobs")
        new_texts = [job_texts[i] for i in missing_idx]
        new_vecs = embedder.encode(
            new_texts,
            normalize_embeddings=True,
        ).astype("float32")
        vectors[missing_idx] = new_vecs
        cache.add(new_texts, new_vecs)

    # ---------- Scoring ----------
    logger.info("[RANK] Semantic scoring")
    jobs_df["semantic_score"] = cosine_similarity(r_emb, vectors)[0]
    jobs_df = jobs_df[jobs_df["semantic_score"] >= MIN_SEMANTIC_SCORE]

    logger.info(f"[RANK] After semantic filter: {len(jobs_df)} jobs")

    # ---------- Final score ----------
    logger.info("[RANK] Final scoring")
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

    LOW_PRIORITY_SKILLS = {
        "java", "spark", "hadoop", "scala", "kafka"
    }

    def low_priority_penalty(skills):
        overlap = set(skills) & LOW_PRIORITY_SKILLS
        return 0.85 if overlap else 1.0

    jobs_df["low_priority_penalty"] = jobs_df["__skills"].apply(low_priority_penalty)

    jobs_df["final_score"] = (
        jobs_df["semantic_score"]
        * jobs_df["company_weight"]
        * jobs_df["low_priority_penalty"]
    )

    # hard quality floor
    jobs_df = jobs_df[
        (jobs_df["semantic_score"] >= 0.22) &
        (jobs_df["final_score"] >= 0.18)
    ]
    # ranked = jobs_df.sort_values("final_score", ascending=False).reset_index(drop=True)
    # --------------------------------------------------
    # HARD IC FILTER (SAFE)
    # --------------------------------------------------
    if "role" in jobs_df.columns:
        jobs_df = jobs_df[jobs_df["role"] == "individual_contributor"]
    else:
        if logger:
            logger.warning(
                "[RANK] 'role' column missing; skipping IC-only filter"
            )

    ranked = (
        jobs_df
        .sort_values("final_score", ascending=False)
        .reset_index(drop=True)
    )

    logger.info(
        f"[RANK] Completed in {time.time() - t0:.1f}s → {len(ranked)} jobs"
    )
    logger.info(
        f"[RANK] Summary → "
        f"total={len(jobs_df)}, "
        f"returned={len(ranked)}, "
        f"min_score={ranked['final_score'].min():.3f}, "
        f"max_score={ranked['final_score'].max():.3f}"
    )
    return ranked