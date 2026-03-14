# job_ranker — Changes & Architecture Summary

> Last updated: 2026-03-10
> Branch: `feat/job-ranker-batch-first`
> Remote: https://github.com/examplecandidate/scrape_jobs.git

---

## What This Is

`job_ranker` is a batch pipeline that:
1. **Scrapes** job listings from multiple sources
2. **Deduplicates** by URL
3. **Enriches** job descriptions (optional, `--skip-enrich` to skip)
4. **Ranks** jobs against a persona embedding (resume intent)
5. **Persists** ranked results to DuckDB for review

---

## Sources

| Source | Status | Notes |
|--------|--------|-------|
| **JobSpy / Indeed** | ✅ Working | Sequential (1 query at a time, 3s delay) to avoid 403s |
| **JobSpy / LinkedIn** | ✅ Working | Parallel-safe |
| **SerpAPI Google Jobs** | ✅ Working | Set `SERPAPI_KEY` in `.env`. 100 free/month at https://serpapi.com |
| **Gmail Job Alerts** | ⛔ Abandoned | Auth works, emails parsed — but links go to `google.com/search?udm=8` (CAPTCHA). No direct apply URLs. Low ROI. |
| **Remotive / Himalayas / Jobicy** | ✅ Working | Free APIs, no key needed. Disabled in `jobspy_only` mode |
| **JSearch (RapidAPI)** | ⚠️ Rate-limited | Pulls from company career pages. Disabled by default |
| **LinkedIn RapidAPI** | ⚠️ Rate-limited | Free tier exhausted quickly. Disabled by default |
| **Direct Google scraping** | ❌ Blocked | Blocked on all IPs. Replaced by SerpAPI |

---

## Key Decisions

### 1. Serialize JobSpy Indeed calls
Parallel requests caused 403 errors. Fixed by running queries sequentially with `JOBSPY_INTER_QUERY_DELAY = 3.0s`.

### 2. `jobspy_only: true` as default
RapidAPI sources are off by default. Only JobSpy, SerpAPI, and Gmail run unless explicitly enabled.

### 3. speedyapply fork over PyPI `python-jobspy`
Fork supports `hours_old` parameter. Auto-retry fallback added for compatibility with vanilla jobspy.

### 4. SerpAPI for Google Jobs
Direct Google HTML scraping is blocked on all IPs (residential included). SerpAPI handles proxy rotation on their end — works from anywhere.

### 5. Gmail Job Alerts via IMAP (read-only)
Uses IMAP `EXAMINE` (never SELECT) — guaranteed read-only, no emails marked or deleted. Parses `jobalerts-noreply@google.com` emails from a configurable Gmail label.

### 6. `--skip-enrich` flag
Enrichment (LinkedIn profile lookups) defaults on but can be skipped for faster runs.

### 7. Clean git history
Large files (CSV, DuckDB) were removed from tracking. A `clean-push` branch was used to push without large file history.

---

## Architecture

```
job-ranker run
  │
  ├── Phase 1: JobSpy (Indeed + LinkedIn) — sequential, 3s delay
  ├── Phase 2: RapidAPI sources (JSearch, LinkedIn ATS) — disabled by default
  ├── Phase 3: Free APIs (Remotive, Himalayas, Jobicy) — disabled in jobspy_only mode
  ├── Phase 4: Google Jobs via SerpAPI — always runs if SERPAPI_KEY set
  └── Phase 5: Gmail Job Alerts (IMAP read-only) — runs if gmail_alerts.enabled: true
       │
       ▼
  Deduplicate by job_url
       │
       ▼
  Enrich (LinkedIn lookups) — skippable via --skip-enrich
       │
       ▼
  Rank (persona embedding + role weights + company tiers + location scoring)
       │
       ▼
  Persist to DuckDB → ranked_jobs CSV
```

---

## Environment Variables (`.env`)

```env
# LLM — for enrichment/veto (optional)
OPENROUTER_API_KEY=sk-...

# RapidAPI — disabled by default, enable in base.yaml
RAPIDAPI_KEY=...

# Google Jobs via SerpAPI (100 free/month — https://serpapi.com)
SERPAPI_KEY=...

# Gmail Job Alerts (read-only IMAP)
GMAIL_USER=you@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx   # from https://myaccount.google.com/apppasswords
GMAIL_LABEL=Job Alerts/Google Alerts

# Residential proxy fallback for Google Jobs (if no SerpAPI)
# GOOGLE_JOBS_PROXY=user:pass@host:port
```

Template: `job_ranker/.env copy` (tracked in git)
Real `.env` is always gitignored.

---

## Config

Main config: `job_ranker/config/base.yaml`
User overrides: `job_ranker/config/overrides/<user>.yaml`

Key flags:
```yaml
scraping:
  jobspy_only: true          # disables RapidAPI + free APIs
  google_jobs:
    enabled: false           # direct scraping blocked — use SerpAPI
  gmail_alerts:
    enabled: true            # reads Gmail Job Alert emails
    days_back: 30
    max_emails: 30
```

---

## CLI

```bash
# Basic run
job-ranker run --user example --search "mlops|llmops|ai platform engineer" --hours-old 72

# Skip enrichment (faster)
job-ranker run --user example --search "mlops" --hours-old 168 --skip-enrich --force-refresh
```

---

## Gmail Job Alerts Setup

To get jobs into the Gmail label:
1. Go to https://www.google.com/alerts
2. Create alerts for your search terms (e.g. "mlops jobs India")
3. In Gmail, create a filter: `from:jobalerts-noreply@google.com` → apply label `Job Alerts/Google Alerts`
4. Wait for alert emails to arrive, then rerun job-ranker

IMAP setup:
1. Gmail → Settings → Forwarding and POP/IMAP → **Enable IMAP**
2. https://myaccount.google.com/apppasswords → create App Password → add to `.env`

---

## Known Issues / Blocked

| Issue | Status |
|-------|--------|
| SerpAPI `start` param deprecated | ✅ Fixed — using `next_page_token` |
| SerpAPI `chips` param causes 400 | ✅ Fixed — auto-retry without date filter |
| Gmail label empty (0 emails) | ⚠️ Need to set up Google Alerts + Gmail filter |
| LinkedIn RapidAPI rate-limited | ⚠️ Free tier exhausted — upgrade plan or reduce frequency |
| Indeed Scraper RapidAPI | ❌ 403 — not subscribed |
| Direct Google scraping | ❌ Blocked on all IPs |

---

## Files Changed (this session)

| File | Change |
|------|--------|
| `job_ranker/batch/scraper.py` | SerpAPI backend, Gmail Phase 5, pagination fix, `next_page_token` |
| `job_ranker/scrapers/gmail_alerts.py` | New — read-only IMAP Gmail scraper |
| `job_ranker/scrapers/google_jobs/` | Kept as reference (not used — JobSpy Google blocked) |
| `job_ranker/config/base.yaml` | `gmail_alerts` config block, `google_jobs.enabled: false` |
| `job_ranker/config/overrides/example.yaml` | `gmail_alerts.enabled: true`, `days_back: 30` |
| `job_ranker/.env copy` | Full template with all env vars |
| `job_ranker/tests/test_gmail_alerts.py` | Local test script for Gmail IMAP |
| `.gitignore` | `.env` always ignored, `.env copy` explicitly allowed |
| `SETUP.md` | Gmail + SerpAPI setup instructions |
| `LEARNINGS.md` | Iterative findings |
