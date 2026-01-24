import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from resume_parser import latex_to_text
from scrape_jobs import fetch_jobs
from company_scoring import CompanyScorer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
COMPANY_CONFIG_PATH = "config/company_tiers.yaml"


def embed_texts(texts, model):
    return model.encode(texts, normalize_embeddings=True)


def main():
    print("Loading resume...")
    resume_text = latex_to_text("./users/Example_Candidate/resume.tex")

    print("Fetching jobs...")
    jobs_df = fetch_jobs()

    if jobs_df.empty:
        print("No jobs fetched. Exiting.")
        return

    print(f"Fetched {len(jobs_df)} jobs")

    job_texts = (
        jobs_df["title"].fillna("") + ". " +
        jobs_df["description"].fillna("")
    ).tolist()

    print("Loading embedding model...")
    model = SentenceTransformer(MODEL_NAME)

    print("Embedding resume and job descriptions...")
    resume_embedding = embed_texts([resume_text], model)
    job_embeddings = embed_texts(job_texts, model)

    print("Computing semantic similarity...")
    semantic_scores = cosine_similarity(resume_embedding, job_embeddings)[0]
    jobs_df["semantic_score"] = semantic_scores

    print("Loading company scoring rules...")
    scorer = CompanyScorer(COMPANY_CONFIG_PATH)

    print("Applying company weights...")
    jobs_df["company_weight"] = jobs_df["company"].apply(scorer.score)

    jobs_df["final_score"] = (
        jobs_df["semantic_score"] * jobs_df["company_weight"]
    )

    ranked = jobs_df.sort_values("final_score", ascending=False)

    output_cols = [
        "site",
        "title",
        "company",
        "location",
        "job_url",
        "semantic_score",
        "company_weight",
        "final_score",
    ]

    ranked[output_cols].head(50).to_csv("ranked_jobs.csv", index=False)

    print("\nTop calm-aligned roles:")
    print(
        ranked[["title", "company", "final_score"]]
        .head(10)
        .to_string(index=False)
    )

    print("\nSaved ranked_jobs.csv")


if __name__ == "__main__":
    main()