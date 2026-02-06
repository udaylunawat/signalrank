# job_ranker/batch/ranker.py
"""
Deterministic batch ranking pipeline.

Design principles:
- Early hard gates beat late multipliers
- Quality > cleverness
- Semantic similarity is primary; everything else is a modifier
- No signal should resurrect a bad match
"""

import logging
import re
from typing import Dict

import numpy as np
import pandas as pd

from job_ranker.batch.veto import apply_llm_veto
from job_ranker.domain.company import CompanyScorer
from job_ranker.domain.description_quality import description_quality_multiplier
from job_ranker.domain.embed_math import cosine_similarity
from job_ranker.domain.embeddings import (
    EmbeddingCache,
    EmbeddingEngine,
    build_job_embedding_text,
    build_resume_embedding_text,
    fingerprint_text,
)
from job_ranker.domain.roles import classify_functional_role
from job_ranker.domain.scoring import (
    extract_required_yoe,
    location_weight,
    recency_weight,
    seniority_penalty,
)
from job_ranker.domain.skill_boost import bounded_skill_boost
from job_ranker.domain.skills import SkillCanonicalizer, extract_skills_from_texts
from job_ranker.storage.store import Store
from job_ranker.domain.negative_keywords import violates_negative_keywords

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------
def cfg_section(cfg: Dict, name: str, default=None) -> Dict:
    if default is None:
        default = {}
    return cfg.get(name, default)


def role_aware_min_semantic(cfg: Dict, role: str) -> float:
    ranking_cfg = cfg_section(cfg, "ranking")
    role_thresholds = ranking_cfg.get("role_semantic_thresholds", {})
    return role_thresholds.get(
        role,
        ranking_cfg.get("min_semantic_score", 0.20),
    )


# ---------------------------------------------------------------------
# Title heuristics (local, deterministic)
# ---------------------------------------------------------------------
NON_IC_KEYWORDS = {
    "analyst",
    "executive",
    "operations",
    "process",
    "hr",
    "human resource",
    "trainer",
    "talent",
    "sourcing",
    "business systems",
}

IC_ALLOWLIST = {
    "engineer",
    "developer",
    "architect",
    "systems",
}

CONSULTING_KEYWORDS = {
    "consultant",
    "consulting",
    "engagement",
    "advisory",
    "client",
    "manager",
    "director",
    "assistant manager",
    "senior manager",
}

STRONG_IC_KEYWORDS = {
    "engineer",
    "developer",
    "architect",
    "platform",
    "systems",
    "backend",
    "ml",
    "ai",
}


def requires_high_semantic_floor(title: str) -> bool:
    t = title.lower()
    is_non_ic = any(k in t for k in NON_IC_KEYWORDS)
    has_ic_signal = any(k in t for k in IC_ALLOWLIST)
    return is_non_ic and not has_ic_signal


def consulting_dampener(title: str) -> float:
    t = title.lower()
    has_consulting = any(k in t for k in CONSULTING_KEYWORDS)
    has_ic_signal = any(k in t for k in STRONG_IC_KEYWORDS)
    if has_consulting and not has_ic_signal:
        return 0.8
    return 1.0


