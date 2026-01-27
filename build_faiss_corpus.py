#!/usr/bin/env python3
# ================================
# FILE: build_faiss_corpus.py
# ================================
import argparse
from pathlib import Path
import pandas as pd

from sentence_transformers import SentenceTransformer

from embeddings.embedding_cache import EmbeddingCache
from logger import setup_logger
from config_loader import settings, load_effective_settings, fingerprint_settings
from user_context import resolve_user_context

logger = setup_logger()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", help="User name (required)")
    parser.add_argument("--use-case", help="Use case (optional)")
    args = parser.parse_args()

    # --------------------------------------------------
    # USER-SCOPED ONLY
    # --------------------------------------------------
    if not args.user:
        raise SystemExit(
            "ERROR: --user is required for FAISS corpus build.\n"
            "Global / legacy embeddings are no longer supported."
        )

    ctx = resolve_user_context(
        user=args.user,
        use_case_override=args.use_case,
    )

    corpus_path = ctx.corpus_dir / "jobs_corpus.csv"
    faiss_dir = ctx.base_dir / "embeddings"
    faiss_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"[FAISS] Using user-scoped embeddings → {faiss_dir}")

    if not corpus_path.exists():
        logger.error(f"{corpus_path} not found. Run build_corpus.py first.")
        return

    df = pd.read_csv(corpus_path)
    if df.empty:
        logger.error("Corpus is empty")
        return

    logger.info(f"[FAISS] Building embeddings for {len(df)} corpus jobs")

    # --------------------------------------------------
    # LOAD EFFECTIVE CONFIG (MERGED)
    # --------------------------------------------------
    effective_settings = load_effective_settings(ctx)
    cfg_fp = fingerprint_settings(effective_settings)

    # --------------------------------------------------
    # SKILL EXTRACTION + CANONICALIZATION
    # MUST MATCH rank_jobs() EXACTLY
    # --------------------------------------------------
    from skills.canonicalizer import build_canonical_texts

    canonical_texts, _ = build_canonical_texts(
        df["description"].fillna("").tolist(),
        effective_settings=effective_settings,
        cfg_fingerprint=cfg_fp,
    )

    # --------------------------------------------------
    # EMBEDDINGS
    # --------------------------------------------------
    model = SentenceTransformer(
        settings.embeddings.model_name,
        device=settings.embeddings.device,
    )

    cache = EmbeddingCache(
        dim=settings.embeddings.embedding_dim,
        cache_dir=str(faiss_dir),
        cfg_fingerprint=cfg_fp,
        logger=logger,
    )

    found, missing = cache.lookup(canonical_texts)

    if missing:
        logger.info(f"[FAISS] Embedding {len(missing)} new corpus rows")
        batch = [canonical_texts[i] for i in missing]
        vecs = model.encode(
            batch,
            normalize_embeddings=settings.embeddings.text.normalize_embeddings,
            show_progress_bar=True,
        ).astype("float32")
        cache.add(batch, vecs)

    logger.info("[FAISS] Corpus FAISS snapshot ready")


if __name__ == "__main__":
    main()