# Job Ranker — Learnings & Debug Log

> Iteratively updated as we debug, fix, and improve the scraping stack.

---

## 2026-03-09 — Initial Investigation

### Environment Status
| Key | Status |
|-----|--------|
| `RAPIDAPI_KEY` | ✅ Valid (50-char key in `.env`) — `.env copy` has placeholder, real file is fine |
| `OPENROUTER_API_KEY` | ❌ Invalid (placeholder `sk-` in `.env copy`) — check actual `.env` |

> Note: `.env copy` (the backup) has placeholder values. The real `.env` has valid keys. Always load from `.env`.

### Source Probe Results (2026-03-09)
| Source | Status | Notes |
|--------|--------|-------|
| JobSpy / Indeed | ✅ 5 jobs | 1.0s, reliable |
| JSearch (RapidAPI) | ✅ 10 jobs | 12.8s, slow but working |
| Himalayas | ✅ 5 jobs | 1.1s, remote-only |
| Jobicy | ✅ 1 job | 0.6s, remote-only |
| Remotive | ⚠️ 0 jobs | remote-only, no mlops india results |
| LinkedIn JB (RapidAPI) | ⚠️ 0 jobs | May need subscription or different query |

### JobSpy Indeed — Working ✅
- `scrape_jobs(site_name=["indeed"], location="India", country_indeed="India")` returns real results
- India is a valid `Country` enum value in JobSpy (`co.in` domain)
- Hardcoded API key in `jobspy/indeed/constant.py` is currently live
- **Risk:** hardcoded key can expire or get rotated without notice

### Free Direct APIs — Working ✅
- Remotive, Himalayas, Jobicy all return 200 + real jobs for "mlops"
- These need no key and should always be primary fallback
- Arbeitnow direct endpoint also works (no key needed)

### RapidAPI Endpoints — All 401/403 ❌
- Every RapidAPI call fails because `RAPIDAPI_KEY=dd` is invalid
- Scraper handles this gracefully (skips on 401), but yields 0 rows from these sources
- Sources affected: LinkedIn JB, LinkedIn ATS, JSearch, Indeed Scraper, Google Jobs, Arbeitnow (via RapidAPI)

### Root Cause of "no results" / 401/403
1. `.env copy` has placeholder keys — but the real `.env` is fine
2. LinkedIn JB endpoint returns 0 results (subscription or query mismatch)
3. Old scraper design: free APIs only ran as RapidAPI fallback — fixed
4. JSearch is slow (12.8s) but actually works with the valid key

---

## Key Architecture Decisions

### Scraping Priority (as of 2026-03-09)
```
[1] RapidAPI sources (if RAPIDAPI_KEY valid)
    └── LinkedIn JB, ATS, JSearch, Indeed Scraper, Google Jobs
[2] JobSpy (free, Indeed + LinkedIn)
    └── Uses internal API key — works but fragile
[3] Free direct APIs (no key needed, always available)
    └── Remotive, Himalayas, Jobicy, Arbeitnow
```

### What Changed
- JobSpy promoted to co-primary (not just fallback) for Indeed + LinkedIn
- Free direct APIs should always run regardless of RapidAPI key status

---

## Fixes Applied

### Fix 1: Decouple free APIs from RapidAPI key check
- Previously: free APIs only ran as fallback when RapidAPI failed
- After: free APIs always run unconditionally (they're free, always available)

### Fix 2: JobSpy runs for Indeed always (not just as fallback)
- JobSpy Indeed works reliably for `country_indeed="India"`
- Should be attempted in parallel with RapidAPI, not only when it fails

### Fix 3: Env validation / doctor feedback
- `just doctor` now warns clearly when RAPIDAPI_KEY or OPENROUTER_API_KEY are placeholders

---

## Gotchas & Tips

- `country_indeed` must be `"India"` not `"IN"` — JobSpy resolves it via enum name
- JobSpy returns a DataFrame, not list — `_normalize_jobs` handles this correctly
- `hours_old` filter for Indeed: set `supports_hours_old: true` in config to enable
- JSearch (RapidAPI) is the best LinkedIn alternative when LinkedIn API key is invalid
- Remotive/Jobicy/Himalayas are remote-only — good for remote searches, low signal for India on-site

---

## TODO / Next Steps
- [ ] Get a valid `RAPIDAPI_KEY` (free tier available) to unlock LinkedIn + JSearch
- [ ] Get a valid `OPENROUTER_API_KEY` to re-enable LLM veto/enrichment
- [ ] Add a health-check probe that tests each source on startup
- [ ] Cache JobSpy results to reduce repeat API calls (key fragility mitigation)
- [ ] Consider rotating/proxying the Indeed internal API key with retries
