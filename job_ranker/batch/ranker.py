# job_ranker/batch/ranker.py

"""
Deterministic batch ranking pipeline.

Principles:
- Early hard gates beat late multipliers
- Semantic similarity is primary signal
- Multipliers must not silently flatten variance
- Caps should never collapse the entire distribution
"""

import logging
import re

import numpy as np
import pandas as pd

from job_ranker.batch.veto import apply_llm_veto
from job_ranker.domain.additive_scoring import (
    apply_company_semantic_floor,
    apply_hidden_gem_bonus,
    company_score_0_100,
    compute_weighted_score,
    detect_contract_type,
    location_score_0_100,
    recency_score_0_100,
    seniority_score_0_100,
    skills_score_0_100,
)
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
from job_ranker.domain.negative_keywords import violates_negative_keywords
from job_ranker.domain.roles import (
    classify_functional_role,
    consulting_dampener,
    requires_high_semantic_floor,
    role_intent_cap,
)
from job_ranker.domain.scoring import (
    calculate_role_and_skill_match_score,
    calculate_seniority_score,
    extract_required_yoe,
    location_weight,
    recency_weight,
)
from job_ranker.domain.skill_boost import bounded_skill_boost
from job_ranker.domain.skills import SkillCanonicalizer, extract_skills_from_texts
from job_ranker.storage.store import Store

logger = logging.getLogger(__name__)


# -------------------------------------------------------------
# Helpers
# -------------------------------------------------------------
def cfg_section(cfg: dict, name: str, default=None) -> dict:
    return cfg.get(name, default or {})


def gates(cfg):
    return cfg.get("ranking", {})


def role_aware_min_semantic(cfg: dict, role: str) -> float:
    ranking = cfg_section(cfg, "ranking")
    thresholds = ranking.get("role_semantic_thresholds", {})
    return thresholds.get(role, ranking.get("min_semantic_score", 0.20))


def _log_distribution(df: pd.DataFrame, col: str, stage: str):
    if df.empty or col not in df:
        return
    logger.info(
        "[DIST %s] %s min=%.6f max=%.6f unique=%d",
        stage,
        col,
        df[col].min(),
        df[col].max(),
        df[col].nunique(),
    )


