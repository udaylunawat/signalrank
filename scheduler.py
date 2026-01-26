# scheduler.py
import subprocess
import time
from pathlib import Path
from datetime import datetime, timedelta
import logging
import sys
import os

# --------------------------------------------------
# CONFIG
# --------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
RUN_SCRIPT = BASE_DIR / "run_daily.sh"
OUTPUT_FILE = BASE_DIR / "outputs" / "ranked_jobs.csv"
LOG_FILE = Path.home() / "job_ranker_scheduler.log"

CHECK_INTERVAL_SECONDS = 24 * 60 * 60   # 24 hours
STALE_AFTER_HOURS = 24

STREAMLIT_CMD = [
    sys.executable,
    "-m",
    "streamlit",
    "run",
    "app.py",
]

# --------------------------------------------------
# LOGGING
# --------------------------------------------------
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger("").addHandler(console)


# --------------------------------------------------
# HELPERS
# --------------------------------------------------
def is_output_stale() -> bool:
    if not OUTPUT_FILE.exists():
        logging.warning("ranked_jobs.csv missing")
        return True

    mtime = datetime.fromtimestamp(OUTPUT_FILE.stat().st_mtime)
    age = datetime.now() - mtime

    if age > timedelta(hours=STALE_AFTER_HOURS):
        logging.warning(
            f"ranked_jobs.csv stale ({age.total_seconds()/3600:.1f}h old)"
        )
        return True

    return False


def run_daily_job() -> bool:
    logging.info("Running daily ranking job")

    try:
        subprocess.run(
            ["bash", str(RUN_SCRIPT)],
            cwd=BASE_DIR,
            check=True,
        )
        logging.info("run_daily.sh completed successfully")
        return True

    except subprocess.CalledProcessError as e:
        logging.error(f"run_daily.sh failed: {e}")
        return False


def start_streamlit():
    logging.info("Starting Streamlit app")

    subprocess.Popen(
        STREAMLIT_CMD,
        cwd=BASE_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=os.environ.copy(),
    )


# --------------------------------------------------
# MAIN LOOP
# --------------------------------------------------
def main():
    logging.info("Job Ranker scheduler started")

    while True:
        try:
            needs_run = is_output_stale()

            if needs_run:
                success = run_daily_job()
                if success:
                    start_streamlit()
                else:
                    logging.error("Daily job failed; Streamlit not started")
            else:
                logging.info("ranked_jobs.csv is fresh; no action taken")

        except Exception as e:
            logging.exception(f"Scheduler error: {e}")

        logging.info("Sleeping until next check")
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()