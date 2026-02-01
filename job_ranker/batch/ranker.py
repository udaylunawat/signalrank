# batch/ranker.py
import logging
import re

import numpy as np
import pandas as pd

from job_ranker.batch.veto import apply_llm_veto
from job_ranker.domain.company import CompanyScorer
from job_ranker.domain.embed_math import cosine_similarity
from job_ranker.domain.embeddings import (
    EmbeddingCache,
    EmbeddingEngine,
    build_job_embedding_text,
    build_resume_embedding_text,
    fingerprint_text,
    get_or_create_resume_embedding,
)
from job_ranker.domain.roles import classify_functional_role
from job_ranker.domain.scoring import (
    extract_required_yoe,
    location_weight,
    recency_weight,
    seniority_penalty,
)
from job_ranker.domain.skills import SkillCanonicalizer, extract_skills_from_texts
from job_ranker.llm.distill_resume import distill_resume

logger = logging.getLogger(__name__)


def cfg_section(cfg, name, default=None):
    if default is None:
        default = {}
    return cfg.get(name, default)


def rank(ctx, jobs_df: pd.DataFrame) -> pd.DataFrame:
    if jobs_df.empty:
        logger.info("[RANK] No jobs to rank")
        return jobs_df.assign(final_score=[])

    cfg = ctx.config
    df = jobs_df.copy()

    logger.info("[RANK] Starting ranking on %d jobs", len(df))

    # --------------------------------------------------
    # Skill extraction
    # --------------------------------------------------
    raw_skills = extract_skills_from_texts(
        df["description"].fillna("").tolist(),
        cfg,
    )

    canon = SkillCanonicalizer(cfg)
    df["canonical_skills"] = [sorted(canon.canonicalize(s)) for s in raw_skills]
    blocklist = cfg.get("title_blocklist", [])
    if blocklist:
        rx = re.compile(
            r"\b(?:%s)\b" % "|".join(map(re.escape, blocklist)),
            re.IGNORECASE,
        )
        df = df[~df["title"].fillna("").str.contains(rx)]

    # --------------------------------------------------
    # EXPERIENCE HARD FILTER (YOE)
    # --------------------------------------------------
    exp_cfg = cfg.get("experience", {})
    max_yoe = exp_cfg.get("max_yoe")

    if max_yoe is not None:
        df["_required_yoe"] = df["description"].apply(extract_required_yoe)

        before = len(df)
        df = df[(df["_required_yoe"].isna()) | (df["_required_yoe"] <= max_yoe)]

        logger.info(
            "[RANK] YOE filter max=%s → kept %d / %d",
            max_yoe,
            len(df),
            before,
        )
    # --------------------------------------------------
    # Job embedding texts
    # --------------------------------------------------
    job_texts = [
        build_job_embedding_text(
            title=row.get("title", ""),
            description=row.get("description", ""),
            canonical_skills=row["canonical_skills"],
            cfg=cfg,
        )
        for _, row in df.iterrows()
    ]

    # --------------------------------------------------
    # Embeddings (jobs)
    # --------------------------------------------------
    engine = EmbeddingEngine(cfg)
    cache = EmbeddingCache(ctx.store, ctx)

    job_fps = [fingerprint_text(t) for t in job_texts]
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

    logger.info(
        "[RANK] Job embedding cache: hits=%d misses=%d",
        len(job_fps) - len(misses),
        len(misses),
    )

    if misses:
        new_vecs = engine.embed([job_texts[i] for i in misses])
        cache.store_vectors(
            [(job_fps[i], v.tolist()) for i, v in zip(misses, new_vecs)]
        )
        for i, v in zip(misses, new_vecs):
            vectors[i] = v

    # --------------------------------------------------
    # Resume embedding
    # --------------------------------------------------
    distilled = distill_resume(ctx.resume_text)

    resume_text = build_resume_embedding_text(
        resume_text=ctx.resume_text,
        distilled=distilled,
        cfg=cfg,
        use_case=ctx.use_case,
    )

    resume_fp = fingerprint_text(resume_text)
    resume_cached = cache.fetch([resume_fp])

    if resume_fp in resume_cached:
        r_emb = np.array(resume_cached[resume_fp], dtype="float32")
        logger.info("[RANK] Resume embedding cache hit")
    else:
        logger.info("[RANK] Resume embedding cache miss")
        r_emb = engine.embed([resume_text])[0]
        cache.store_vectors([(resume_fp, r_emb.tolist())])

    get_or_create_resume_embedding(ctx, engine)
    # --------------------------------------------------
    # Semantic similarity + gate
    # --------------------------------------------------
    df["semantic_score"] = cosine_similarity(r_emb, vectors)
    min_len = cfg_section(cfg, "ranking").get("min_description_length", 100)
    short_penalty = cfg_section(cfg, "ranking").get("short_description_penalty", 0.85)
    short_mask = df["description"].str.len() < (min_len * 2)
    df.loc[short_mask, "semantic_score"] *= short_penalty
    min_score = cfg_section(cfg, "ranking").get("min_semantic_score", 0.30)
    before = len(df)
    df = df[df["semantic_score"] >= min_score]

    logger.info(
        "[RANK] Semantic gate %.2f → kept %d / %d",
        min_score,
        len(df),
        before,
    )

    if df.empty:
        return df.assign(final_score=[])

    df["location_weight"] = df["location"].apply(
        lambda location: location_weight(location, cfg)
    )
    # --------------------------------------------------
    # Functional role + penalties
    # --------------------------------------------------
    df["functional_role"] = (
        df["title"].fillna("") + " " + df["description"].fillna("")
    ).apply(lambda t: classify_functional_role(t, cfg))
    ENGINE_ROLES = {
        "agentic_systems",
        "mlops_llmops",
        "platform_devops",
        "software_general",
        "security",
    }
    df["Category"] = df["functional_role"]
    raw_penalties = cfg.get("ranking", {}).get("functional_role_penalties", {})
    role_penalties = {k: v for k, v in raw_penalties.items() if k in ENGINE_ROLES}

    df["functional_role_penalty"] = df["functional_role"].apply(
        lambda r: role_penalties.get(r, 1.0)
    )

    # --------------------------------------------------
    # Other deterministic signals
    # --------------------------------------------------
    scorer = CompanyScorer(cfg)
    df["company_weight"] = df["company"].apply(scorer.score)

    df["recency_weight"] = df["date_posted"].apply(lambda d: recency_weight(cfg, d))
    logger.info(df["date_posted"])
    df["seniority_penalty"] = df.apply(
        lambda r: seniority_penalty(cfg, r["title"], r["description"]),
        axis=1,
    )

    # --------------------------------------------------
    # Final score
    # --------------------------------------------------
    df["final_score"] = (
        df["semantic_score"]
        * df["company_weight"]
        * df["location_weight"]
        * df["recency_weight"]
        * df["functional_role_penalty"]
        * df["seniority_penalty"]
    )

    # --------------------------------------------------
    # Optional LLM veto (safe)
    # --------------------------------------------------
    veto_flags = apply_llm_veto(
        resume_summary=ctx.resume_text,
        job_descriptions=df["description"].fillna("").tolist(),
        role_intent=cfg.get("profile_intent", {}).get("preset", ""),
        cfg=cfg,
    )

    penalty = cfg.get("ranking", {}).get("llm_veto", {}).get("penalty_multiplier", 1.0)
    for i, allowed in enumerate(veto_flags):
        if not allowed:
            df.at[i, "final_score"] *= penalty

    logger.info("[RANK] Ranking complete → %d jobs", len(df))
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

    logger.info(
        "[RANK] Deduplicated jobs: kept %d / %d",
        len(df),
        before,
    )
    return df.sort_values("final_score", ascending=False).reset_index(drop=True)
