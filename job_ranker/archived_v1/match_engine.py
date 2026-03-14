# ================================
# FILE: match_engine.py
# ================================
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
from company_scoring import CompanyScorer
from config_loader import fingerprint_settings, settings
from core.score_primitives import extract_max_yoe, recency_weight, seniority_penalty
from fastembed import TextEmbedding
from llm.classify_functional_role import classify_functional_roles_batch
from llm.distill_resume import distill_resume
from profiles import Profile
from skills.canonicalizer import build_canonical_texts
from storage.db import JobStore
from utils.timing import timed


# --------------------------------------------------
# Utilities
# --------------------------------------------------
def fingerprint_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------
# Resume profile + embedding text
# --------------------------------------------------
def load_resume_profile(
    *,
    resume_text: str,
    workspace: Path,
    cfg_fp: str,
    effective_settings: dict,
    ctx,
    logger,
) -> Tuple[set[str], str]:
    """
    Returns:
      (canonical_resume_skills, resume_embedding_text)
    """

    distilled_path = workspace / "resume_distilled.json"
    resume_fp = fingerprint_text(resume_text)
    canon_path = workspace / f"resume_canonical_skills_{cfg_fp}_{resume_fp}.json"

    # ------------------------------
    # Distill resume (cached)
    # ------------------------------
    if distilled_path.exists():
        distilled = json.loads(distilled_path.read_text())
    else:
        distilled = distill_resume(resume_text)
        distilled_path.write_text(json.dumps(distilled, indent=2))

    # ------------------------------
    # Canonical skills (cached)
    # ------------------------------
    canonical_skills: set[str] = set()

    if canon_path.exists():
        payload = json.loads(canon_path.read_text())
        if payload.get("cfg_fingerprint") == cfg_fp:
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
                effective_settings=effective_settings,
                cfg_fingerprint=cfg_fp,
            )
        )

        canon_path.write_text(
            json.dumps(
                {
                    "cfg_fingerprint": cfg_fp,
                    "skills": sorted(canonical_skills),
                },
                indent=2,
            )
        )

    # ------------------------------
    # Build embedding text (CRITICAL)
    # ------------------------------
    mode = settings.resume.embedding.mode
    sep = settings.resume.embedding.separator

    if mode == "prefix_only":
        embed_text = settings.resume.embedding_prefix

    elif mode == "skills_only":
        embed_text = sep.join(sorted(canonical_skills))

    else:
        # ✅ FIX: use ctx.use_case, not cfg.use_case
        prefix = settings.resume.embedding_prefix
        overrides = getattr(settings.resume, "embedding_prefix_by_use_case", {})

        if isinstance(overrides, dict):
            prefix = overrides.get(ctx.use_case, prefix)

        logger.info(
            f"[RANK] Using resume embedding prefix for use_case='{ctx.use_case}'"
        )

        embed_text = prefix + sep + sep.join(sorted(canonical_skills))

    return canonical_skills, embed_text


