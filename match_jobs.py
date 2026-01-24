import argparse
from pathlib import Path

from resume_parser import load_resume
from scrape_jobs import fetch_jobs
from match_engine import rank_jobs
from profiles import PROFILES
from logger import setup_logger


def build_parser():
    parser = argparse.ArgumentParser(
        description="Calm-first job ranking (CLI)"
    )

    parser.add_argument("--resume", required=True)
    parser.add_argument("--search", required=True)
    parser.add_argument("--country", default="India")
    parser.add_argument("--hours-old", type=int, default=48)
    parser.add_argument("--remote-only", action="store_true")
    parser.add_argument("--profile", choices=PROFILES.keys(), default="senior_ic")
    parser.add_argument("--force-refresh", action="store_true")

    # 👇 NEW
    parser.add_argument(
        "--view-only",
        action="store_true",
        help="Skip scraping and use cached jobs only",
    )

    return parser


def main():
    args = build_parser().parse_args()
    logger = setup_logger()

    profile = PROFILES[args.profile]
    logger.info(f"Using profile: {profile.name}")

    resume_text = load_resume(args.resume)

    search_terms = [s.strip() for s in args.search.split("|") if s.strip()]
    search_query = " OR ".join(f'"{t}"' for t in search_terms)

    jobs_df = fetch_jobs(
        search_query=search_query,
        country=args.country,
        hours_old=args.hours_old,
        remote_only=args.remote_only,
        profile=profile,
        force_refresh=args.force_refresh,
        logger=logger,
        view_mode=args.view_only,   # 👈 NEW
    )

    if jobs_df.empty:
        logger.warning("No jobs to rank")
        return

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

    print(
        ranked[["title", "company", "final_score", "explanation"]]
        .head(10)
        .to_string(index=False)
    )

    ranked.to_csv("ranked_jobs.csv", index=False)
    print("Saved ranked_jobs.csv")


if __name__ == "__main__":
    main()