# ---------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------
def rank(ctx, jobs_df: pd.DataFrame) -> pd.DataFrame:
    if jobs_df.empty:
        logger.info("[RANK] No jobs to rank")
        return jobs_df.assign(final_score=[])

    cfg = ctx.config
    df = jobs_df.copy()

    logger.info("[RANK] Starting ranking on %d jobs", len(df))

    if "job_url_direct" not in df.columns:
        df["job_url_direct"] = None

    # ------------------------------------------------------------------
    # Skill extraction + canonicalization
    # ------------------------------------------------------------------
    raw_skills = extract_skills_from_texts(
        df["description"].fillna("").tolist(),
        cfg,
    )

    canon = SkillCanonicalizer(cfg)
    df["canonical_skills"] = [sorted(canon.canonicalize(s)) for s in raw_skills]
    df["skill_overlap"] = df["canonical_skills"].apply(len)

    # ------------------------------------------------------------------
    # Optional title blocklist
    # ------------------------------------------------------------------
    blocklist = cfg.get("title_blocklist", [])
    if blocklist:
        rx = re.compile(
            r"\b(?:%s)\b" % "|".join(map(re.escape, blocklist)),
            re.IGNORECASE,
        )
        before = len(df)
        df = df[~df["title"].fillna("").str.contains(rx)]
        logger.info("[RANK] Title blocklist removed %d jobs", before - len(df))

    # ------------------------------------------------------------------
    # Experience hard filter
    # ------------------------------------------------------------------
    exp_cfg = cfg.get("experience", {})
    max_yoe = exp_cfg.get("max_yoe")

    if max_yoe is not None:
        df["_required_yoe"] = df["description"].apply(extract_required_yoe)
        before = len(df)
        df = df[(df["_required_yoe"].isna()) | (df["_required_yoe"] <= max_yoe)]
        logger.info("[RANK] YOE filter max=%s kept=%d/%d", max_yoe, len(df), before)

    if df.empty:
        return df.assign(final_score=[])

    # ------------------------------------------------------------------
    # Role-specific negative keyword kill-switch
    # ------------------------------------------------------------------
    role_intent = cfg.get("profile_intent", {}).get("preset", "software_general")
    neg_cfg = cfg_section(cfg, "ranking").get("role_negative_keywords", {})
    neg_terms = neg_cfg.get(role_intent, [])

    if neg_terms:
        before = len(df)
        df = df[
            ~(
                df["title"].fillna("") + " " + df["description"].fillna("")
            ).apply(
                lambda t: violates_negative_keywords(
                    text=t,
                    negative_keywords=neg_terms,
                )
            )
        ]
        logger.info(
            "[RANK] Negative keyword kill-switch role=%s removed=%d",
            role_intent,
            before - len(df),
        )

    # ------------------------------------------------------------------
    # Build job embedding texts
    # ------------------------------------------------------------------
    min_len = cfg_section(cfg, "ranking").get("min_description_length", 100)
    df = df[df["description"].str.len() >= min_len]

    job_texts = [
        build_job_embedding_text(
            title=row.get("title", ""),
            description=row.get("description", ""),
            canonical_skills=row["canonical_skills"],
            cfg=cfg,
        )
        for _, row in df.iterrows()
    ]

    # ------------------------------------------------------------------
    # Job embeddings (cached)
    # ------------------------------------------------------------------
    store = Store(ctx.db_path)
    cache = EmbeddingCache(store, ctx)
    engine = None

    job_fps = [fingerprint_text(t) for t in job_texts]
    df["_text_fp"] = job_fps

    cached = cache.fetch(job_fps)
    vectors = np.zeros(
        (len(job_fps), cfg["embeddings"]["embedding_dim"]),
        dtype="float32",
    )

    misses = []
    for i, fp in enumerate(job_fps):
        if fp in cached:
            vectors[i] = np.array(cached[fp], dtype="float32")
        else:
            misses.append(i)

    if misses:
        engine = engine or EmbeddingEngine(cfg)
        new_vecs = engine.embed([job_texts[i] for i in misses])
        cache.store_vectors(
            [(job_fps[i], v.tolist()) for i, v in zip(misses, new_vecs)]
        )
        for i, v in zip(misses, new_vecs):
            vectors[i] = v

    # ------------------------------------------------------------------
    # Resume embedding
    # ------------------------------------------------------------------
    resume_cfg = cfg.get("resume", {})
    resume_text = build_resume_embedding_text(
        resume_text=ctx.resume_text,
        distilled=resume_cfg["distilled_text"],
        cfg=cfg,
        use_case=ctx.use_case,
    )

    resume_fp = fingerprint_text(resume_text)
    resume_cached = cache.fetch([resume_fp])

    if resume_fp in resume_cached:
        r_emb = np.array(resume_cached[resume_fp], dtype="float32")
    else:
        engine = engine or EmbeddingEngine(cfg)
        r_emb = engine.embed([resume_text])[0]
        cache.store_vectors([(resume_fp, r_emb.tolist())])

    # ------------------------------------------------------------------
    # Semantic similarity
    # ------------------------------------------------------------------
    df["semantic_score"] = cosine_similarity(r_emb, vectors)

    # ------------------------------------------------------------------
    # Non-IC hard semantic floor
    # ------------------------------------------------------------------
    before = len(df)
    df = df[
        ~df["title"].apply(requires_high_semantic_floor)
        | (df["semantic_score"] >= 0.75)
    ]
    logger.info(
        "[RANK] Non-IC semantic floor removed=%d",
        before - len(df),
    )

    # ------------------------------------------------------------------
    # Description quality gate
    # ------------------------------------------------------------------
    df["description_quality"] = df["description"].apply(description_quality_multiplier)

    min_q = cfg_section(cfg, "ranking").get("min_quality_multiplier", 0.70)
    before = len(df)
    df = df[df["description_quality"] >= min_q]
    logger.info(
        "[RANK] Description quality gate min=%.2f kept=%d/%d",
        min_q,
        len(df),
        before,
    )

    df["semantic_score"] *= df["description_quality"]

    # ------------------------------------------------------------------
    # Role-aware semantic gate (software_general tightened)
    # ------------------------------------------------------------------
    min_sem = role_aware_min_semantic(cfg, role_intent)
    before = len(df)

    if role_intent == "software_general":
        df = df[
            (df["semantic_score"] >= min_sem)
            & (df["description_quality"] >= 0.9)
        ]
    else:
        df = df[df["semantic_score"] >= min_sem]

    logger.info(
        "[RANK] Role-aware semantic gate role=%s kept=%d/%d",
        role_intent,
        len(df),
        before,
    )

    if df.empty:
        return df.assign(final_score=[])

    # ------------------------------------------------------------------
    # Skill overlap bounded boost
    # ------------------------------------------------------------------
    df["semantic_score"] *= df["skill_overlap"].apply(bounded_skill_boost)

    # ------------------------------------------------------------------
    # Functional role classification
    # ------------------------------------------------------------------
    df["functional_role"] = (
        df["title"].fillna("") + " " + df["description"].fillna("")
    ).apply(lambda t: classify_functional_role(t, cfg))

    # ------------------------------------------------------------------
    # Deterministic secondary signals
    # ------------------------------------------------------------------
    df["location_weight"] = df["location"].apply(lambda loc: location_weight(loc, cfg))

    scorer = CompanyScorer(cfg)
    df["company_weight"] = df["company"].apply(scorer.score)

    df["recency_weight"] = df["date_posted"].apply(lambda d: recency_weight(cfg, d))

    df["seniority_penalty"] = df.apply(
        lambda r: seniority_penalty(cfg, r["title"], r["description"]),
        axis=1,
    )

    role_penalties = cfg_section(cfg, "ranking").get("functional_role_penalties", {})
    df["functional_role_penalty"] = df["functional_role"].apply(
        lambda r: role_penalties.get(r, 1.0)
    )

    # ------------------------------------------------------------------
    # Final score (consulting dampener applied here)
    # ------------------------------------------------------------------
    df["final_score"] = (
        df["semantic_score"]
        * df["company_weight"]
        * df["location_weight"]
        * df["recency_weight"]
        * df["functional_role_penalty"]
        * df["seniority_penalty"]
        * df["title"].apply(consulting_dampener)
    )

    # ------------------------------------------------------------------
    # Optional LLM veto
    # ------------------------------------------------------------------
    veto_flags = apply_llm_veto(
        resume_summary=ctx.resume_text,
        job_descriptions=df["description"].fillna("").tolist(),
        role_intent=role_intent,
        cfg=cfg,
    )

    veto_penalty = (
        cfg_section(cfg, "ranking").get("llm_veto", {}).get("penalty_multiplier", 1.0)
    )

    for idx, allowed in zip(df.index, veto_flags):
        if not allowed:
            df.at[idx, "final_score"] *= veto_penalty

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------
    df["_dedupe_key"] = (
        df["company"].fillna("").str.lower().str.strip()
        + "||"
        + df["title"].fillna("").str.lower().str.strip()
        + "||"
        + df["description"].fillna("").str.lower().str.strip()
    )

    before = len(df)
    df = (
        df.sort_values("final_score", ascending=False)
        .drop_duplicates("_dedupe_key", keep="first")
        .drop(columns="_dedupe_key")
    )

    logger.info("[RANK] Deduplicated kept=%d/%d", len(df), before)
    logger.info("[RANK] Ranking complete")

    return df.sort_values("final_score", ascending=False).reset_index(drop=True)