# -------------------------------------------------------------
# Phase 1
# -------------------------------------------------------------
def apply_pre_filters(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    out = df.copy()

    blocklist = cfg.get("title_blocklist", [])
    if blocklist:
        rx = re.compile(r"\b(?:%s)\b" % "|".join(map(re.escape, blocklist)), re.I)
        out = out.loc[
            ~out["title"].fillna("").astype(str).str.contains(rx)
        ].copy()

    max_yoe = cfg.get("experience", {}).get("max_yoe")
    if max_yoe is not None:
        out["_required_yoe"] = out["description"].apply(extract_required_yoe)
        out = out.loc[
            out["_required_yoe"].isna() | (out["_required_yoe"] <= max_yoe)
        ].copy()

    return out


# -------------------------------------------------------------
# Phase 2-3 (gates)
# -------------------------------------------------------------
def apply_semantic_gates(df: pd.DataFrame, cfg: dict, role_intent: str):
    out = df.copy()

    mask_non_ic = out["title"].astype(str).apply(
        requires_high_semantic_floor
    )
    mask_semantic = out["semantic_score"] >= 0.75
    out = out.loc[~mask_non_ic | mask_semantic].copy()

    out["description_quality"] = out["description"].apply(
        description_quality_multiplier
    )

    min_q = gates(cfg).get("min_quality_multiplier", 0.0)
    out = out.loc[out["description_quality"] >= min_q].copy()

    min_sem = role_aware_min_semantic(cfg, role_intent)
    out = out.loc[out["semantic_score"] >= min_sem].copy()

    return out


# -------------------------------------------------------------
# Phase 4 — Additive scoring
# -------------------------------------------------------------
def apply_additive_scoring(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    df = df.copy()

    # Compute consulting dampener per row
    df["_consulting_damp"] = df["title"].apply(consulting_dampener)

    # Dimension scores (each 0-100)
    df["skills_score"] = df.apply(
        lambda r: skills_score_0_100(
            r["semantic_score"],
            r["skill_overlap"],
            r["role_skill_score"],
            r["functional_role_penalty"],
            r["_consulting_damp"],
        ),
        axis=1,
    )
    df["company_score"] = df["company_tier"].apply(company_score_0_100)

    # Apply semantic floor to company score
    semantic_floor = cfg.get("ranking", {}).get("company_semantic_floor", 0.60)
    df["company_score"] = df.apply(
        lambda r: apply_company_semantic_floor(
            r["company_score"], r["semantic_score"], semantic_floor
        ),
        axis=1,
    )

    # Apply hidden gem bonus for unknown-tier companies with high semantic fit
    gem_threshold = cfg.get("ranking", {}).get("hidden_gem_semantic_threshold", 0.70)
    gem_bonus = cfg.get("ranking", {}).get("hidden_gem_company_bonus", 60)
    df["company_score"] = df.apply(
        lambda r: apply_hidden_gem_bonus(
            r["company_score"], r["company_tier"], r["semantic_score"],
            threshold=gem_threshold, bonus_score=gem_bonus,
        ),
        axis=1,
    )

    df["seniority_score_dim"] = df["seniority_score"].apply(seniority_score_0_100)
    df["location_score"] = df["location_weight"].apply(location_score_0_100)
    df["recency_score"] = df["date_posted"].apply(recency_score_0_100)

    # Read weights from config (with defaults)
    weights = cfg.get("ranking", {}).get("scoring_weights", {})

    df["final_score"] = df.apply(
        lambda r: compute_weighted_score(
            {
                "skills_match": r["skills_score"],
                "company_fit": r["company_score"],
                "seniority": r["seniority_score_dim"],
                "location": r["location_score"],
                "recency": r["recency_score"],
            },
            weights or None,
        ),
        axis=1,
    )

    df["final_score"] = df["final_score"].fillna(0.0)

    # Contract/part-time penalty
    contract_penalty = cfg.get("ranking", {}).get("contract_penalty", 0.9)
    df["is_contract"] = df.apply(
        lambda r: detect_contract_type(r["title"], r["description"]), axis=1
    )
    df.loc[df["is_contract"], "final_score"] *= contract_penalty

    df = df.drop(columns=["_consulting_damp"])

    return df


# -------------------------------------------------------------
# Phase 5
# -------------------------------------------------------------
def apply_caps_and_veto(df: pd.DataFrame, ctx, role_intent: str):
    df = df.copy()

    # ---- SAFE CAPS ----
    raw_caps = ctx.config.get("ranking", {}).get("caps", {}).get("role_intent", {})
    # Auto-detect old-scale caps (< 2.0) and convert to 0-100
    caps = {
        k: v * 100 if v < 2.0 else v
        for k, v in raw_caps.items()
    }

    if caps:
        cap_values = df["functional_role"].map(lambda r: caps.get(r, None))

        # Only cap where cap exists and is lower than score
        mask = cap_values.notna()
        df.loc[mask, "final_score"] = np.minimum(
            df.loc[mask, "final_score"],
            cap_values[mask],
        )

    # ---- LLM veto ----
    veto_cfg = ctx.config.get("ranking", {}).get("llm_veto", {})
    penalty = veto_cfg.get("penalty_multiplier", 1.0)

    veto_flags = apply_llm_veto(
        resume_summary=ctx.resume_text,
        job_descriptions=df["description"].fillna("").tolist(),
        role_intent=role_intent,
        cfg=ctx.config,
    )

    for idx, allowed in zip(df.index, veto_flags):
        if not allowed:
            df.at[idx, "final_score"] *= penalty

    return df


# -------------------------------------------------------------
# Main entry
# -------------------------------------------------------------
def rank(ctx, jobs_df: pd.DataFrame) -> pd.DataFrame:
    if jobs_df.empty:
        return jobs_df.assign(final_score=[])

    cfg = ctx.config
    df = jobs_df.copy()

    if "job_url_direct" not in df.columns:
        df["job_url_direct"] = None

    # ---- Phase 1
    df = apply_pre_filters(df, cfg)

    role_intent = (
        cfg.get("profile_intent", {}).get("preset")
        or cfg.get("ranking", {}).get("default_role")
        or "software_general"
    )

    if df.empty:
        return df.assign(final_score=[])

    # ---- Embeddings
    raw_skills = extract_skills_from_texts(
        df["description"].fillna("").tolist(),
        cfg,
    )
    canon = SkillCanonicalizer(cfg)
    df["canonical_skills"] = [sorted(canon.canonicalize(s)) for s in raw_skills]
    df["skill_overlap"] = df["canonical_skills"].apply(len)

    job_texts = [
        build_job_embedding_text(
            title=r["title"],
            description=r["description"],
            canonical_skills=r["canonical_skills"],
            cfg=cfg,
        )
        for _, r in df.iterrows()
    ]

    store = Store(ctx.db_path)
    cache = EmbeddingCache(store, ctx)

    job_fps = [fingerprint_text(t) for t in job_texts]
    cached = cache.fetch(job_fps)

    vectors = np.zeros(
        (len(job_fps), cfg["embeddings"]["embedding_dim"]),
        dtype="float32",
    )

    misses = [i for i, fp in enumerate(job_fps) if fp not in cached]

    for i, fp in enumerate(job_fps):
        if fp in cached:
            vectors[i] = np.array(cached[fp], dtype="float32")

    if misses:
        engine = EmbeddingEngine(cfg)
        new_vecs = engine.embed([job_texts[i] for i in misses])
        cache.store_vectors(
            [(job_fps[i], v.tolist()) for i, v in zip(misses, new_vecs)]
        )
        for i, v in zip(misses, new_vecs):
            vectors[i] = v

    resume_text = build_resume_embedding_text(
        resume_text=ctx.resume_text,
        distilled=cfg.get("resume", {}).get("distilled_text"),
        cfg=cfg,
        use_case=ctx.use_case,
    )

    resume_fp = fingerprint_text(resume_text)
    resume_cached = cache.fetch([resume_fp])

    if resume_fp in resume_cached:
        r_emb = np.array(resume_cached[resume_fp], dtype="float32")
    else:
        engine = EmbeddingEngine(cfg)
        r_emb = engine.embed([resume_text])[0]
        cache.store_vectors([(resume_fp, r_emb.tolist())])

    df["semantic_score"] = cosine_similarity(r_emb, vectors)
    _log_distribution(df, "semantic_score", "semantic")

    # ---- Phase 3
    df = apply_semantic_gates(df, cfg, role_intent)
    if df.empty:
        return df.assign(final_score=[])

    df["semantic_score"] *= df["skill_overlap"].apply(bounded_skill_boost)

    # ---- Phase 4
    df["functional_role"] = df.apply(
        lambda r: classify_functional_role(
            r["title"] or "", r["description"] or "", cfg
        ),
        axis=1,
    )

    df["role_skill_score"] = df.apply(
        lambda r: calculate_role_and_skill_match_score(
            cfg,
            title=r["title"],
            description=r["description"],
        ),
        axis=1,
    )

    scorer = CompanyScorer(cfg)
    df["company_weight"] = df["company"].apply(scorer.score)
    df["company_tier"] = df["company"].apply(scorer.classify)
    df["location_weight"] = df["location"].apply(
        lambda x: location_weight(x, cfg)
    )
    df["recency_weight"] = df["date_posted"].apply(
        lambda d: recency_weight(cfg, d)
    )

    user_yoe = cfg.get("experience", {}).get("max_yoe")
    df["seniority_score"] = df.apply(
        lambda r: calculate_seniority_score(
            cfg,
            title=r["title"],
            description=r["description"],
            user_yoe=user_yoe,
        ),
        axis=1,
    )

    penalties = cfg_section(cfg, "ranking").get(
        "functional_role_penalties", {}
    )
    df["functional_role_penalty"] = df["functional_role"].apply(
        lambda r: penalties.get(r, 1.0)
    )

    # ---- Phase 4: Additive scoring
    df = apply_additive_scoring(df, cfg)
    _log_distribution(df, "final_score", "before_caps")

    df = apply_caps_and_veto(df, ctx, role_intent)
    _log_distribution(df, "final_score", "after_caps")

    # ---- Dedup by URL
    df = (
        df.sort_values("final_score", ascending=False)
        .drop_duplicates(subset=["job_url"])
    )

    # ---- Dedup by title+company (same job from different sources)
    df["_dedup_key"] = (
        df["title"].str.strip().str.lower() + "|"
        + df["company"].str.strip().str.lower()
    )
    df = df.drop_duplicates(subset="_dedup_key", keep="first")
    df = df.drop(columns=["_dedup_key"]).reset_index(drop=True)

    return df