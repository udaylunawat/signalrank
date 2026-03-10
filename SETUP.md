# Job Ranker — Local Setup Guide

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) — fast Python package manager
- Git

Install uv if you don't have it:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## 1. Clone & install

```bash
git clone https://github.com/examplecandidate/scrape_jobs.git
cd scrape_jobs
git checkout feat/job-ranker-batch-first
```

Install the **speedyapply JobSpy fork** (required — has `hours_old` support):
```bash
pip install git+https://github.com/speedyapply/JobSpy.git
```

Install job-ranker:
```bash
uv venv .venv --python python3.11
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv pip install -e .
uv pip install git+https://github.com/speedyapply/JobSpy.git  # override PyPI version
```

---

## 2. Configure environment

Copy the example env file:
```bash
cp job_ranker/.env.example job_ranker/.env   # if it exists
# or create job_ranker/.env manually:
```

Minimum `.env`:
```env
# Required for RapidAPI sources (optional — disabled by default)
RAPIDAPI_KEY=your_key_here

# Required for LLM veto/enrichment (optional)
OPENROUTER_API_KEY=your_key_here

# Optional: residential proxy for Google Jobs on servers
# GOOGLE_JOBS_PROXY=user:pass@host:port
```

---

## 3. Run

### Quick test — JobSpy + Google Jobs only (no API keys needed):
```bash
job-ranker run \
  --user example \
  --search "mlops|llmops|ai platform engineer" \
  --hours-old 72 \
  --force-refresh \
  --skip-enrich
```

### Full run (all sources, with RapidAPI):
```bash
# First set jobspy_only: false in job_ranker/config/base.yaml
job-ranker run \
  --user example \
  --search "mlops|llmops|ai platform engineer" \
  --hours-old 72 \
  --force-refresh
```

### With enrichment (LinkedIn descriptions — slow, hits rate limits):
```bash
job-ranker run --user example --search "mlops" --hours-old 72 --force-refresh
# (omit --skip-enrich)
```

---

## 4. View results

Launch the Streamlit dashboard:
```bash
job-ranker ui
```

Or inspect the ranked CSV directly:
```bash
ls ranked_*.csv | tail -1 | xargs head -20
```

---

## 5. Config reference

Key settings in `job_ranker/config/base.yaml`:

| Setting | Default | Notes |
|---------|---------|-------|
| `scraping.jobspy_only` | `true` | Disable RapidAPI, use only JobSpy |
| `scraping.google_jobs.enabled` | `true` | Google Jobs scraper (laptop only) |
| `scraping.google_jobs.proxy` | `null` | Residential proxy for server use |
| `scraping.supports_hours_old` | `true` | Requires speedyapply fork |
| `scraping.max_results` | `1500` | Per query per source |

Per-user config overrides live in `job_ranker/config/overrides/<user>.yaml`.

---

## 6. Source health check

Run the probe to see which sources are working:
```bash
python job_ranker/tests/source_probe.py
```

---

## 7. Adding a new user

```bash
job-ranker onboard
```

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `scrape_jobs() got unexpected keyword argument 'hours_old'` | Wrong JobSpy version — run `pip install git+https://github.com/speedyapply/JobSpy.git` |
| `Google Jobs 0 results` | Running on server/Docker IP — works on laptop without proxy |
| `LinkedIn 429` | Free RapidAPI tier rate limit — use `--skip-enrich` or subscribe to higher tier |
| `unrecognized arguments: --jobspy-only` | Old version — `git pull origin feat/job-ranker-batch-first` |
