#!/usr/bin/env bash
set -e

# --------------------------------------------------
# Failure trap (state contract with notifier)
# --------------------------------------------------
trap 'echo "{\"run_id\":\"$(date +%s)\",\"timestamp\":\"$(date -Iseconds)\",\"status\":\"failed\",\"notified\":false}" > "$HOME/.job_ranker_last_run.json"' ERR

# --------------------------------------------------
# Resolve project root safely
# --------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"
LOCKFILE="$PROJECT_ROOT/outputs/.run.lock"

echo "[$(date)] run_daily.sh started"
echo "Project root: $PROJECT_ROOT"
echo "Using Python: $VENV_PYTHON"

# --------------------------------------------------
# Sanity checks
# --------------------------------------------------
if [ ! -x "$VENV_PYTHON" ]; then
  echo "ERROR: Virtualenv python not found at $VENV_PYTHON"
  exit 127
fi

mkdir -p "$PROJECT_ROOT/outputs"

# --------------------------------------------------
# Lockfile (prevent overlapping runs)
# --------------------------------------------------
if [ -f "$LOCKFILE" ]; then
  echo "Another run is already in progress. Exiting."
  exit 0
fi

touch "$LOCKFILE"
trap 'rm -f "$LOCKFILE"' EXIT

cd "$PROJECT_ROOT"

# --------------------------------------------------
# Environment (MINIMAL, FUTURE-PROOF)
# --------------------------------------------------
export PYTHONPATH="$PROJECT_ROOT"
export JOBSCRAPER_MODE=batch
export TOKENIZERS_PARALLELISM=false

# NOTE:
# - No OpenMP / MKL / Torch pinning here anymore
# - DuckDB does not require it
# - SentenceTransformers thread control belongs in Python if needed
# - This keeps the shell clean and portable

# --------------------------------------------------
# Run batch pipeline
# --------------------------------------------------
"$VENV_PYTHON" cli.py run \
  --resume "$PROJECT_ROOT/users/Example_Candidate/resume.tex" \
  --search "mlops engineer|genai engineer|llmops engineer|generative ai|senior software engineer|forward deployed engineer|sweIII" \
  --exclude "cyber,cybersecurity,soc,siem,incident,forensics,qa,test,quality,product manager,program manager" \
  --prefer-companies "uhg,roche,pfizer,abbvie,ubs,walmart,servicenow,atlassian,merck,msci,siemens,optum,unitedhealth,eli lilly,philips,ge healthcare,visa,mastercard,capital one,intuit,workday,salesforce,john deere,goldman,microsoft,google,apple" \
  --skip-companies "amazon,uber,wipro,infosys,tcs,hcl,tech mahindra,cognizant,capgemini,ibm,globallogic,nagarro,citius,fractal" \
  --hours-old 4 \
  --max-results 50 \
  --user example \
  --country India \
  --force-refresh

echo "[$(date)] run_daily.sh finished successfully"

# --------------------------------------------------
# Persist success status (single source of truth)
# --------------------------------------------------
STATUS_FILE="$HOME/.job_ranker_last_run.json"
RUN_ID="$(date +%s)"

echo "{
  \"run_id\": \"$RUN_ID\",
  \"timestamp\": \"$(date -Iseconds)\",
  \"status\": \"success\",
  \"notified\": false
}" > "$STATUS_FILE"

# --------------------------------------------------
# Best-effort notification trigger
# --------------------------------------------------
launchctl kickstart -k gui/$(id -u)/com.example.job_ranker.notify || true