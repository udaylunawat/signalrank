#!/usr/bin/env bash
set -e

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
export JOBSCRAPER_MODE=batch

# --------------------------------------------------
# Run batch pipeline (explicit venv python)
# --------------------------------------------------
"$VENV_PYTHON" cli.py run \
  --resume "$PROJECT_ROOT/users/Example_Candidate/resume.tex" \
  --search "mlops engineer|genai engineer|llmops engineer|generative ai|senior software engineer|forward deployed engineer" \
  --exclude "cyber,cybersecurity,soc,siem,incident,forensics,qa,test,quality,product manager,program manager" \
  --prefer-companies "uhg,roche,pfizer,abbvie,ubs,walmart,servicenow,atlassian,merck,msci,siemens,optum,unitedhealth,eli lilly,philips,ge healthcare,visa,mastercard,capital one,intuit,workday,salesforce,adobe,blackrock,goldman,microsoft,google,apple" \
  --skip-companies "amazon,uber,wipro,infosys,tcs,hcl,tech mahindra,cognizant,capgemini,ibm,epam,globallogic,nagarro,citius,fractal" \
  --hours-old 120 \
  --max-results 50 \
  --user example \
  --profile senior_ic \
  --country India \
  --force-refresh

echo "[$(date)] run_daily.sh finished successfully"