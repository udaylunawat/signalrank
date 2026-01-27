#!/usr/bin/env bash
set -e

# --------------------------------------------------
# Resolve project root safely
# --------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"

USER="uday"
USE_CASE="default"

BASE_DIR="$PROJECT_ROOT/users/$USER/$USE_CASE"
OUTPUT_DIR="$BASE_DIR/outputs"
CACHE_DIR="$BASE_DIR/cache"
LOCKFILE="$OUTPUT_DIR/.run.lock"

echo "[$(date)] run_daily.sh started"
echo "Project root: $PROJECT_ROOT"
echo "User: $USER / Use case: $USE_CASE"
echo "Using Python: $VENV_PYTHON"

# --------------------------------------------------
# Sanity checks
# --------------------------------------------------
if [ ! -x "$VENV_PYTHON" ]; then
  echo "ERROR: Virtualenv python not found at $VENV_PYTHON"
  exit 127
fi

mkdir -p "$OUTPUT_DIR" "$CACHE_DIR"

# --------------------------------------------------
# Lockfile (user + use_case scoped)
# --------------------------------------------------
if [ -f "$LOCKFILE" ]; then
  echo "Another run is already in progress for $USER/$USE_CASE. Exiting."
  exit 0
fi

touch "$LOCKFILE"
trap 'rm -f "$LOCKFILE"' EXIT

cd "$PROJECT_ROOT"

# --------------------------------------------------
# Environment safety (macOS + FAISS + Torch)
# --------------------------------------------------
export PYTHONPATH="$PROJECT_ROOT"
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export TORCH_NUM_THREADS=1
export TOKENIZERS_PARALLELISM=false

# Explicit batch + cache scope
export JOBSCRAPER_MODE=batch
export JOBRANKER_CACHE_DIR="$CACHE_DIR"

# --------------------------------------------------
# Run batch pipeline
# --------------------------------------------------
"$VENV_PYTHON" cli.py run \
  --user "$USER" \
  --use-case "$USE_CASE" \
  --profile senior_ic \
  --country India \
  --search "mlops engineer|genai engineer|llmops engineer|generative ai|senior software engineer|forward deployed engineer|swe3|sweIII" \
  --exclude "cyber,cybersecurity,soc,siem,incident,forensics,qa,test,quality,product manager,program manager" \
  --prefer-companies "uhg,roche,pfizer,abbvie,ubs,walmart,servicenow,atlassian,merck,msci,siemens,optum,unitedhealth,eli lilly,philips,ge healthcare,visa,mastercard,capital one,intuit,workday,salesforce,adobe,blackrock,goldman,microsoft,google,apple" \
  --skip-companies "amazon,uber,wipro,infosys,tcs,hcl,tech mahindra,cognizant,capgemini,ibm,epam,globallogic,nagarro,citius,fractal" \
  --hours-old 24 \
  --max-results 50 \
  --force-refresh

echo "[$(date)] run_daily.sh finished successfully"

# python cli.py run \
#   --resume users/Uday_Lunawat/resume.tex \
#   --search "mlops engineer" \
#   --user uday \
#   --profile senior_ic \
#   --country India \
#   --hours-old 4 \
#   --max-results 100