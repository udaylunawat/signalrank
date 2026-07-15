import logging
import re
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from api.models import JobRaw
from domain.additive_scoring import (
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
from domain.company import CompanyScorer
from domain.description_quality import description_quality_multiplier
from domain.embed_math import cosine_similarity
from domain.embeddings import (
    EmbeddingEngine,
    build_job_embedding_text,
    build_resume_embedding_text,
    fingerprint_text,
)
from domain.roles import (
    classify_functional_role,
    consulting_dampener,
    requires_high_semantic_floor,
)
from domain.scoring import (
    calculate_role_and_skill_match_score,
    calculate_seniority_score,
    extract_required_yoe,
    location_weight,
    recency_weight,
)
from domain.skill_boost import bounded_skill_boost
from domain.skills import SkillCanonicalizer, extract_skills_from_texts
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from batch.context import build_context
from batch.embedding_cache import PgEmbeddingCache

logger = logging.getLogger(__name__)

TOP_N = 200
_ROLE_SYNONYMS = {
    "ai": {"ai", "machine learning", "ml", "llm", "agent", "agentic"},
    "agentic": {"ai", "llm", "agent", "agentic"},
    "engineer": {"engineer", "developer", "architect"},
    "platform": {"platform", "infrastructure", "devops", "cloud", "sre"},
}
_ROLE_STOPWORDS = {
    "engineer",
    "junior",
    "lead",
    "principal",
    "senior",
    "staff",
}


def _split_preference_values(values: object) -> list[str]:
    raw = values if isinstance(values, list) else [values]
    result: list[str] = []
    for value in raw:
        if not isinstance(value, str):
            continue
        for item in re.split(r"[,;\n]+", value):
            cleaned = re.sub(
                r"\s+(?:roles?|jobs?|companies|firms)$", "", item.strip(), flags=re.I
            )
            if cleaned:
                result.append(cleaned)
    return result


def _preference_location_weight(location: object, cfg: dict) -> float:
    preferred = cfg.get("location_scoring", {}).get("preferred_locations", [])
    if not preferred:
        return location_weight(str(location or ""), cfg)

    job_location = str(location or "").casefold()
    remote_job = any(
        term in job_location for term in ("remote", "worldwide", "anywhere")
    )
    for preference in preferred:
        value = str(preference).strip().casefold()
        if value in {"open to relocation", "open relocation"}:
            continue
        if value in {"remote", "remote only", "worldwide"} and remote_job:
            return float(cfg.get("location_scoring", {}).get("preferred_weight", 1.4))
        if value in {"any india", "india", "anywhere in india"} and (
            "india" in job_location
            or any(
                city in job_location
                for city in (
                    "bengaluru",
                    "bangalore",
                    "hyderabad",
                    "mumbai",
                    "pune",
                    "delhi",
                    "chennai",
                )
            )
        ):
            return float(cfg.get("location_scoring", {}).get("preferred_weight", 1.4))
        aliases = {value}
        if value in {"bangalore", "bengaluru"}:
            aliases.update({"bangalore", "bengaluru"})
        if value in {"delhi/ncr", "delhi ncr", "ncr"}:
            aliases.update({"delhi", "ncr", "gurugram", "gurgaon", "noida"})
        if any(alias and alias in job_location for alias in aliases):
            return float(cfg.get("location_scoring", {}).get("preferred_weight", 1.4))
    return 1.0


async def load_jobs_dataframe(db: AsyncSession) -> pd.DataFrame:
    result = await db.execute(
        select(
            JobRaw.id,
            JobRaw.job_url,
            JobRaw.title,
            JobRaw.company,
            JobRaw.description,
            JobRaw.location,
            JobRaw.site,
            JobRaw.date_posted,
            JobRaw.last_seen,
        ).where(JobRaw.active.is_(True))
    )
    rows = result.all()
    if not rows:
        return pd.DataFrame(
            columns=[
                "id",
                "job_url",
                "title",
                "company",
                "description",
                "location",
                "site",
                "date_posted",
                "last_seen",
            ]
        )
    return pd.DataFrame(
        rows,
        columns=[
            "id",
            "job_url",
            "title",
            "company",
            "description",
            "location",
            "site",
            "date_posted",
            "last_seen",
        ],
    )


def _apply_pre_filters(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    out = df.copy()
    max_age_days = cfg.get("ranking", {}).get("max_job_age_days", 30)
    if max_age_days and "date_posted" in out and "last_seen" in out:
        posted = pd.to_datetime(out["date_posted"], utc=True, errors="coerce")
        seen = pd.to_datetime(out["last_seen"], utc=True, errors="coerce")
        effective_date = posted.fillna(seen)
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        out = out.loc[effective_date.isna() | (effective_date >= cutoff)].copy()
    company_preferences = cfg.get("company_preferences", {})
    selected_tiers = {
        str(tier).strip().casefold()
        for tier in company_preferences.get("tiers", [])
        if str(tier).strip()
    }
    preferred_companies = _split_preference_values(
        company_preferences.get("preferred_companies", [])
    )
    if selected_tiers and "any" not in selected_tiers:
        scorer = CompanyScorer(cfg)
        tier_match = out["company"].apply(
            lambda company: scorer.classify(str(company or "")) in selected_tiers
        )
        preferred_match = out["company"].apply(
            lambda company: scorer.matches(str(company or ""), preferred_companies)
        )
        out = out.loc[tier_match | preferred_match].copy()
    blocklist = _split_preference_values(cfg.get("title_blocklist", []))
    if blocklist:
        rx = re.compile(r"\b(?:%s)\b" % "|".join(map(re.escape, blocklist)), re.I)
        out = out.loc[~out["title"].fillna("").astype(str).str.contains(rx)].copy()
    excluded_companies = _split_preference_values(
        company_preferences.get("excluded_companies", [])
    )
    if excluded_companies:
        scorer = CompanyScorer(cfg)
        mask = out["company"].apply(
            lambda company: scorer.matches(str(company or ""), excluded_companies)
        )
        out = out.loc[~mask].copy()
    max_yoe = cfg.get("experience", {}).get("max_yoe")
    if max_yoe is not None:
        out["_required_yoe"] = out["description"].apply(extract_required_yoe)
        out = out.loc[
            out["_required_yoe"].isna() | (out["_required_yoe"] <= max_yoe)
        ].copy()
    return out


def _apply_target_role_filter(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Annotate role fit without dropping adjacent or semantically strong jobs."""
    out = df.copy()
    roles = cfg.get("profile_intent", {}).get("roles", [])
    if not roles:
        out["target_role_score"] = 1.0
        out["match_lane"] = "primary"
        return out

    role_patterns: list[list[re.Pattern]] = []
    for role in roles:
        patterns = []
        for token in re.findall(r"[a-z]+", str(role).lower()):
            if token not in _ROLE_STOPWORDS and len(token) > 1:
                terms = _ROLE_SYNONYMS.get(token, {token})
                patterns.append(
                    re.compile(
                        r"\b(?:%s)\b" % "|".join(map(re.escape, sorted(terms))),
                        re.I,
                    )
                )
        if patterns:
            role_patterns.append(patterns)

    if not role_patterns:
        out["target_role_score"] = 1.0
        out["match_lane"] = "primary"
        return out

    def target_score(title: str) -> float:
        scores = []
        for patterns in role_patterns:
            matched = sum(bool(pattern.search(title)) for pattern in patterns)
            scores.append(matched / len(patterns))
        best = max(scores, default=0.0)
        if best >= 1.0:
            return 1.15
        if best >= 0.5:
            return 1.0
        if best > 0:
            return 0.9
        return 0.8

    out["target_role_score"] = out["title"].fillna("").astype(str).apply(target_score)
    out["match_lane"] = np.where(out["target_role_score"] >= 1.0, "primary", "broader")
    return out


def _apply_semantic_gates(
    df: pd.DataFrame, cfg: dict, role_intent: str
) -> pd.DataFrame:
    out = df.copy()
    mask_non_ic = out["title"].astype(str).apply(requires_high_semantic_floor)
    mask_semantic = out["semantic_score"] >= 0.75
    out = out.loc[~mask_non_ic | mask_semantic].copy()
    out["description_quality"] = out["description"].apply(
        description_quality_multiplier
    )
    ranking = cfg.get("ranking", {})
    min_q = ranking.get("min_quality_multiplier", 0.0)
    out = out.loc[out["description_quality"] >= min_q].copy()
    thresholds = ranking.get("role_semantic_thresholds", {})
    min_sem = thresholds.get(role_intent, ranking.get("min_semantic_score", 0.20))
    rescue_sem = ranking.get("broader_match_semantic_score", 0.18)
    primary = out["semantic_score"] >= min_sem
    rescue = (out["semantic_score"] >= rescue_sem) & (
        (out.get("target_role_score", 0.0) >= 1.0) | (out.get("skill_overlap", 0) >= 2)
    )
    out = out.loc[primary | rescue].copy()
    if "match_lane" in out:
        out.loc[~primary.loc[out.index], "match_lane"] = "broader"
    return out


def _apply_additive_scoring(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    df = df.copy()
    df["_consulting_damp"] = df["title"].apply(consulting_dampener)
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
    preferred_companies = _split_preference_values(
        cfg.get("company_preferences", {}).get("preferred_companies", [])
    )
    semantic_floor = cfg.get("ranking", {}).get("company_semantic_floor", 0.60)
    df["company_score"] = df.apply(
        lambda r: apply_company_semantic_floor(
            r["company_score"], r["semantic_score"], semantic_floor
        ),
        axis=1,
    )
    gem_threshold = cfg.get("ranking", {}).get("hidden_gem_semantic_threshold", 0.70)
    gem_bonus = cfg.get("ranking", {}).get("hidden_gem_company_bonus", 60)
    df["company_score"] = df.apply(
        lambda r: apply_hidden_gem_bonus(
            r["company_score"],
            r["company_tier"],
            r["semantic_score"],
            threshold=gem_threshold,
            bonus_score=gem_bonus,
        ),
        axis=1,
    )
    if preferred_companies:
        scorer = CompanyScorer(cfg)
        preferred_mask = df["company"].apply(
            lambda company: scorer.matches(str(company or ""), preferred_companies)
        )
        df.loc[preferred_mask, "company_score"] = 100.0
    df["seniority_score_dim"] = df["seniority_score"].apply(seniority_score_0_100)
    df["location_score"] = df["location_weight"].apply(location_score_0_100)
    df["recency_score"] = df["date_posted"].apply(recency_score_0_100)
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
    ).fillna(0.0)
    contract_penalty = cfg.get("ranking", {}).get("contract_penalty", 0.9)
    df["is_contract"] = df.apply(
        lambda r: detect_contract_type(r["title"], r["description"]),
        axis=1,
    )
    df.loc[df["is_contract"], "final_score"] *= contract_penalty
    df = df.drop(columns=["_consulting_damp"])
    return df


def _apply_role_lane_cap(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    if "match_lane" not in df or "final_score" not in df:
        return df
    out = df.copy()
    cap = float(cfg.get("ranking", {}).get("broader_match_score_cap", 64))
    broader = out["match_lane"] == "broader"
    out.loc[broader, "final_score"] = out.loc[broader, "final_score"].clip(upper=cap)
    return out


_SENIORITY_SUFFIXES = re.compile(
    r"\s*[-\u2013\u2014]\s*(?:vice president|assistant vice president|"
    r"senior vice president|vp|avp|svp|associate|"
    r"senior associate|principal associate)\s*$",
    re.I,
)


async def _compute_embeddings(
    df: pd.DataFrame,
    cfg: dict,
    db: AsyncSession,
    cfg_fp: str,
    resume_text: str,
    distilled_text: str | None = None,
) -> pd.DataFrame:
    cache = PgEmbeddingCache(db, cfg_fp)

    raw_skills = extract_skills_from_texts(df["description"].fillna("").tolist(), cfg)
    canon = SkillCanonicalizer(cfg)
    df["canonical_skills"] = [sorted(canon.canonicalize(s)) for s in raw_skills]
    resume_skills = canon.canonicalize(
        extract_skills_from_texts(
            ["\n".join(part for part in (resume_text, distilled_text) if part)], cfg
        )[0]
    )
    df["matched_skills"] = df["canonical_skills"].apply(
        lambda skills: matched_resume_skills(skills, resume_skills)
    )
    df["skill_overlap"] = df["matched_skills"].apply(len)
    df["skill_coverage"] = df.apply(
        lambda row: row["skill_overlap"] / max(1, len(row["canonical_skills"])),
        axis=1,
    )

    job_texts = [
        build_job_embedding_text(
            title=r["title"],
            description=r["description"],
            canonical_skills=r["canonical_skills"],
            cfg=cfg,
        )
        for _, r in df.iterrows()
    ]
    job_fps = [fingerprint_text(t) for t in job_texts]
    cached = await cache.fetch(job_fps)

    dim = cfg["embeddings"]["embedding_dim"]
    vectors = np.zeros((len(job_fps), dim), dtype="float32")
    misses = []
    for i, fp in enumerate(job_fps):
        if fp in cached:
            vectors[i] = np.array(cached[fp], dtype="float32")
        else:
            misses.append(i)

    if misses:
        engine = EmbeddingEngine(cfg)
        new_vecs = engine.embed([job_texts[i] for i in misses])
        await cache.store_vectors(
            [(job_fps[i], v.tolist()) for i, v in zip(misses, new_vecs)]
        )
        for i, v in zip(misses, new_vecs):
            vectors[i] = v

    resume_emb_text = build_resume_embedding_text(
        resume_text=resume_text,
        distilled=distilled_text or cfg.get("resume", {}).get("distilled_text"),
        cfg=cfg,
        use_case="default",
    )
    resume_fp = fingerprint_text(resume_emb_text)
    resume_cached = await cache.fetch([resume_fp])

    if resume_fp in resume_cached:
        r_emb = np.array(resume_cached[resume_fp], dtype="float32")
    else:
        engine = EmbeddingEngine(cfg)
        r_emb = engine.embed([resume_emb_text])[0]
        await cache.store_vectors([(resume_fp, r_emb.tolist())])

    df["semantic_score"] = cosine_similarity(r_emb, vectors)
    return df


def matched_resume_skills(job_skills: list[str], resume_skills: set[str]) -> list[str]:
    return sorted(set(job_skills) & resume_skills)


async def score_jobs_for_user(
    db: AsyncSession,
    user_id: str,
    resume_text: str,
    config_overrides: dict | None,
    distilled_text: str | None = None,
) -> pd.DataFrame:
    ctx = build_context(user_id, resume_text, config_overrides)
    cfg = ctx.config

    df = await load_jobs_dataframe(db)
    if df.empty:
        return pd.DataFrame(columns=["final_score"])

    df = _apply_pre_filters(df, cfg)
    df = _apply_target_role_filter(df, cfg)
    if df.empty:
        return pd.DataFrame(columns=["final_score"])

    role_intent = (
        cfg.get("profile_intent", {}).get("preset")
        or cfg.get("ranking", {}).get("default_role")
        or "software_general"
    )

    df = await _compute_embeddings(
        df, cfg, db, ctx.config_fp, resume_text, distilled_text=distilled_text
    )

    df = _apply_semantic_gates(df, cfg, role_intent)
    if df.empty:
        return pd.DataFrame(columns=["final_score"])

    df["semantic_score"] *= df["skill_overlap"].apply(bounded_skill_boost)

    df["functional_role"] = df.apply(
        lambda r: classify_functional_role(
            r["title"] or "", r["description"] or "", cfg
        ),
        axis=1,
    )
    df["role_skill_score"] = df.apply(
        lambda r: (
            calculate_role_and_skill_match_score(
                cfg,
                title=r["title"],
                description=r["description"],
            )
            * r.get("target_role_score", 1.0)
        ),
        axis=1,
    )
    scorer = CompanyScorer(cfg)
    df["company_weight"] = df["company"].apply(scorer.score)
    df["company_tier"] = df["company"].apply(scorer.classify)
    df["location_weight"] = df["location"].apply(
        lambda value: _preference_location_weight(value, cfg)
    )
    df["recency_weight"] = df["date_posted"].apply(lambda d: recency_weight(cfg, d))

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
    penalties = cfg.get("ranking", {}).get("functional_role_penalties", {})
    df["functional_role_penalty"] = df["functional_role"].apply(
        lambda r: penalties.get(r, 1.0)
    )

    df = _apply_additive_scoring(df, cfg)
    df = _apply_role_lane_cap(df, cfg)

    df = df.sort_values("final_score", ascending=False).drop_duplicates(
        subset=["job_url"]
    )
    df["_dedup_key"] = (
        df["title"].str.strip().str.lower()
        + "|"
        + df["company"].str.strip().str.lower()
    )
    df = df.drop_duplicates(subset="_dedup_key", keep="first")
    df["_fuzzy_key"] = (
        df["title"]
        .str.strip()
        .str.lower()
        .str.replace(_SENIORITY_SUFFIXES, "", regex=True)
        .str.strip()
        + "|"
        + df["company"].str.strip().str.lower()
    )
    df = df.drop_duplicates(subset="_fuzzy_key", keep="first")
    df = df.drop(columns=["_dedup_key", "_fuzzy_key"], errors="ignore").reset_index(
        drop=True
    )

    return df.head(TOP_N)
