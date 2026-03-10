#!/usr/bin/env python3
# ================================
# FILE: scheduler.py
# ================================
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from config_loader import settings
from user_context import resolve_user_context

USER = os.environ.get("JOBRANKER_USER")
USE_CASE = os.environ.get("JOBRANKER_USE_CASE", "default")

if not USER:
    raise SystemExit(
        "JOBRANKER_USER must be set for scheduler.\n"
        "Example:\n"
        "export JOBRANKER_USER=example\n"
        "export JOBRANKER_USE_CASE=default"
    )

ctx = resolve_user_context(
    user=USER,
    use_case_override=USE_CASE,
    require_resume=False,
)

RUN_SCRIPT = Path(settings.paths.project_root).resolve() / "run_daily.sh"
OUTPUT_FILE = ctx.outputs_dir / settings.outputs.ranked_jobs_file

CHECK_INTERVAL_SECONDS = settings.scheduler.check_interval_seconds
STALE_AFTER_HOURS = settings.scheduler.stale_after_hours

logging.basicConfig(
    filename=settings.logging.log_file if settings.logging.log_to_file else None,
    level=getattr(logging, settings.logging.level),
    format=settings.logging.format,
)


def is_output_stale() -> bool:
    if not OUTPUT_FILE.exists():
        logging.warning("ranked_jobs.csv missing")
        return True

    mtime = datetime.fromtimestamp(OUTPUT_FILE.stat().st_mtime)
    age = datetime.now() - mtime
    return age > timedelta(hours=STALE_AFTER_HOURS)


def run_daily_job() -> bool:
    try:
        subprocess.run(["bash", str(RUN_SCRIPT)], check=True)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"run_daily.sh failed: {e}")
        return False


def main():
    logging.info(f"Scheduler started for {ctx.user}/{ctx.use_case}")

    while True:
        try:
            if is_output_stale():
                logging.info("Output stale; running daily job")
                run_daily_job()
            else:
                logging.info("Output fresh; no action")

        except Exception:
            logging.exception("Scheduler error")

        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
