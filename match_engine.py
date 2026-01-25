# match_engine.py
import json
import re
from pathlib import Path
from typing import List

import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from company_scoring import CompanyScorer
from profiles import Profile
from skill_normalizer import normalize_text
from llm.normalize_skills import normalize_skills_batch
from llm.explain_match import explain_match
from llm.distill_resume import distill_resume
from llm.classify_functional_role import classify_functional_roles_batch

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
from config import (
    MIN_SEMANTIC_SCORE,
    UNKNOWN_COMPANY_PENALTY,
    YOE_MISMATCH_PENALTY,
    TOP_K_EXPLAIN,
)

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

# ---------------- Utilities ----------------

def normalize_title(title: str) -> str:
    t = title.lower()
    t = re.sub(r"[^a-z ]+", " ", t)
    t = re.sub(r"\b(sr|senior|lead|principal|staff)\b", "", t)
    return re.sub(r"\s+", " ", t).strip()


def extract_max_yoe(text: str) -> int | None:
    matches = re.findall(r"(\d+)\s*\+?\s*years", text.lower())
    return max(map(int, matches)) if matches else None


def binary_job_quality(row: pd.Series) -> float:
    if len(row["description"]) < 800:
        return 0.85
    if any(x in row["title"].lower() for x in ["intern", "junior", "trainee"]):
        return 0.0
    return 1.0


def _align_skills_length(
    skills: List[List[str]],
    target_len: int,
    logger,
) -> List[List[str]]:
    """
    HARD INVARIANT:
    len(skills) MUST equal target_len.
    """
    if len(skills) == target_len:
        return skills

    logger.warning(
        f"Skill normalization length mismatch: "
        f"{len(skills)} vs {target_len}. Applying fallback."
    )

    if len(skills) > target_len:
        return skills[:target_len]

    # pad with empty skill lists
    return skills + [[] for _ in range(target_len - len(skills))]

AI_TERMS = {
    "llm", "agent", "rag", "embedding",
    "prompt", "inference", "evaluation",
    "retrieval", "orchestration",
}

def ai_density_penalty(text: str) -> float:
    tokens = text.lower().split()
    if not tokens:
        return 0.7
    hits = sum(1 for t in tokens if t in AI_TERMS)
    density = hits / len(tokens)
    if density < 0.002:
        return 0.6
    if density < 0.005:
        return 0.8
    return 1.0

# ---------------- Main ----------------

def rank_jobs(
    resume_text: str,
    jobs_df: pd.DataFrame,
    preferences: dict,
    profile: Profile,
    logger,
):
    if jobs_df.empty:
        return jobs_df

    jobs_df = jobs_df.copy()

    # ---------- Resume distillation ----------
    workspace = Path(profile.workspace_dir)
    workspace.mkdir(parents=True, exist_ok=True)
    distilled_path = workspace / "resume_distilled.json"

    if distilled_path.exists():
        distilled = json.loads(distilled_path.read_text())
    else:
        distilled = distill_resume(resume_text)
        distilled_path.write_text(json.dumps(distilled, indent=2))

    resume_caps = distilled.get("core_capabilities", [])
    non_focus = set(distilled.get("non_focus", []))

    resume_embed_text = (
        "AI agentic systems, LLM pipelines, ML lifecycle ownership, inference, evaluation, orchestration. "
        + ", ".join(resume_caps)
    )

    # ---------- Skill normalization ----------
    descriptions = jobs_df["description"].fillna("").tolist()

    raw_skills = normalize_skills_batch(
        descriptions,
        batch_size=8,
        logger=logger,
    )

    job_skills = _align_skills_length(
        raw_skills,
        target_len=len(jobs_df),
        logger=logger,
    )

    jobs_df["__skills"] = job_skills

    job_texts = [
        " ".join(s) if s else normalize_text(d)
        for s, d in zip(job_skills, descriptions)
    ]

    # ---------- Embeddings ----------
    model = SentenceTransformer(MODEL_NAME)
    r_emb = model.encode([resume_embed_text], normalize_embeddings=True)
    j_emb = model.encode(job_texts, normalize_embeddings=True)

    jobs_df["semantic_score"] = cosine_similarity(r_emb, j_emb)[0]
    jobs_df = jobs_df[jobs_df["semantic_score"] >= MIN_SEMANTIC_SCORE]

    if jobs_df.empty:
        return jobs_df

    # ---------- Functional role classification ----------
    jobs_df["functional_role"] = classify_functional_roles_batch(
        jobs_df["title"].fillna("").tolist(),
        logger=logger,
    )

    jobs_df["role_weight"] = jobs_df["functional_role"].map(
        ROLE_WEIGHT
    ).fillna(0.5)

    # ---------- Company scoring ----------
    scorer = CompanyScorer(
        preferred=preferences.get("preferred", []),
        deprioritized=preferences.get("deprioritized", []),
    )

    jobs_df["company_weight"] = jobs_df["company"].apply(scorer.score)

    # ---------- YoE mismatch ----------
    jobs_df["max_yoe"] = jobs_df["description"].apply(extract_max_yoe)
    jobs_df.loc[
        jobs_df["max_yoe"].fillna(0) >= 12,
        "semantic_score",
    ] *= YOE_MISMATCH_PENALTY

    # ---------- Non-focus penalty ----------
    def non_focus_penalty(job_skills):
        overlap = set(job_skills or []) & non_focus
        if len(overlap) >= 3:
            return 0.6
        if len(overlap) >= 1:
            return 0.8
        return 1.0

    jobs_df["non_focus_penalty"] = jobs_df["__skills"].apply(non_focus_penalty)

    # ---------- Job quality ----------
    jobs_df["quality_score"] = jobs_df.apply(binary_job_quality, axis=1)

    # ---------- Final score ----------
    jobs_df["final_score"] = (
        jobs_df["semantic_score"]
        * jobs_df["company_weight"]
        * jobs_df["quality_score"]
        * jobs_df["role_weight"]
        * jobs_df["non_focus_penalty"]
    )

    # ---------- AI density penalty (kills infra-only roles) ----------
    jobs_df["ai_density_penalty"] = jobs_df["description"].apply(ai_density_penalty)
    jobs_df["final_score"] *= jobs_df["ai_density_penalty"]

    ranked = jobs_df.sort_values("final_score", ascending=False).reset_index(drop=True)

    # ---------- Explanations ----------
    ranked["explanation"] = ranked.apply(
        lambda r: (
            f"Role={r.functional_role}, "
            f"semantic={r.semantic_score:.2f}, "
            f"role_wt={r.role_weight:.2f}"
        ),
        axis=1,
    )

    if profile.use_llm_explanations and resume_caps:
        for i in range(min(TOP_K_EXPLAIN, len(ranked))):
            ranked.at[i, "explanation"] = explain_match(
                resume_caps, ranked.at[i, "__skills"]
            )

    return ranked