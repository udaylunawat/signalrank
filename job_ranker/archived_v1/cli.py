# ================================
# FILE: cli.py
# ================================
import argparse
import os
from datetime import datetime

from config_loader import load_effective_settings
from config_override import persist_override
from core.pipeline_context import resolve_profile_name
from llm.veto_relevance import apply_llm_veto
from logger import setup_logger
from match_engine import rank_jobs
from profiles import PROFILES
from resume_parser import load_resume
from scrape_jobs import fetch_jobs
from storage.db import JobStore
from user_context import resolve_user_context
from utils.timing import timed


def parse_list(s: str) -> list[str]:
    return [x.strip().lower() for x in s.split(",") if x.strip()]


def build_parser():
    p = argparse.ArgumentParser(prog="jobs")
    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Fetch then rank (batch, deterministic)")

    run.add_argument("--resume", required=False)
    run.add_argument("--search", required=True)
    run.add_argument("--user", required=True)
    run.add_argument("--use-case", help="Use case (optional)")
    run.add_argument("--country", default="India")
    run.add_argument("--hours-old", type=int, default=24)
    run.add_argument("--remote-only", action="store_true")
    run.add_argument("--force-refresh", action="store_true")
    run.add_argument("--exclude", default="")
    run.add_argument("--max-results", type=int, default=100)
    run.add_argument("--prefer-companies", default="")
    run.add_argument("--skip-companies", default="")
    run.add_argument(
        "--sites",
        help="Comma-separated list of sites add only (e.g. google,linkedin,indeed)",
    )

    return p


