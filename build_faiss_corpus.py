#!/usr/bin/env python3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from sentence_transformers import SentenceTransformer
from embeddings.embedding_cache import EmbeddingCache
from logger import setup_logger
from match_engine import MODEL_NAME, EMBED_DIM
from llm.normalize_skills import normalize_skills_batch

logger = setup_logger()

CORPUS_PATH = PROJECT_ROOT / "corpus" / "jobs_corpus.csv"
FAISS_DIR = PROJECT_ROOT / "corpus" / "faiss"
FAISS_DIR.mkdir(parents=True, exist_ok=True)


def main():
    if not CORPUS_PATH.exists():
        logger.error("jobs_corpus.csv not found. Run build_corpus.py first.")
        return

    df = pd.read_csv(CORPUS_PATH)
    if df.empty:
        logger.error("Corpus is empty")
        return

    # --------------------------------------------------
    # IMPORTANT: build embeddings from SAME text as rank_jobs
    # --------------------------------------------------
    skills = normalize_skills_batch(
        df["description"].fillna("").tolist(),
        logger=logger,
    )

    texts = [" ".join(s) for s in skills]

    logger.info(f"Building FAISS corpus index for {len(texts)} jobs")

    model = SentenceTransformer(MODEL_NAME, device="cpu")
    cache = EmbeddingCache(
        dim=EMBED_DIM,
        cache_dir=str(FAISS_DIR),
        logger=logger,
    )

    found, missing = cache.lookup(texts)

    if missing:
        logger.info(f"Embedding {len(missing)} new corpus rows")
        batch = [texts[i] for i in missing]

        vecs = model.encode(
            batch,
            normalize_embeddings=True,
            show_progress_bar=True,
        ).astype("float32")

        cache.add(batch, vecs)

    logger.info("Corpus FAISS snapshot ready")


if __name__ == "__main__":
    main()