# --------------------------------------------------
# Main ranking entrypoint
# --------------------------------------------------
def rank_jobs(
    *,
    resume_text: str,
    jobs_df: pd.DataFrame,
    preferences: dict,
    profile: Profile,
    logger,
    effective_settings,
    ctx,
    allow_embedding: bool = True,
    embedding_cache_dir: str | None = None,  # API compatibility
):

    t0 = time.time()

    if jobs_df.empty:
        return jobs_df.assign(final_score=[])

    jobs_df = jobs_df.copy()
    logger.info(f"[RANK] Starting ranking on {len(jobs_df)} jobs")

    # --------------------------------------------------
    # Hard filters (titles + companies)
    # --------------------------------------------------
    blocklist = effective_settings["ranking"]["hard_title_blocklist"]
    if blocklist:
        title_re = re.compile(
            r"\b(?:%s)\b" % "|".join(map(re.escape, blocklist)),
            re.IGNORECASE,
        )
        jobs_df = jobs_df[~jobs_df["title"].fillna("").str.contains(title_re)]

    blocked_companies = {c.lower() for c in profile.deprioritized_companies}
    if blocked_companies:
        jobs_df = jobs_df[
            ~jobs_df["company"]
            .fillna("")
            .str.lower()
            .apply(lambda c: any(b in c for b in blocked_companies))
        ]

    if jobs_df.empty:
        return jobs_df.assign(final_score=[])

    # --------------------------------------------------
    # Workspace + store
    # --------------------------------------------------
    workspace = Path(
        settings.workspace.template.format(
            workspaces_dir=settings.paths.workspaces_dir,
            user=ctx.user,
            profile=profile.name,
        )
    )
    workspace.mkdir(parents=True, exist_ok=True)

    cfg_fp = fingerprint_settings(effective_settings)
    store = JobStore(ctx.base_dir / "jobs.duckdb")

    # --------------------------------------------------
    # Resume embedding
    # --------------------------------------------------
    embedder = TextEmbedding(model_name=settings.embeddings.model_name)

    resume_skills, resume_embed_text = load_resume_profile(
        resume_text=resume_text,
        workspace=workspace,
        cfg_fp=cfg_fp,
        effective_settings=effective_settings,
        ctx=ctx,
        logger=logger,
    )

    resume_fp = fingerprint_text(resume_embed_text)
    cached = store.fetch_embeddings(
        text_fingerprints=[resume_fp],
        cfg_fingerprint=cfg_fp,
        user=ctx.user,
        use_case=ctx.use_case,
    )

    if resume_fp in cached:
        r_emb = np.array(cached[resume_fp], dtype="float32")
    else:
        if not allow_embedding:
            raise RuntimeError("Missing resume embedding")

        r_emb = np.array(list(embedder.embed([resume_embed_text]))[0], dtype="float32")
        store.store_embeddings(
            rows=[(resume_fp, cfg_fp, r_emb.tolist())],
            user=ctx.user,
            use_case=ctx.use_case,
        )

    # --------------------------------------------------
    # Functional role classification
    # --------------------------------------------------
    role_texts = (
        jobs_df["title"].fillna("") + " " + jobs_df["description"].fillna("").str[:800]
    )

    with timed("Functional role classification", logger):
        jobs_df["functional_role"] = classify_functional_roles_batch(
            role_texts.tolist(),
            logger=logger,
        )

    allowed_roles = set(
        effective_settings["ranking"].get("allowed_functional_roles", [])
    )
    if allowed_roles:
        jobs_df = jobs_df[jobs_df["functional_role"].isin(allowed_roles)]

    if jobs_df.empty:
        return jobs_df.assign(final_score=[])

    # --------------------------------------------------
    # Job embeddings
    # --------------------------------------------------
    canonical_texts, canonical_job_skills = build_canonical_texts(
        jobs_df["description"].fillna("").tolist(),
        effective_settings=effective_settings,
        cfg_fingerprint=cfg_fp,
    )
    jobs_df["canonical_job_skills"] = canonical_job_skills

    fps = [fingerprint_text(t) for t in canonical_texts]
    found_vecs = store.fetch_embeddings(
        text_fingerprints=fps,
        cfg_fingerprint=cfg_fp,
        user=ctx.user,
        use_case=ctx.use_case,
    )

    vectors = np.zeros((len(fps), settings.embeddings.embedding_dim), dtype="float32")
    missing_texts, missing_idx = [], []

    for i, fp in enumerate(fps):
        if fp in found_vecs:
            vectors[i] = np.array(found_vecs[fp], dtype="float32")
        else:
            missing_texts.append(canonical_texts[i])
            missing_idx.append(i)

    if missing_texts:
        if not allow_embedding:
            raise RuntimeError("Missing job embeddings")

        new_vecs = list(embedder.embed(missing_texts))
        rows = []
        for idx, vec in zip(missing_idx, new_vecs):
            v = np.array(vec, dtype="float32")
            vectors[idx] = v
            rows.append((fps[idx], cfg_fp, v.tolist()))

        store.store_embeddings(
            rows=rows,
            user=ctx.user,
            use_case=ctx.use_case,
        )

    # --------------------------------------------------
    # Semantic similarity + gating
    # --------------------------------------------------
    semantic = store.cosine_similarity_bulk(
        query_vector=r_emb.tolist(),
        vectors=vectors.tolist(),
    )
    jobs_df["semantic_score"] = pd.Series(semantic).fillna(0.0)

    min_score = effective_settings["ranking"]["min_semantic_score"]
    per_profile = effective_settings["ranking"].get("min_semantic_score_by_profile", {})
    min_score = per_profile.get(profile.name, min_score)

    passed = jobs_df[jobs_df["semantic_score"] >= min_score]

    if passed.empty:
        logger.warning(
            "[RANK] Absolute semantic gate removed all jobs. Using fallback."
        )
        cutoff = max(np.percentile(jobs_df["semantic_score"], 85), 0.03)
        passed = jobs_df[jobs_df["semantic_score"] >= cutoff]
        logger.warning(
            f"[RANK] Fallback semantic cutoff={cutoff:.4f} "
            f"kept={len(passed)}/{len(jobs_df)}"
        )

    if passed.empty:
        return jobs_df.assign(final_score=[])

    jobs_df = passed

    # --------------------------------------------------
    # Company scoring
    # --------------------------------------------------
    scorer = CompanyScorer(
        preferred=preferences.get("preferred", []),
        deprioritized=preferences.get("deprioritized", []),
    )

    jobs_df["raw_company_weight"] = jobs_df["company"].apply(scorer.score)
    floor = effective_settings["ranking"]["semantic_company_floor"]

    jobs_df["effective_company_weight"] = np.where(
        jobs_df["semantic_score"] >= floor,
        jobs_df["raw_company_weight"],
        1.0,
    )

    jobs_df["effective_company_weight"] *= np.where(
        jobs_df["raw_company_weight"] == 1.0, 1.05, 1.0
    )

    # --------------------------------------------------
    # Experience + recency
    # --------------------------------------------------
    jobs_df["max_yoe"] = jobs_df["description"].apply(
        lambda x: extract_max_yoe(settings, x)
    )

    jobs_df.loc[
        jobs_df["max_yoe"].fillna(0)
        >= effective_settings["ranking"]["yoe_penalty_threshold"],
        "semantic_score",
    ] *= effective_settings["ranking"]["yoe_mismatch_penalty"]

    jobs_df["recency_weight"] = jobs_df["date_posted"].apply(
        lambda d: recency_weight(settings, d)
    )

    # --------------------------------------------------
    # Functional role penalty
    # --------------------------------------------------
    penalties = effective_settings["ranking"]["functional_role_penalties"]
    jobs_df["functional_role_penalty"] = jobs_df["functional_role"].apply(
        lambda r: penalties.get(r, 1.0)
    )

    # --------------------------------------------------
    # Skill overlap
    # --------------------------------------------------
    overlap_cfg = effective_settings["ranking"]["skill_overlap"]
    resume_skill_set = set(resume_skills)

    overlap_mult, overlap_top = [], []

    for skills in jobs_df["canonical_job_skills"]:
        overlap = sorted(resume_skill_set.intersection(skills))
        overlap_top.append(overlap[:3])

        if overlap_cfg["enabled"] and overlap:
            boost = 1.0 + overlap_cfg["alpha"] * (
                len(overlap) / max(1, len(resume_skill_set))
            )
            overlap_mult.append(min(boost, overlap_cfg["cap_multiplier"]))
        else:
            overlap_mult.append(1.0)

    jobs_df["skill_overlap_multiplier"] = overlap_mult
    jobs_df["skill_overlap_top"] = overlap_top

    # --------------------------------------------------
    # Seniority penalty
    # --------------------------------------------------
    jobs_df["seniority_penalty"] = jobs_df.apply(
        lambda r: seniority_penalty(r["title"], r["description"], settings),
        axis=1,
    )

    # --------------------------------------------------
    # Final score
    # --------------------------------------------------
    jobs_df["final_score"] = (
        jobs_df["semantic_score"]
        * jobs_df["effective_company_weight"]
        * jobs_df["recency_weight"]
        * jobs_df["functional_role_penalty"]
        * jobs_df["skill_overlap_multiplier"]
        * jobs_df["seniority_penalty"]
    )

    ranked = jobs_df.sort_values("final_score", ascending=False).reset_index(drop=True)

    logger.info(f"[RANK] Completed in {time.time() - t0:.1f}s → {len(ranked)} jobs")

    ranked.attrs["canonical_resume_skills"] = sorted(resume_skills)
    return ranked
