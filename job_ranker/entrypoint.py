# job_ranker/entrypoint.py
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_batch(args):
    from job_ranker.cli import main as cli_main

    sys.argv = [
        "job-ranker",
        "--user",
        args.user,
        "--use-case",
        args.use_case,
        "--search",
        args.search,
        "--hours-old",
        str(args.hours_old),
    ] + (["--force-refresh"] if args.force_refresh else [])

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
    cmd = [
        sys.executable,
        str(ROOT / "tools" / "onboard_user.py"),
    ]
    subprocess.run(cmd, check=True)


def doctor(_args):
    print("✔ Python:", sys.executable)
    print("✔ Repo root:", ROOT)
    print("✔ DuckDB path exists:", (ROOT / "duckdb").exists())
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
    r.add_argument("--hours-old", type=int, default=24)
    r.add_argument("--force-refresh", action="store_true")
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

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
