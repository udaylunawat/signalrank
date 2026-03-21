# job_ranker/entrypoint.py
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_batch(args):
    from job_ranker.cli import main as cli_main

    argv = [
        "job-ranker",
        "--user",
        args.user,
        "--use-case",
        args.use_case,
    ]

    if args.search is not None:
        argv += ["--search", args.search]
    if args.hours_old is not None:
        argv += ["--hours-old", str(args.hours_old)]
    if args.force_refresh:
        argv.append("--force-refresh")
    if args.csv:
        argv += ["--csv", args.csv]
    if args.jobspy_only:
        argv.append("--jobspy-only")
    if args.skip_enrich:
        argv.append("--skip-enrich")
    if args.skip_ai_analysis:
        argv.append("--skip-ai-analysis")

    sys.argv = argv
    cli_main()


def run_ui(_args):
    from job_ranker import app as app_pkg

    app_path = Path(app_pkg.__file__).parent / "app.py"

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
    ]
    subprocess.run(cmd, check=True)


def run_onboard(_args):
    script = ROOT / "job_ranker" / "tools" / "onboard_user.py"

    if not script.exists():
        raise RuntimeError(f"Onboarding script not found: {script}")

    cmd = [
        sys.executable,
        str(script),
    ]
    subprocess.run(cmd, check=True)


def run_find_recruiter(args):
    """
    Find HR/recruiter contacts for jobs from a CSV (LinkedIn + Indeed).

    Strategies used:
      1. Clearbit → domain resolution (free)
      2a. Email extraction from job descriptions (Indeed goldmine)
      2b. SerpAPI → LinkedIn profile search (uses SERPAPI_KEY from .env)

    Examples:
        job-ranker find-recruiter --csv ranked_jobs_20260225_045914.csv
        job-ranker find-recruiter --csv ranked_jobs_20260225_045914.csv --top 20
        job-ranker find-recruiter --company "Adobe"
    """
    import logging
    from pathlib import Path

    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    log = logging.getLogger(__name__)

    from job_ranker.scrapers.recruiter_finder import RecruiterFinder

    db_path = str(ROOT / "job_ranker" / "duckdb")
    finder = RecruiterFinder(logger_=log, db_path=db_path)

    # ── CSV mode (primary) ──────────────────────────────────
    if args.csv:
        csv_path = Path(args.csv)
        if not csv_path.is_absolute():
            # Try relative to project root
            for candidate in [csv_path, ROOT / csv_path, ROOT / "job_ranker" / csv_path]:
                if candidate.exists():
                    csv_path = candidate
                    break

        db_path = str(ROOT / "job_ranker" / "duckdb")
        print(f"\n🔍 Finding recruiters from: {csv_path.name}")
        print(f"   Top {args.top} companies · strategies: description emails + DDG LinkedIn (SerpAPI fallback)\n")

        results, out_path = finder.find_from_csv(
            csv_path=str(csv_path),
            top=args.top,
            output_csv=args.output,
            db_path=db_path,
            refresh=getattr(args, "refresh", False),
        )

        _print_results(results, out_path)
        return

    # ── Single company mode ─────────────────────────────────
    if not args.company:
        print("❌ Provide --csv <path> or --company <name>")
        raise SystemExit(1)

    company = args.company
    print(f"\n🔍 Finding recruiters for: {company}\n")

    contacts = finder.find(company=company, refresh=getattr(args, "refresh", False))
    if not contacts:
        print(f"⚠  No contacts found for '{company}'.")
        print("   Tips: ensure SERPAPI_KEY is set in .env")
        return

    print(f"✅ {len(contacts)} contact(s):\n")
    for i, c in enumerate(contacts, 1):
        print(f"  {i}. {c.display()}")

    if args.output:
        import csv as _csv
        rows = [c.to_dict() for c in contacts]
        with open(args.output, "w", newline="") as f:
            w = _csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"\nSaved → {args.output}")