def main():
    args = build_parser().parse_args()
    logger = setup_logger()

    # --------------------------------------------------
    # USER CONTEXT
    # --------------------------------------------------
    ctx = resolve_user_context(
        user=args.user,
        use_case_override=args.use_case,
        require_resume=True,
    )

    os.environ["JOBRANKER_ROLE_CACHE_DIR"] = str(ctx.base_dir / "role_cache")

    # --------------------------------------------------
    # DUCKDB STORE (SINGLE SPINE)
    # --------------------------------------------------
    db_path = ctx.base_dir / "jobs.duckdb"
    store = JobStore(db_path)
    store.ensure_corpus_view()

    # ----------------------------------
    # Load baseline config (NO LOCK YET)
    # ----------------------------------
    effective_cfg = load_effective_settings(ctx)

    profile_name = resolve_profile_name(effective_cfg)
    profile = PROFILES[profile_name]
    profile_name = resolve_profile_name(effective_cfg)

    # ----------------------------------
    # Persist CLI intent
    # ----------------------------------
    overrides = {}

    if args.exclude:
        overrides.setdefault("profiles", {}).setdefault(profile_name, {})[
            "exclude_keywords"
        ] = parse_list(args.exclude)

    if args.skip_companies:
        overrides.setdefault("profiles", {}).setdefault(profile_name, {})[
            "deprioritized_companies"
        ] = parse_list(args.skip_companies)

    if args.prefer_companies:
        overrides.setdefault("company_scoring", {})["preferred_companies"] = parse_list(
            args.prefer_companies
        )

    if overrides:
        persist_override(ctx, overrides)

    # ----------------------------------
    # FINAL effective config (LOCK SOURCE)
    # ----------------------------------
    effective_cfg = load_effective_settings(ctx)

    from config_lock import write_settings_lock

    lock = write_settings_lock(
        ctx,
        effective_settings=effective_cfg,
        force=True,
    )

    logger.info(f"[CONFIG] settings.lock.json → fingerprint={lock['fingerprint']}")
    profile_name = resolve_profile_name(effective_cfg)
    profile = PROFILES[profile_name]

    preferences = {
        "preferred": parse_list(args.prefer_companies),
        "deprioritized": parse_list(args.skip_companies),
    }

    # --------------------------------------------------
    # FETCH (SCRAPE ONLY, NO STORAGE SIDE EFFECTS)
    # --------------------------------------------------
    search_terms = [s.strip() for s in args.search.split("|") if s.strip()]
    query = " OR ".join(f'"{t}"' for t in search_terms)

    sites = None
    if args.sites:
        sites = [s.strip().lower() for s in args.sites.split(",") if s.strip()]

    scraped_df = fetch_jobs(
        search_query=query,
        country=args.country,
        hours_old=args.hours_old,
        remote_only=args.remote_only,
        profile=profile,
        effective_settings=effective_cfg,
        force_refresh=args.force_refresh,
        results_wanted=args.max_results,
        sites=sites,
        logger=logger,
    )

    logger.info(
        f"[SCRAPE DIAG] scraped_df rows="
        f"{0 if scraped_df is None else len(scraped_df)}"
    )

    # --------------------------------------------------
    # PERSIST RAW JOBS (REPLACES CSV CACHE)
    # --------------------------------------------------
    if scraped_df is not None and not scraped_df.empty:
        store.upsert_raw_jobs(
            scraped_df,
            user=ctx.user,
            use_case=ctx.use_case,
        )

    # --------------------------------------------------
    # LOAD CORPUS (DEDUPE + USER-SCOPED)
    # --------------------------------------------------
    jobs_df = store.load_corpus(
        user=ctx.user,
        use_case=ctx.use_case,
    )

    logger.info("[DIAG] job_sources | " f"corpus_rows={len(jobs_df)}")

    if jobs_df.empty:
        logger.warning("No jobs available for ranking")
        return

    # --------------------------------------------------
    # RESUME
    # --------------------------------------------------
    resume_text = load_resume(str(ctx.resume_path))

    # --------------------------------------------------
    # RANKING (UNCHANGED LOGIC)
    # --------------------------------------------------
    ranked = rank_jobs(
        resume_text=resume_text,
        jobs_df=jobs_df,
        preferences=preferences,
        profile=profile,
        logger=logger,
        effective_settings=effective_cfg,
        ctx=ctx,
        embedding_cache_dir=str(ctx.base_dir / "embeddings"),
    )

    if ranked.empty:
        logger.warning("Ranking produced no results")
        return

    # --------------------------------------------------
    # OPTIONAL LLM RELEVANCE VETO (POST-RANK)
    # --------------------------------------------------
    veto_cfg = effective_cfg.get("ranking", {}).get("llm_veto", {})

    if (
        veto_cfg.get("enabled", False)
        and not ranked.empty
        and "description" in ranked.columns
    ):
        top_n = int(veto_cfg.get("top_n", 20))
        max_tokens = int(veto_cfg.get("model_max_tokens", 200))
        penalty = float(veto_cfg.get("penalty_multiplier", 0.65))

        logger.info(f"[LLM VETO] Evaluating top {top_n} jobs")

        slice_df = ranked.head(top_n).copy()
        resume_skills = ranked.attrs.get("canonical_resume_skills", [])
        resume_summary = " ".join(resume_skills)

        with timed(f"LLM veto (top {top_n})", logger):
            profile_intent = effective_cfg.get("profile_intent", {}).get("preset", "")

            veto_flags = apply_llm_veto(
                resume_summary=resume_summary,
                job_descriptions=slice_df["description"].fillna("").tolist(),
                role_intent=profile_intent,
                max_tokens=max_tokens,
                logger=logger,
            )

        vetoed = 0
        for i, allowed in enumerate(veto_flags):
            ranked.at[i, "vetoed"] = not allowed
            if not allowed:
                ranked.at[i, "final_score"] *= penalty
                vetoed += 1

        logger.info(f"[LLM VETO] Penalized {vetoed} jobs")

        ranked = ranked.sort_values(
            "final_score",
            ascending=False,
        ).reset_index(drop=True)

    # --------------------------------------------------
    # WRITE SNAPSHOT (DUCKDB, NOT FILESYSTEM)
    # --------------------------------------------------
    run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    store.write_ranked_snapshot(
        run_id=run_id,
        user=ctx.user,
        use_case=ctx.use_case,
        df=ranked,
    )

    logger.info(f"[RANK] Snapshot stored (run_id={run_id})")


if __name__ == "__main__":
    main()
