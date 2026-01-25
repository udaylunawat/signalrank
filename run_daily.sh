#!/usr/bin/env bash
set -e

cd "$HOME/Downloads/jobs_scraper/scrape_jobs"

export PYTHONPATH="$(pwd)"
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export TORCH_NUM_THREADS=1
export TOKENIZERS_PARALLELISM=false
export JOBSCRAPER_MODE=batch

python cli.py run \
  --resume "/Users/udaylunawat/Downloads/jobs_scraper/scrape_jobs/users/Uday_Lunawat/resume.tex" \
  --search "mlops engineer|genai engineer|llmops engineer|generative ai|senior software engineer" \
  --exclude "cyber,cybersecurity,soc,siem,incident,forensics" \
  --hours-old 72 \
  --max-results 100 \
  --user uday \
  --profile senior_ic \
  --country India
