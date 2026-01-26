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


def parse_list(s: str) -> list[str]:
    return [x.strip().lower() for x in s.split(",") if x.strip()]


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

    f.add_argument("--exclude", default="")
    f.add_argument("--max-results", type=int, default=300)

    f.add_argument("--prefer-companies", default="")
    f.add_argument("--skip-companies", default="")

    # ---------- rank ----------
    r = sub.add_parser("rank", help="Rank cached jobs")
    r.add_argument("--resume", required=True)
    r.add_argument("--user", required=True)
    r.add_argument("--profile", choices=PROFILES.keys(), default="senior_ic")
    r.add_argument("--min-score", type=float, default=0.25)
    r.add_argument("--max-results", type=int, default=30)

    r.add_argument("--prefer-companies", default="")
    r.add_argument("--skip-companies", default="")

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

    run.add_argument("--exclude", default="")
    run.add_argument("--max-results", type=int, default=100)

    run.add_argument("--prefer-companies", default="")
    run.add_argument("--skip-companies", default="")
    run.add_argument(
        "--rank-corpus",
        action="store_true",
        help="Rank against consolidated corpus instead of cache",
    )
    return p


def apply_company_overrides(profile, args, logger):
    preferred = parse_list(getattr(args, "prefer_companies", ""))
    skipped = parse_list(getattr(args, "skip_companies", ""))

    profile.preferred_companies = list(
        set(profile.preferred_companies + preferred)
    )
    profile.deprioritized_companies = list(
        set(profile.deprioritized_companies + skipped)
    )

    logger.info(f"Preferred companies: {profile.preferred_companies}")
    logger.info(f"Skipped companies: {profile.deprioritized_companies}")


def main():
    args = build_parser().parse_args()
    logger = setup_logger()

    if args.cmd == "fetch":
        profile = PROFILES[args.profile]
        apply_company_overrides(profile, args, logger)

        profile.exclude_keywords = parse_list(args.exclude)

        search_terms = [s.strip() for s in args.search.split("|") if s.strip()]
        query = " OR ".join(f'"{t}"' for t in search_terms)

        df = fetch_jobs(
            search_query=query,
            country=args.country,
            hours_old=args.hours_old,
            remote_only=args.remote_only,
            profile=profile,
            force_refresh=args.force_refresh,
            results_wanted=args.max_results,
            logger=logger,
        )
        logger.info(f"Fetched {len(df)} jobs")

    elif args.cmd == "rank":
        profile = PROFILES[args.profile]
        profile.workspace_dir = f"workspaces/{args.user}/{profile.name}"
        apply_company_overrides(profile, args, logger)

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

        ranked = ranked.query("final_score >= @args.min_score").head(args.max_results)

        out = Path("outputs")
        out.mkdir(exist_ok=True)
        path = out / "ranked_jobs.csv"
        ranked.to_csv(path, index=False)
        logger.info(f"Saved {path}")

    elif args.cmd == "run":
        profile = PROFILES[args.profile]
        profile.workspace_dir = f"workspaces/{args.user}/{profile.name}"
        apply_company_overrides(profile, args, logger)

        profile.exclude_keywords = parse_list(args.exclude)

        if args.rank_corpus:
            logger.info("=== CORPUS RANK PHASE ===")
            corpus_path = Path("corpus/jobs_corpus.csv")
            if not corpus_path.exists():
                logger.error("Corpus not found. Run build_corpus.py first.")
                return

            jobs_df = pd.read_csv(corpus_path)

        else:
            logger.info("=== FETCH PHASE ===")
            search_terms = [s.strip() for s in args.search.split("|") if s.strip()]
            query = " OR ".join(f'"{t}"' for t in search_terms)

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

            jobs_df = load_all_cached_jobs(logger)

        logger.info("=== RANK PHASE ===")
        resume_text = load_resume(args.resume)

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