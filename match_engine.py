# ================================
# FILE: match_engine.py
# ================================
import json
import re
from pathlib import Path
import time
import math
import hashlib
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Tuple

import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

from company_scoring import CompanyScorer
from profiles import Profile
from llm.distill_resume import distill_resume
from llm.classify_functional_role import classify_functional_roles_batch
from embeddings.embedding_cache import EmbeddingCache
from config_loader import settings, fingerprint_settings


# --------------------------------------------------
# CONFIG NORMALIZATION
# --------------------------------------------------
def to_namespace(obj):
    if isinstance(obj, dict):
        return SimpleNamespace(**{k: to_namespace(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return [to_namespace(x) for x in obj]
    return obj


# --------------------------------------------------
# PURE HELPERS
# --------------------------------------------------
def recency_weight(cfg, date_posted: str | None) -> float:
    if not cfg.ranking.enable_recency_decay or not date_posted:
        return 1.0
    try:
        posted = datetime.fromisoformat(date_posted.replace("Z", "+00:00"))
        age_days = (datetime.now(timezone.utc) - posted).days
        return math.exp(-age_days / cfg.ranking.recency_half_life_days)
    except Exception:
        return 1.0


def extract_max_yoe(cfg, text: str) -> int | None:
    matches = re.findall(r"(\d+)\s*\+?\s*years", text.lower())
    if not matches:
        return None
    return min(max(map(int, matches)), cfg.ranking.max_yoe_cap)


def fingerprint_resume(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------
# RESUME PIPELINE
# --------------------------------------------------
def _load_or_build_resume_profile(
    *,
    resume_text: str,
    workspace: Path,
    cfg_fp: str,
) -> Tuple[set[str], str]:
    """
    Returns:
    - canonical_resume_skills (set)
    - resume_text_for_embedding (str)
    """
    distilled_path = workspace / "resume_distilled.json"
    resume_fp = fingerprint_resume(resume_text)
    canonical_path = workspace / f"resume_canonical_skills_{cfg_fp}_{resume_fp}.json"

    # --- distillation ---
    if distilled_path.exists():
        distilled = json.loads(distilled_path.read_text())
    else:
        distilled = distill_resume(resume_text)
        distilled_path.write_text(json.dumps(distilled, indent=2))

    # --- canonical skills ---
    canonical_skills: set[str] = set()

    if canonical_path.exists():
        payload = json.loads(canonical_path.read_text())
        if payload.get("cfg_fingerprint") == cfg_fp and payload.get("resume_fingerprint") == resume_fp:
            canonical_skills = set(payload.get("skills", []))

    if not canonical_skills:
        from skills.canonicalizer import canonicalize_and_dedupe

        raw_skills = (
            distilled.get("core_capabilities", [])
            + distilled.get("primary_focus", [])
            + distilled.get("secondary_skills", [])
        )

        canonical_skills = set(
            canonicalize_and_dedupe(
                raw_skills,
                effective_settings=settings if isinstance(settings, dict) else settings,
                cfg_fingerprint=cfg_fp,
            )
        )

        canonical_path.write_text(
            json.dumps(
                {
                    "cfg_fingerprint": cfg_fp,
                    "resume_fingerprint": resume_fp,
                    "skills": sorted(canonical_skills),
                },
                indent=2,
            )
        )

    resume_embed_text = (
        settings.resume.embedding_prefix + " " + " ".join(sorted(canonical_skills))
    )

    return canonical_skills, resume_embed_text


def _load_or_build_resume_embedding(
    *,
    resume_embed_text: str,
    embedder: SentenceTransformer,
    embed_path: Path,
    cfg,
) -> np.ndarray:
    if embed_path.exists():
        return np.load(embed_path)

    emb = embedder.encode(
        [resume_embed_text],
        normalize_embeddings=cfg.embeddings.text.normalize_embeddings,
    ).astype("float32")

    np.save(embed_path, emb)
    return emb


# --------------------------------------------------
# JOB EMBEDDINGS
# --------------------------------------------------
def _build_job_embeddings(
    *,
    jobs_df: pd.DataFrame,
    cfg,
    embedder: SentenceTransformer,
    cache: EmbeddingCache,
    allow_embedding: bool,
    effective_settings,
) -> Tuple[np.ndarray, list[list[str]]]:
    from skills.canonicalizer import build_canonical_texts

    cfg_fp = fingerprint_settings(effective_settings)

    canonical_texts, canonical_job_skills = build_canonical_texts(
        jobs_df["description"].fillna("").tolist(),
        effective_settings=effective_settings,
        cfg_fingerprint=cfg_fp,
    )

    vectors = np.zeros(
        (len(canonical_texts), cfg.embeddings.embedding_dim), dtype="float32"
    )

    found, missing = cache.lookup(canonical_texts)

    if found:
        vectors[found] = cache.get_vectors(
            [canonical_texts[i] for i in found]
        )

    if missing:
        if not allow_embedding:
            raise RuntimeError("Missing embeddings in read-only mode")
        texts = [canonical_texts[i] for i in missing]
        vecs = embedder.encode(
            texts,
            normalize_embeddings=cfg.embeddings.text.normalize_embeddings,
        ).astype("float32")
        vectors[missing] = vecs
        cache.add(texts, vecs)

    return vectors, canonical_job_skills


# --------------------------------------------------
# MAIN ORCHESTRATOR
# --------------------------------------------------
def rank_jobs(
    *,
    resume_text: str,
    jobs_df: pd.DataFrame,
    preferences: dict,
    profile: Profile,
    logger,
    effective_settings=None,
    allow_embedding: bool = True,
    embedding_cache_dir: str | None = None,
):
    t0 = time.time()
    cfg = to_namespace(effective_settings) if effective_settings else settings

    if jobs_df.empty:
        return jobs_df.assign(final_score=[])

    jobs_df = jobs_df.copy()
    logger.info(f"[RANK] Starting ranking on {len(jobs_df)} jobs")

    # --------------------------------------------------
    # HARD TITLE FILTER
    # --------------------------------------------------
    title_re = re.compile(
        r"\b(?:%s)\b" % "|".join(map(re.escape, cfg.ranking.hard_title_blocklist)),
        re.IGNORECASE,
    )
    jobs_df = jobs_df[~jobs_df["title"].fillna("").str.contains(title_re)]

    if jobs_df.empty:
        return jobs_df.assign(final_score=[])

    # --------------------------------------------------
    # WORKSPACE
    # --------------------------------------------------
    workspace = Path(profile.workspace_dir)
    workspace.mkdir(parents=True, exist_ok=True)

    cfg_fp = fingerprint_settings(effective_settings)
    resume_fp = fingerprint_resume(resume_text)
    embed_path = workspace / f"resume_embedding_{cfg_fp}_{resume_fp}.npy"

    embedder = SentenceTransformer(
        cfg.embeddings.model_name,
        device=cfg.embeddings.device,
    )

    # --------------------------------------------------
    # RESUME PIPELINE
    # --------------------------------------------------
    canonical_resume_skills, resume_embed_text = _load_or_build_resume_profile(
        resume_text=resume_text,
        workspace=workspace,
        cfg_fp=cfg_fp,
    )

    r_emb = _load_or_build_resume_embedding(
        resume_embed_text=resume_embed_text,
        embedder=embedder,
        embed_path=embed_path,
        cfg=cfg,
    )

    # --------------------------------------------------
    # FUNCTIONAL ROLE (NON-BLOCKING)
    # --------------------------------------------------
    role_texts = (
        jobs_df["title"].fillna("")
        + " "
        + jobs_df["description"].fillna("").str[:800]
    )

    jobs_df["functional_role"] = classify_functional_roles_batch(
        role_texts.tolist(), logger=logger
    )

    # --------------------------------------------------
    # JOB EMBEDDINGS
    # --------------------------------------------------
    if not embedding_cache_dir:
        raise ValueError("embedding_cache_dir must be provided")

    cache = EmbeddingCache(
        dim=cfg.embeddings.embedding_dim,
        cache_dir=embedding_cache_dir,
        cfg_fingerprint=cfg_fp,
        logger=logger,
    )

    vectors, canonical_job_skills = _build_job_embeddings(
        jobs_df=jobs_df,
        cfg=cfg,
        embedder=embedder,
        cache=cache,
        allow_embedding=allow_embedding,
        effective_settings=effective_settings,
    )

    jobs_df["canonical_job_skills"] = canonical_job_skills

    # --------------------------------------------------
    # SCORING
    # --------------------------------------------------
    semantic = cosine_similarity(r_emb, vectors)[0]
    jobs_df["semantic_score"] = semantic

    jobs_df = jobs_df[jobs_df["semantic_score"] >= cfg.ranking.min_semantic_score]

    scorer = CompanyScorer(
        preferred=preferences.get("preferred", []),
        deprioritized=preferences.get("deprioritized", []),
    )

    company_weight = jobs_df["company"].apply(scorer.score)
    jobs_df["company_weight"] = company_weight

    max_yoe = jobs_df["description"].apply(lambda x: extract_max_yoe(cfg, x))
    jobs_df["max_yoe"] = max_yoe

    yoe_penalty_applied = max_yoe.fillna(0) >= cfg.ranking.yoe_penalty_threshold
    jobs_df.loc[yoe_penalty_applied, "semantic_score"] *= cfg.ranking.yoe_mismatch_penalty

    recency = jobs_df["date_posted"].apply(lambda d: recency_weight(cfg, d))
    jobs_df["recency_weight"] = recency

    # --------------------------------------------------
    # SKILL OVERLAP MULTIPLIER
    # --------------------------------------------------
    overlap_cfg = getattr(cfg.ranking, "skill_overlap", None)

    overlap_multiplier = []
    overlap_top = []

    resume_skills = set(canonical_resume_skills)

    for skills in jobs_df["canonical_job_skills"]:
        overlap = sorted(resume_skills.intersection(skills))
        overlap_top.append(overlap[:3])

        if overlap_cfg and overlap_cfg.enabled and overlap:
            boost = 1.0 + overlap_cfg.alpha * (len(overlap) / max(1, len(resume_skills)))
            overlap_multiplier.append(min(boost, overlap_cfg.cap_multiplier))
        else:
            overlap_multiplier.append(1.0)

    jobs_df["skill_overlap_multiplier"] = overlap_multiplier
    jobs_df["skill_overlap_top"] = overlap_top

    # --------------------------------------------------
    # FINAL SCORE + BREAKDOWN
    # --------------------------------------------------
    final = (
        jobs_df["semantic_score"]
        * jobs_df["company_weight"]
        * jobs_df["recency_weight"]
        * jobs_df["skill_overlap_multiplier"]
    )

    jobs_df["final_score"] = final

    jobs_df["score_breakdown"] = [
        json.dumps(
            {
                "semantic": round(s, 4),
                "company": round(c, 4),
                "recency": round(r, 4),
                "skill_overlap": round(o, 4),
                "yoe_penalty_applied": bool(y),
            }
        )
        for s, c, r, o, y in zip(
            jobs_df["semantic_score"],
            jobs_df["company_weight"],
            jobs_df["recency_weight"],
            jobs_df["skill_overlap_multiplier"],
            yoe_penalty_applied,
        )
    ]

    ranked = jobs_df.sort_values("final_score", ascending=False).reset_index(drop=True)

    logger.info(f"[RANK] Completed in {time.time() - t0:.1f}s → {len(ranked)} jobs")

    return ranked