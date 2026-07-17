import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import (
    CompanyReputation as CompanyReputationModel,
    JobFeedback,
    JobRaw,
)
from batch.context import build_context
from batch.embedding_cache import PgEmbeddingCache
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
from domain.embed_math import cosine_similarity
from domain.embeddings import (
    EmbeddingEngine,
    build_job_embedding_text,
    build_resume_embedding_text,
    fingerprint_text,
)
from domain.scoring import (
    calculate_seniority_score,
    extract_required_yoe_range,
    location_weight,
)
from domain.skill_boost import bounded_skill_boost
from domain.skills import SkillCanonicalizer
from llm.company_reputation import canonicalize_company_name

logger = logging.getLogger(__name__)

TOP_N = 200
_ROLE_GENERIC_WORDS = {
    "associate",
    "developer",
    "engineer",
    "junior",
    "lead",
    "manager",
    "principal",
    "senior",
    "specialist",
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
    frame = pd.DataFrame(
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
    reputation_rows = await db.execute(select(CompanyReputationModel))
    reputations = {row.canonical_name: row for row in reputation_rows.scalars().all()}

    def reputation_value(company: object, field: str, default: object) -> object:
        row = reputations.get(canonicalize_company_name(str(company or "")))
        return getattr(row, field, default) if row else default

    frame["ai_company_score"] = frame["company"].apply(
        lambda company: reputation_value(company, "reputation_score", None)
    )
    frame["ai_company_tier"] = frame["company"].apply(
        lambda company: reputation_value(company, "reputation_tier", "unknown")
    )
    frame["company_reputation_confidence"] = frame["company"].apply(
        lambda company: reputation_value(company, "confidence", 0.0)
    )
    frame["company_reputation_rationale"] = frame["company"].apply(
        lambda company: reputation_value(company, "rationale", None)
    )
    return frame


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
    filter_mode = company_preferences.get("filter_mode", "all")
    selected_tiers = {
        str(tier).strip().casefold()
        for tier in company_preferences.get("tiers", [])
        if str(tier).strip()
    }
    preferred_companies = _split_preference_values(
        company_preferences.get("preferred_companies", [])
    )
    if filter_mode == "top_reputed":
        known_tier = out.get("ai_company_tier", pd.Series("unknown", index=out.index))
        confidence = out.get(
            "company_reputation_confidence", pd.Series(0.0, index=out.index)
        )
        scorer = CompanyScorer(cfg)
        preferred_match = out["company"].apply(
            lambda company: scorer.matches(str(company or ""), preferred_companies)
        )
        out = out.loc[
            ((known_tier.isin(["S", "A"])) & (confidence >= 0.7)) | preferred_match
        ].copy()
    elif (
        filter_mode == "selected_tiers"
        and selected_tiers
        and "any" not in selected_tiers
    ):
        scorer = CompanyScorer(cfg)
        selected_ai_tiers = {
            tier.removeprefix("tier_").upper() for tier in selected_tiers
        }
        tier_match = out.get(
            "ai_company_tier", pd.Series("unknown", index=out.index)
        ).isin(selected_ai_tiers)
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
    return out


def _apply_target_role_filter(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Annotate role fit without dropping adjacent or semantically strong jobs."""
    out = df.copy()
    roles = cfg.get("profile_intent", {}).get("roles", [])
    if not roles:
        out["target_role_score"] = 1.0
        out["match_lane"] = "primary"
        return out

    configured_aliases = cfg.get("profile_intent", {}).get("role_aliases", {})
    role_signatures: list[tuple[str, set[str], str]] = []
    for role in roles:
        aliases = [role]
        if isinstance(configured_aliases, dict):
            aliases.extend(configured_aliases.get(str(role), []) or [])
        for alias in aliases:
            normalized = " ".join(
                re.findall(r"[a-z0-9+#.]+", str(alias).casefold())
            )
            tokens = set(normalized.split())
            discriminative = tokens - _ROLE_GENERIC_WORDS
            if normalized:
                role_signatures.append(
                    (normalized, discriminative or tokens, str(role))
                )

    if not role_signatures:
        out["target_role_score"] = 1.0
        out["match_lane"] = "primary"
        return out

    def target_score(title: str, description: str) -> tuple[float, str | None, str]:
        normalized_title = " ".join(
            re.findall(r"[a-z0-9+#.]+", str(title).casefold())
        )
        title_tokens = set(normalized_title.split())
        normalized_description = " ".join(
            re.findall(r"[a-z0-9+#.]+", str(description).casefold())
        )
        description_tokens = set(normalized_description.split())
        best = (0.0, None, "none")
        for role_phrase, tokens, target_role in role_signatures:
            if role_phrase and role_phrase in normalized_title:
                candidate = (1.0, target_role, "title_phrase")
            else:
                title_coverage = len(tokens & title_tokens) / max(1, len(tokens))
                candidate = (title_coverage * 0.88, target_role, "title_tokens")
            if candidate[0] > best[0]:
                best = candidate
            if role_phrase and role_phrase in normalized_description:
                candidate = (0.78, target_role, "description_phrase")
            else:
                description_coverage = len(tokens & description_tokens) / max(
                    1, len(tokens)
                )
                candidate = (
                    description_coverage * 0.68,
                    target_role,
                    "description_tokens",
                )
            if candidate[0] > best[0]:
                best = candidate

        return best

    role_evidence = out.apply(
        lambda row: target_score(row.get("title", ""), row.get("description", "")),
        axis=1,
    )
    out["target_role_score"] = role_evidence.apply(lambda item: item[0])
    out["matched_target_role"] = role_evidence.apply(lambda item: item[1])
    out["role_match_method"] = role_evidence.apply(lambda item: item[2])
    out["match_lane"] = np.where(out["target_role_score"] >= 0.75, "primary", "broader")
    return out


def _apply_semantic_gates(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    out = df.copy()
    ranking = cfg.get("ranking", {})
    min_sem = ranking.get("min_semantic_score", 0.20)
    rescue_sem = ranking.get("broader_match_semantic_score", 0.18)
    primary = out["semantic_score"] >= min_sem
    rescue = (out["semantic_score"] >= rescue_sem) & (
        (out.get("target_role_score", 0.0) >= 0.75) | (out.get("skill_overlap", 0) >= 2)
    )
    out = out.loc[primary | rescue].copy()
    if "match_lane" in out:
        out.loc[~primary.loc[out.index], "match_lane"] = "broader"
    return out


def _apply_additive_scoring(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    df = df.copy()
    df["skills_score"] = df.apply(
        lambda r: skills_score_0_100(
            r["semantic_score"],
            r["skill_overlap"],
            int(r.get("required_skill_overlap", 0)),
            int(r.get("preferred_skill_overlap", 0)),
        ),
        axis=1,
    )
    df["company_score"] = df.apply(
        lambda row: (
            float(row["ai_company_score"])
            if pd.notna(row.get("ai_company_score"))
            else company_score_0_100(row["company_tier"])
        ),
        axis=1,
    )
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
    return df


def _apply_role_lane_cap(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    if "match_lane" not in df or "final_score" not in df:
        return df
    out = df.copy()
    cap = float(cfg.get("ranking", {}).get("broader_match_score_cap", 64))
    broader = out["match_lane"] == "broader"
    out.loc[broader, "final_score"] = out.loc[broader, "final_score"].clip(upper=cap)
    return out


def _order_match_lanes(df: pd.DataFrame) -> pd.DataFrame:
    if "match_lane" not in df or "final_score" not in df:
        return df
    out = df.copy()
    out["_match_lane_priority"] = np.where(
        out["match_lane"] == "primary", 0, 1
    )
    return out.sort_values(
        ["_match_lane_priority", "final_score"],
        ascending=[True, False],
    )


def _order_ranked_jobs(
    df: pd.DataFrame, *, prioritize_primary_lane: bool
) -> pd.DataFrame:
    if prioritize_primary_lane:
        return _order_match_lanes(df)
    return df.sort_values("final_score", ascending=False)


def _build_explanation(row: pd.Series) -> dict:
    concerns: list[str] = []
    if row.get("match_lane") == "broader":
        concerns.append("Title is an adjacent rather than direct target-role match.")
    confidence = row.get("company_reputation_confidence")
    if pd.isna(confidence) or float(confidence or 0) < 0.7:
        concerns.append("Company reputation evidence is limited or unverified.")
    required_yoe_min = row.get("required_yoe_min")
    candidate_yoe = row.get("candidate_yoe")
    if (
        pd.notna(required_yoe_min)
        and pd.notna(candidate_yoe)
        and float(candidate_yoe) + 1 < float(required_yoe_min)
    ):
        concerns.append("The stated experience requirement is above your profile.")
    if row.get("feedback_value") == "not_relevant":
        concerns.append("You previously marked this role as not relevant.")
    return {
        "role_fit": {
            "lane": str(row.get("match_lane", "primary")),
            "title_similarity": round(float(row.get("target_role_score", 1.0)), 3),
            "matched_target": row.get("matched_target_role"),
            "method": str(row.get("role_match_method", "none")),
        },
        "matched_skills": list(row.get("matched_skills") or []),
        "skill_evidence": {
            "required": list(row.get("required_skills") or []),
            "preferred": list(row.get("preferred_skills") or []),
            "mentioned": list(row.get("mentioned_skills") or []),
        },
        "scores": {
            "semantic": round(float(row.get("semantic_score", 0)) * 100, 1),
            "skills": round(float(row.get("skills_score", 0)), 1),
            "company": round(float(row.get("company_score", 0)), 1),
            "seniority": round(float(row.get("seniority_score_dim", 0)), 1),
            "location": round(float(row.get("location_score", 0)), 1),
            "recency": round(float(row.get("recency_score", 0)), 1),
        },
        "concerns": concerns,
        "experience": {
            "required_min_years": (
                int(required_yoe_min) if pd.notna(required_yoe_min) else None
            ),
            "required_max_years": (
                int(row["required_yoe_max"])
                if pd.notna(row.get("required_yoe_max"))
                else None
            ),
            "candidate_years": int(candidate_yoe) if pd.notna(candidate_yoe) else None,
        },
    }


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
    resume_skills: list[str] | None = None,
) -> pd.DataFrame:
    cache = PgEmbeddingCache(db, cfg_fp)

    canon = SkillCanonicalizer(cfg)
    explicit_resume_skills = canon.canonicalize(resume_skills or [])
    job_text = (
        df["title"].fillna("").astype(str)
        + "\n"
        + df["description"].fillna("").astype(str)
    )
    skill_evidence = job_text.apply(
        lambda text: _classify_explicit_skill_matches(text, explicit_resume_skills)
    )
    df["matched_skills"] = skill_evidence.apply(lambda value: value["all"])
    df["required_skills"] = skill_evidence.apply(lambda value: value["required"])
    df["preferred_skills"] = skill_evidence.apply(lambda value: value["preferred"])
    df["mentioned_skills"] = skill_evidence.apply(lambda value: value["mentioned"])
    df["canonical_skills"] = df["matched_skills"]
    df["skill_overlap"] = df["matched_skills"].apply(len)
    df["required_skill_overlap"] = df["required_skills"].apply(len)
    df["preferred_skill_overlap"] = df["preferred_skills"].apply(len)

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
        distilled=distilled_text,
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


def _match_explicit_skills(text: str, resume_skills: set[str]) -> list[str]:
    return _classify_explicit_skill_matches(text, resume_skills)["all"]


def _classify_explicit_skill_matches(
    text: str, resume_skills: set[str]
) -> dict[str, list[str]]:
    value = str(text or "").casefold()
    buckets = {"required": [], "preferred": [], "mentioned": []}
    for skill in resume_skills:
        pattern = rf"(?<!\w){re.escape(skill.casefold())}(?!\w)"
        matches = list(re.finditer(pattern, value))
        if not matches:
            continue
        contexts = []
        for match in matches:
            start = (
                max(
                    value.rfind(".", 0, match.start()),
                    value.rfind("\n", 0, match.start()),
                )
                + 1
            )
            end_candidates = [
                position
                for position in (
                    value.find(".", match.end()),
                    value.find("\n", match.end()),
                )
                if position != -1
            ]
            end = min(end_candidates) if end_candidates else len(value)
            contexts.append(value[start:end])
        if any(
            re.search(r"\b(?:required|must have|must-have|essential|minimum)\b", context)
            for context in contexts
        ):
            buckets["required"].append(skill)
        elif any(
            re.search(r"\b(?:preferred|nice to have|nice-to-have|bonus|plus)\b", context)
            for context in contexts
        ):
            buckets["preferred"].append(skill)
        else:
            buckets["mentioned"].append(skill)
    for bucket in buckets.values():
        bucket.sort()
    buckets["all"] = sorted(
        buckets["required"] + buckets["preferred"] + buckets["mentioned"]
    )
    return buckets


async def _apply_feedback_adjustments(
    df: pd.DataFrame,
    db: AsyncSession,
    user_id: str,
    cfg: dict,
) -> pd.DataFrame:
    try:
        uuid.UUID(str(user_id))
    except ValueError:
        df["feedback_value"] = None
        return df
    result = await db.execute(
        select(JobFeedback.job_id, JobFeedback.value).where(
            JobFeedback.user_id == user_id
        )
    )
    feedback = dict(result.all())
    if not feedback:
        df["feedback_value"] = None
        return df
    out = df.copy()
    out["feedback_value"] = out["id"].map(feedback)
    ranking = cfg.get("ranking", {})
    positive_bonus = float(ranking.get("relevant_feedback_bonus", 5))
    negative_penalty = float(ranking.get("not_relevant_feedback_penalty", 35))
    out.loc[out["feedback_value"] == "relevant", "final_score"] += positive_bonus
    out.loc[out["feedback_value"] == "not_relevant", "final_score"] -= negative_penalty
    out["final_score"] = out["final_score"].clip(lower=0, upper=100)
    return out


async def score_jobs_for_user(
    db: AsyncSession,
    user_id: str,
    resume_text: str,
    config_overrides: dict | None,
    distilled_text: str | None = None,
    resume_skills: list[str] | None = None,
    prioritize_primary_lane: bool = True,
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

    df = await _compute_embeddings(
        df,
        cfg,
        db,
        ctx.config_fp,
        resume_text,
        distilled_text=distilled_text,
        resume_skills=resume_skills,
    )

    df = _apply_semantic_gates(df, cfg)
    if df.empty:
        return pd.DataFrame(columns=["final_score"])

    df["semantic_score"] *= df["skill_overlap"].apply(bounded_skill_boost)

    scorer = CompanyScorer(cfg)
    static_tiers = df["company"].apply(scorer.classify)
    df["company_tier"] = df.apply(
        lambda row: (
            f"tier_{str(row['ai_company_tier']).casefold()}"
            if str(row.get("ai_company_tier")) in {"S", "A", "B", "C"}
            else static_tiers.loc[row.name]
        ),
        axis=1,
    )
    df["location_weight"] = df["location"].apply(
        lambda value: _preference_location_weight(value, cfg)
    )
    user_yoe = cfg.get("experience", {}).get("max_yoe")
    experience_requirements = df["description"].apply(extract_required_yoe_range)
    df["required_yoe_min"] = experience_requirements.apply(
        lambda requirement: requirement.minimum_years if requirement else None
    )
    df["required_yoe_max"] = experience_requirements.apply(
        lambda requirement: requirement.maximum_years if requirement else None
    )
    df["candidate_yoe"] = user_yoe
    df["seniority_score"] = df.apply(
        lambda r: calculate_seniority_score(
            cfg,
            title=r["title"],
            description=r["description"],
            user_yoe=user_yoe,
        ),
        axis=1,
    )
    df = _apply_additive_scoring(df, cfg)
    df = _apply_role_lane_cap(df, cfg)
    df = await _apply_feedback_adjustments(df, db, user_id, cfg)
    df["explanation"] = df.apply(_build_explanation, axis=1)

    df = _order_ranked_jobs(
        df, prioritize_primary_lane=prioritize_primary_lane
    ).drop_duplicates(subset=["job_url"])
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
    df = _order_ranked_jobs(
        df.drop(
            columns=["_dedup_key", "_fuzzy_key", "_match_lane_priority"],
            errors="ignore",
        ),
        prioritize_primary_lane=prioritize_primary_lane,
    ).drop(columns=["_match_lane_priority"], errors="ignore").reset_index(drop=True)

    return df.head(TOP_N)
