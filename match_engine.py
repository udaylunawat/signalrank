import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from company_scoring import CompanyScorer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def rank_jobs(resume_text: str, jobs_df: pd.DataFrame, preferences: dict, logger):
    if jobs_df.empty:
        logger.warning("No jobs to rank")
        return jobs_df

    model = SentenceTransformer(MODEL_NAME)

    job_texts = (
        jobs_df["title"].fillna("") + ". " +
        jobs_df["description"].fillna("")
    ).tolist()

    logger.info("Embedding resume")
    resume_emb = model.encode([resume_text], normalize_embeddings=True)

    logger.info("Embedding job descriptions")
    job_embs = model.encode(job_texts, normalize_embeddings=True)

    jobs_df["semantic_score"] = cosine_similarity(
        resume_emb, job_embs
    )[0]

    scorer = CompanyScorer(preferences)
    jobs_df["company_weight"] = jobs_df["company"].apply(scorer.score)

    jobs_df["final_score"] = (
        jobs_df["semantic_score"] * jobs_df["company_weight"]
    )

    jobs_df["explanation"] = jobs_df.apply(
        lambda r: (
            f"Semantic match {r.semantic_score:.2f} × "
            f"Company weight {r.company_weight:.2f}"
        ),
        axis=1,
    )

    return jobs_df.sort_values("final_score", ascending=False)