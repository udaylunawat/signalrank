# ================================
# FILE: cli.py
# ================================
import os
import sitecustomize
import argparse
from pathlib import Path

from logger import setup_logger
from profiles import PROFILES
from resume_parser import load_resume
from scrape_jobs import fetch_jobs
from match_engine import rank_jobs
from cache_loader import load_all_cached_jobs
from config_loader import load_effective_settings
from user_context import resolve_user_context


def parse_list(s: str) -> list[str]:
    return [x.strip().lower() for x in s.split(",") if x.strip()]


def resolve_profile_name(effective_cfg: dict) -> str:
    """
    Single source of truth for profile resolution.
    """
    profiles_cfg = effective_cfg.get("profiles", {})
    if len(profiles_cfg) == 1:
        return next(iter(profiles_cfg.keys()))
    return "senior_ic"


def build_parser():
    p = argparse.ArgumentParser(prog="jobs")
    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Fetch then rank")

    run.add_argument("--resume", required=False)
    run.add_argument("--search", required=True)
    run.add_argument("--user", required=True)
    run.add_argument("--use-case", help="Use case (optional)")

    # backward-compatible but NOT authoritative
    run.add_argument(
        "--profile",
        help="(Ignored) Profile is resolved from settings.override.yaml",
    )

    run.add_argument("--country", default="India")
    run.add_argument("--hours-old", type=int, default=24)
    run.add_argument("--remote-only", action="store_true")
    run.add_argument("--force-refresh", action="store_true")
    run.add_argument("--exclude", default="")
    run.add_argument("--max-results", type=int, default=100)
    run.add_argument("--prefer-companies", default="")
    run.add_argument("--skip-companies", default="")

    run.add_argument("--rank-corpus", action="store_true")
    run.add_argument("--scratch", action="store_true")
    run.add_argument("--scratch-hours", type=int, default=24)

    return p


def main():
    args = build_parser().parse_args()
    logger = setup_logger()

    if args.scratch and args.rank_corpus:
        raise ValueError("--rank-corpus not allowed with --scratch")

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
    # LOAD EFFECTIVE CONFIG
    # --------------------------------------------------
    effective_cfg = load_effective_settings(ctx)
    profile_name = resolve_profile_name(effective_cfg)

    if profile_name not in PROFILES:
        raise SystemExit(f"Unknown profile: {profile_name}")

    profile = PROFILES[profile_name]
    profile.workspace_dir = str(ctx.base_dir / "workspace")
    Path(profile.workspace_dir).mkdir(parents=True, exist_ok=True)

    logger.info(
        f"[CLI] Using profile={profile_name} (resolved from config)"
    )

    # --------------------------------------------------
    # CLI OVERRIDES (SCORING ONLY)
    # --------------------------------------------------
    prefer_override = parse_list(args.prefer_companies)
    skip_override = parse_list(args.skip_companies)
    profile.exclude_keywords = parse_list(args.exclude)

    # --------------------------------------------------
    # FETCH
    # --------------------------------------------------
    search_terms = [s.strip() for s in args.search.split("|") if s.strip()]
    query = " OR ".join(f'"{t}"' for t in search_terms)
    hours = args.scratch_hours if args.scratch else args.hours_old

    fetch_jobs(
        search_query=query,
        country=args.country,
        hours_old=hours,
        remote_only=args.remote_only,
        profile=profile,
        effective_settings=effective_cfg,
        force_refresh=args.force_refresh,
        results_wanted=args.max_results,
        logger=logger,
    )

    # --------------------------------------------------
    # LOAD JOBS
    # --------------------------------------------------
    os.environ["JOBRANKER_CACHE_DIR"] = str(ctx.cache_dir)
    jobs_df = load_all_cached_jobs(logger)

    # --------------------------------------------------
    # RANK
    # --------------------------------------------------
    resume_text = load_resume(str(ctx.resume_path))

    ranked = rank_jobs(
        resume_text=resume_text,
        jobs_df=jobs_df,
        preferences={
            "preferred": prefer_override,
            "deprioritized": skip_override,
        },
        profile=profile,
        logger=logger,
        effective_settings=effective_cfg,
        embedding_cache_dir=str(ctx.base_dir / "embeddings"),
    )

    # --------------------------------------------------
    # OUTPUT
    # --------------------------------------------------
    if args.scratch:
        out_dir = ctx.base_dir / "scratch"
        out_dir.mkdir(exist_ok=True)
    else:
        out_dir = ctx.outputs_dir

    output_path = out_dir / "ranked_jobs.csv"
    ranked.to_csv(output_path, index=False)
    state_path = ctx.outputs_dir / ".last_seen_jobs.csv"
    ranked[["job_url"]].dropna().to_csv(state_path, index=False)
    logger.info(f"Saved {output_path}")


if __name__ == "__main__":
    main()