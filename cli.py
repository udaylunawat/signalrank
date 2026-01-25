# cli.py
import sitecustomize
import argparse
from pathlib import Path

from logger import setup_logger
from profiles import PROFILES
from resume_parser import load_resume
from scrape_jobs import fetch_jobs
from match_engine import rank_jobs
from cache_loader import load_all_cached_jobs
from config import DEFAULT_COUNTRY, DEFAULT_HOURS_OLD


def build_parser():
    p = argparse.ArgumentParser(prog="jobs")
    sub = p.add_subparsers(dest="cmd", required=True)

    # ---------- fetch ----------
    f = sub.add_parser("fetch", help="Fetch and cache jobs")
    f.add_argument("--search", required=True)
    f.add_argument("--country", default=DEFAULT_COUNTRY)
    f.add_argument("--hours-old", type=int, default=DEFAULT_HOURS_OLD)
    f.add_argument("--remote-only", action="store_true")
    f.add_argument("--profile", choices=PROFILES.keys(), default="senior_ic")
    f.add_argument("--force-refresh", action="store_true")

    # ---------- rank ----------
    r = sub.add_parser("rank", help="Rank cached jobs")
    r.add_argument("--resume", required=True)
    r.add_argument("--user", required=True)
    r.add_argument("--profile", choices=PROFILES.keys(), default="senior_ic")
    r.add_argument("--min-score", type=float, default=0.25)
    r.add_argument("--max-results", type=int, default=30)

    # ---------- exclude ----------
    f.add_argument(
        "--exclude",
        default="",
        help="Comma-separated keywords to exclude (e.g. java,spark,big data,cyber)",
    )
    f.add_argument(
        "--max-results",
        type=int,
        default=100,
        help="Maximum jobs to fetch per query",
    )
    # ---------- run ----------
    run = sub.add_parser("run", help="Fetch then rank")
    run.add_argument("--resume", required=True)
    run.add_argument("--search", required=True)
    run.add_argument("--user", required=True)
    run.add_argument("--profile", choices=PROFILES.keys(), default="senior_ic")
    run.add_argument("--country", default=DEFAULT_COUNTRY)
    run.add_argument("--hours-old", type=int, default=DEFAULT_HOURS_OLD)
    run.add_argument("--remote-only", action="store_true")
    run.add_argument("--force-refresh", action="store_true")
    run.add_argument(
        "--exclude",
        default="",
        help="Comma-separated keywords to exclude (e.g. java,spark,big data,cyber)",
    )
    run.add_argument(
        "--max-results",
        type=int,
        default=100,
    )
    return p


def main():
    args = build_parser().parse_args()
    logger = setup_logger()

    if args.cmd == "fetch":
        profile = PROFILES[args.profile]
        search_terms = [s.strip() for s in args.search.split("|") if s.strip()]
        query = " OR ".join(f'"{t}"' for t in search_terms)
        exclude_keywords = [
            k.strip().lower()
            for k in args.exclude.split(",")
            if k.strip()
        ]

        profile.exclude_keywords = exclude_keywords
        df = fetch_jobs(
            search_query=query,
            country=args.country,
            hours_old=args.hours_old,
            remote_only=args.remote_only,
            profile=profile,
            force_refresh=args.force_refresh,
            logger=logger,
        )
        logger.info(f"Fetched {len(df)} jobs")

    elif args.cmd == "rank":
        profile = PROFILES[args.profile]
        profile.workspace_dir = f"workspaces/{args.user}/{profile.name}"

        resume_text = load_resume(args.resume)
        jobs_df = load_all_cached_jobs(logger)

        ranked = rank_jobs(
            resume_text=resume_text,
            jobs_df=jobs_df,
            preferences={
                "preferred": profile.preferred_companies,
                "deprioritized": profile.deprioritized_companies,
            },
            profile=profile,
            logger=logger,
        )

        ranked = (
            ranked
            .query("final_score >= @args.min_score")
            .head(args.max_results)
        )

        out = Path("outputs")
        out.mkdir(exist_ok=True)
        path = out / "ranked_jobs.csv"
        ranked.to_csv(path, index=False)

        print(ranked[["title", "company", "final_score"]].to_string(index=False))
        logger.info(f"Saved {path}")

    elif args.cmd == "run":
        profile = PROFILES[args.profile]
        profile.workspace_dir = f"workspaces/{args.user}/{profile.name}"

        search_terms = [s.strip() for s in args.search.split("|") if s.strip()]
        query = " OR ".join(f'"{t}"' for t in search_terms)
        exclude_keywords = [
            k.strip().lower()
            for k in args.exclude.split(",")
            if k.strip()
        ]

        profile.exclude_keywords = exclude_keywords
        logger.info("=== FETCH PHASE ===")
        fetch_jobs(
            search_query=query,
            country=args.country,
            hours_old=args.hours_old,
            remote_only=args.remote_only,
            profile=profile,
            force_refresh=args.force_refresh,
            results_wanted=args.max_results,
            logger=logger,
        )

        resume_text = load_resume(args.resume)
        jobs_df = load_all_cached_jobs(logger)
        logger.info("=== RANK PHASE ===")
        ranked = rank_jobs(
            resume_text=resume_text,
            jobs_df=jobs_df,
            preferences={
                "preferred": profile.preferred_companies,
                "deprioritized": profile.deprioritized_companies,
            },
            profile=profile,
            logger=logger,
        )

        out = Path("outputs")
        out.mkdir(exist_ok=True)
        path = out / "ranked_jobs.csv"
        ranked.to_csv(path, index=False)
        logger.info(f"Saved {path}")


if __name__ == "__main__":
    main()