def _print_results(results: list, out_path: str):
    """Pretty-print recruiter results to terminal."""
    if not results:
        print("⚠  No results.")
        return

    found = [r for r in results if r.get("source") != "not_found"]
    not_found = [r for r in results if r.get("source") == "not_found"]

    # Group by company
    from collections import defaultdict
    by_company: dict = defaultdict(list)
    for r in found:
        by_company[r["company"]].append(r)

    print(f"{'='*70}")
    print(f"  RECRUITER CONTACTS  —  {len(found)} found across {len(by_company)} companies")
    print(f"{'='*70}\n")

    for company, contacts in by_company.items():
        score = contacts[0].get("job_score", "")
        job_title = contacts[0].get("job_title", "")
        score_str = f"  score={float(score):.2f}" if score else ""
        print(f"  ● {company}{score_str}  [{job_title[:40]}]")

        for c in contacts:
            parts = []
            if c.get("name"):
                parts.append(c["name"])
            if c.get("title"):
                parts.append(f"({c['title'][:50]})")
            if c.get("email"):
                parts.append(f"📧 {c['email']}")
            elif c.get("guessed_emails"):
                ge = c["guessed_emails"] if isinstance(c["guessed_emails"], str) else "|".join(c["guessed_emails"])
                parts.append(f"✉ ~{ge.split('|')[0]}")
            if c.get("linkedin_url"):
                parts.append(f"🔗 {c['linkedin_url']}")
            conf = c.get("confidence", "")
            src  = c.get("source", "")
            parts.append(f"[{src}, {conf}]")
            print(f"    {'  '.join(parts)}")
        print()

    if not_found:
        print(f"  ── No contacts found for: {', '.join(r['company'] for r in not_found)}\n")

    print(f"{'='*70}")
    print(f"  Saved → {out_path}")
    print(f"{'='*70}\n")


def doctor(_args):
    print("✔ Python:", sys.executable)
    print("✔ Repo root:", ROOT)
    print("✔ job_ranker package path:", ROOT / "job_ranker")
    print("✔ DuckDB path exists:", (ROOT / "job_ranker" / "duckdb").exists())
    print("✔ Streamlit importable:", end=" ")

    try:
        import streamlit  # noqa

        print("yes")
    except Exception as e:
        print("no:", e)


def main():
    p = argparse.ArgumentParser(prog="job-ranker")
    sub = p.add_subparsers(dest="cmd", required=True)

    # ---------------- run ----------------
    # entrypoint.py (only the run part)

    r = sub.add_parser("run", help="Run batch job")
    r.add_argument("--user")
    r.add_argument("--use-case", default="default")
    r.add_argument("--search")
    r.add_argument("--hours-old", type=int)
    r.add_argument("--force-refresh", action="store_true")
    r.add_argument("--no-scrape", action="store_true")
    r.add_argument("--csv", help="Path to pre-scraped CSV")
    r.add_argument("--jobspy-only", action="store_true",
                   help="Skip RapidAPI, use only JobSpy/Indeed for scraping")
    r.add_argument("--skip-enrich", action="store_true",
                   help="Skip LinkedIn description enrichment (faster, no 429s)")
    r.add_argument(
        "--skip-ai-analysis",
        action="store_true",
        help="Skip post-batch AI config advisor",
    )
    r.set_defaults(fn=run_batch)

    # ---------------- ui ----------------
    u = sub.add_parser("ui", help="Launch Streamlit UI")
    u.set_defaults(fn=run_ui)

    # ---------------- onboard ----------------
    o = sub.add_parser("onboard", help="Onboard a new user")
    o.set_defaults(fn=run_onboard)

    # ---------------- doctor ----------------
    d = sub.add_parser("doctor", help="Environment sanity check")
    d.set_defaults(fn=doctor)

    # ---------------- find-recruiter ----------------
    fr = sub.add_parser(
        "find-recruiter",
        help="Find HR/recruiter contacts from a jobs CSV (LinkedIn + Indeed)",
    )
    fr.add_argument("--csv", help="Path to ranked/scraped jobs CSV (use this for bulk search)")
    fr.add_argument("--top", type=int, default=15, help="Top N unique companies to process (default: 15)")
    fr.add_argument("--company", help="Single company name (alternative to --csv)")
    fr.add_argument("--output", help="Output CSV path (default: auto-generated)")
    fr.add_argument("--refresh", action="store_true", help="Re-search even if contacts already exist in DB")
    fr.set_defaults(fn=run_find_recruiter)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
