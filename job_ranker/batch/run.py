# batch/run.py

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from job_ranker.batch.context import resolve_context
from job_ranker.batch.enrich import enrich_linkedin_jobs
from job_ranker.batch.ranker import rank
from job_ranker.batch.scraper import scrape

logger = logging.getLogger(__name__)


def _normalize_csv_schema(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure CSV matches jobs_raw schema expectations.
    Safe, defensive normalization.
    """

    expected_cols = [
        "job_url",
        "job_url_direct",
        "title",
        "company",
        "description",
        "location",
        "site",
        "date_posted",
    ]

    df = df.copy()

    for col in expected_cols:
        if col not in df.columns:
            df[col] = None

    df = df[expected_cols]

    # Normalize string fields
    for col in ["title", "company", "description", "location", "site"]:
        df[col] = df[col].fillna("").astype(str)

    return df


def execute(
    *,
    user,
    use_case,
    search,
    hours_old,
    force_refresh,
    no_scrape=False,
    csv_path=None,
    jobspy_only=False,
    skip_enrich=False,
    skip_ai_analysis: bool = False,
):
    ctx = resolve_context(user, use_case)

    # --------------------------------------------------
    # Acquire writer (run-scoped)
    # --------------------------------------------------
    try:
        from job_ranker.storage.store import Store

        store = Store(ctx.db_path)
    except Exception as e:
        raise RuntimeError(
            "\n"
            "❌ Cannot start batch run.\n\n"
            "Reason: another batch run is already active.\n\n"
            "Notes:\n"
            "- Streamlit UI does NOT block batch runs\n"
            "- Only one batch run may write at a time\n\n"
            "Original error:\n"
            f"{e}"
        ) from e

    run_id = store.create_run(ctx)

    try:
        jobs = pd.DataFrame()

        # ==================================================
        # CSV MODE (HIGHEST PRIORITY)
        # ==================================================
        if csv_path:
            path = Path(csv_path)

            if not path.exists():
                raise RuntimeError(f"CSV file not found: {csv_path}")

            logger.info("[CSV] Loading pre-scraped CSV: %s", csv_path)

            jobs = pd.read_csv(path)
            jobs = _normalize_csv_schema(jobs)

            logger.info("[CSV] Loaded %d rows", len(jobs))

        # ==================================================
        # SCRAPE MODE
        # ==================================================
        elif no_scrape:
            logger.info("[SCRAPE] Explicitly disabled via --no-scrape")

        else:
            should_scrape = force_refresh

            if not force_refresh:
                latest = store.con.execute(
                    """
                    SELECT MAX(ingested_at)
                    FROM jobs_raw
                    WHERE user = ? AND use_case = ?
                    """,
                    [ctx.user, ctx.use_case],
                ).fetchone()[0]

                if latest:
                    age_hours = (
                        datetime.utcnow() - latest
                    ).total_seconds() / 3600

                    if age_hours >= hours_old:
                        should_scrape = True
                    else:
                        logger.info(
                            "[SCRAPE] Skipping scrape "
                            "(latest %.1fh ago < hours_old=%d)",
                            age_hours,
                            hours_old,
                        )
                else:
                    logger.info("[SCRAPE] No existing data found")
                    should_scrape = True

            if should_scrape:
                jobs = scrape(
                    ctx=ctx,
                    search=search,
                    hours_old=hours_old,
                    force_refresh=force_refresh,
                    jobspy_only=jobspy_only,
                )

        # ==================================================
        # INGEST (safe even if empty)
        # ==================================================
        if not jobs.empty:
            logger.info("[INGEST] Inserting %d jobs", len(jobs))
            store.upsert_raw_jobs(jobs, ctx)
        else:
            logger.info("[INGEST] No new jobs to insert")

        # ==================================================
        # ENRICH empty descriptions (LinkedIn public pages)
        # ==================================================
        if skip_enrich:
            logger.info("[ENRICH] Skipped (--skip-enrich flag set)")
        else:
            enriched = enrich_linkedin_jobs(store.con)
            if enriched:
                logger.info("[ENRICH] Enriched %d job descriptions", enriched)

        # ==================================================
        # RANKING + EMBEDDING PHASE
        # ==================================================
        store.populate_missing_skills(ctx)

        corpus = store.load_corpus(ctx)

        if corpus.empty:
            logger.warning("[RANK] No jobs available in corpus")
        else:
            logger.info("[RANK] Ranking %d jobs", len(corpus))
            ranked = rank(ctx, corpus)
            store.persist_results(run_id, ranked)
            logger.info("[RANK] Persisted %d ranked results", len(ranked))

            # ==================================================
            # AI CONFIG ADVISOR (optional, non-blocking)
            # ==================================================
            if not skip_ai_analysis:
                try:
                    from job_ranker.llm.config_advisor import run_advisor
                    reports_dir = Path(__file__).resolve().parents[2] / "reports"
                    run_advisor(
                        ranked_df=ranked,
                        resume_text=ctx.resume_text,
                        run_id=run_id,
                        config=ctx.config,
                        reports_dir=reports_dir,
                    )
                except Exception as e:
                    logger.warning("[ADVISOR] Failed (non-fatal): %s", e)

        store.finalize_run(run_id, status="success")

    except Exception:
        store.finalize_run(run_id, status="failed")
        raise