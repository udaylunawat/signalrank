# batch/run.py

import logging
from datetime import datetime

import pandas as pd

from job_ranker.batch.context import resolve_context
from job_ranker.batch.ranker import rank
from job_ranker.batch.scraper import scrape

logger = logging.getLogger(__name__)


def execute(*, user, use_case, search, hours_old, force_refresh):
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
        # --------------------------------------------------
        # Optional scrape skipping
        # --------------------------------------------------
        jobs = pd.DataFrame()

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
                age_hours = (datetime.utcnow() - latest).total_seconds() / 3600
                if age_hours < hours_old:
                    logger.info(
                        "[SCRAPE] Skipping scrape (latest %.1fh ago < hours_old=%d)",
                        age_hours,
                        hours_old,
                    )
                else:
                    jobs = scrape(
                        ctx=ctx,
                        search=search,
                        hours_old=hours_old,
                        force_refresh=force_refresh,
                    )
            else:
                jobs = scrape(
                    ctx=ctx,
                    search=search,
                    hours_old=hours_old,
                    force_refresh=force_refresh,
                )
        else:
            jobs = scrape(
                ctx=ctx,
                search=search,
                hours_old=hours_old,
                force_refresh=force_refresh,
            )
        store.upsert_raw_jobs(jobs, ctx)
        store.populate_missing_skills(ctx)
        corpus = store.load_corpus(ctx)
        ranked = rank(ctx, corpus)

        store.persist_results(run_id, ranked)
        store.finalize_run(run_id, status="success")
    except Exception:
        store.finalize_run(run_id, status="failed")
        raise
