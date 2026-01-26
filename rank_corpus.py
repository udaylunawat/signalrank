#!/usr/bin/env python3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from logger import setup_logger
from resume_parser import load_resume
from match_engine import rank_jobs, EMBED_DIM
from profiles import PROFILES
from embeddings.embedding_cache import EmbeddingCache

logger = setup_logger()

CORPUS_PATH = PROJECT_ROOT / "corpus" / "jobs_corpus.csv"
FAISS_DIR = PROJECT_ROOT / "corpus" / "faiss"   # 🔑 IMPORTANT
OUTPUT_PATH = PROJECT_ROOT / "outputs" / "ranked_corpus.csv"


def main():
    if not CORPUS_PATH.exists():
        logger.error("jobs_corpus.csv not found. Run build_corpus.py first.")
        return

    df = pd.read_csv(CORPUS_PATH)
    if df.empty:
        logger.error("Corpus is empty")
        return

    logger.info(f"[CORPUS RANK] Ranking {len(df)} corpus jobs")

    # --------------------------------------------------
    # SAFETY: ensure NO embedding happens here
    # --------------------------------------------------
    texts = (
        df["title"].fillna("") + " "
        + df["company"].fillna("") + " "
        + df["description"].fillna("").str.slice(0, 2000)
    ).tolist()

    cache = EmbeddingCache(
        dim=EMBED_DIM,
        cache_dir=str(FAISS_DIR),   # 🔑 SAME AS build_faiss_corpus.py
        logger=logger,
    )

    found, missing = cache.lookup(texts)

    if missing:
        logger.error(
            f"[CORPUS RANK] {len(missing)} embeddings missing.\n"
            "Run this first:\n\n"
            "  python build_faiss_corpus.py\n\n"
            "Corpus ranking is read-only by design."
        )
        return

    # --------------------------------------------------
    # Rank (read-only, no embedding)
    # --------------------------------------------------
    profile = PROFILES["senior_ic"]
    profile.workspace_dir = "workspaces/example/Senior IC"

    resume_path = PROJECT_ROOT / "users/Example_Candidate/resume.tex"
    resume_text = load_resume(str(resume_path))

    ranked = rank_jobs(
        resume_text=resume_text,
        jobs_df=df,
        preferences={
            "preferred": profile.preferred_companies,
            "deprioritized": profile.deprioritized_companies,
        },
        profile=profile,
        logger=logger,
        allow_embedding=False,
        embedding_cache_dir=str(FAISS_DIR),   # ← CRITICAL
    )

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    ranked.to_csv(OUTPUT_PATH, index=False)

    logger.info(f"[CORPUS RANK] Saved → {OUTPUT_PATH}")


if __name__ == "__main__":
    main()