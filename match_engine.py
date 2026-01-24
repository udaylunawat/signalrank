import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from company_scoring import CompanyScorer
from profiles import Profile
from skill_normalizer import normalize_text

from llm.normalize_skills import normalize_skills_batch
from llm.explain_mathc import explain_match, explain_no_match

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
TOP_K_EXPLAIN = 5


def rank_jobs(
    resume_text: str,
    jobs_df: pd.DataFrame,
    preferences: dict,
    profile: Profile,
    logger,
):
    if jobs_df.empty:
        logger.warning("No jobs to rank")
        return jobs_df

    logger.info(f"Ranking with profile: {profile.name}")

    # --------------------------------------------------
    # 1. Skill normalization (batched, cached)
    # --------------------------------------------------
    if profile.use_llm_skill_norm:
        logger.info("Normalizing resume skills (LLM, cached)")
        resume_skills = normalize_skills_batch([resume_text])[0]

        logger.info("Normalizing job skills (batched LLM)")
        job_skills = normalize_skills_batch(
            jobs_df["description"].fillna("").tolist(),
            batch_size=8,
            logger=logger,
        )

        jobs_df["__skills"] = job_skills
        resume_embed_text = " ".join(resume_skills)
        job_texts = [" ".join(s) for s in job_skills]
    else:
        resume_embed_text = normalize_text(resume_text)
        job_texts = jobs_df["description"].apply(normalize_text).tolist()
        jobs_df["__skills"] = [[] for _ in range(len(jobs_df))]
        resume_skills = []

    # --------------------------------------------------
    # 2. Embedding + deterministic scoring
    # --------------------------------------------------
    model = SentenceTransformer(MODEL_NAME)

    r_emb = model.encode([resume_embed_text], normalize_embeddings=True)
    j_emb = model.encode(job_texts, normalize_embeddings=True)

    jobs_df["semantic_score"] = cosine_similarity(r_emb, j_emb)[0]

    scorer = CompanyScorer(
        preferred=preferences.get("preferred", []),
        deprioritized=preferences.get("deprioritized", []),
    )
    jobs_df["company_weight"] = jobs_df["company"].apply(scorer.score)

    jobs_df["final_score"] = (
        jobs_df["semantic_score"] * jobs_df["company_weight"]
    )

    ranked = jobs_df.sort_values("final_score", ascending=False).reset_index(drop=True)

    # --------------------------------------------------
    # 3. Deterministic explanations (always available)
    # --------------------------------------------------
    ranked["explanation"] = ranked.apply(
        lambda r: f"Skill similarity {r.semantic_score:.2f}, company weight {r.company_weight:.2f}",
        axis=1,
    )
    ranked["why_not_matched"] = ""

    # --------------------------------------------------
    # 4. LLM explanations (top + bottom only)
    # --------------------------------------------------
    if profile.use_llm_explanations:
        logger.info("Generating LLM explanations (top/bottom only)")

        # top-K matches
        for i in range(min(TOP_K_EXPLAIN, len(ranked))):
            row = ranked.iloc[i]
            try:
                ranked.at[i, "explanation"] = explain_match(
                    resume_skills, row["__skills"]
                )
            except Exception as e:
                logger.debug(f"LLM match explain failed: {e}")

        # bottom-K non-matches
        for i in range(max(0, len(ranked) - TOP_K_EXPLAIN), len(ranked)):
            row = ranked.iloc[i]
            try:
                ranked.at[i, "why_not_matched"] = explain_no_match(
                    resume_skills, row["__skills"]
                )
            except Exception as e:
                logger.debug(f"LLM no-match explain failed: {e}")

    return ranked