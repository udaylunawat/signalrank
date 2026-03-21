# Tracker & Recruiter UI Overhaul — 2026-03-21

## Summary

Complete rebuild of the job tracker dashboard and recruiter contacts experience, merging them into a single unified page with a new Email Composer feature.

---

## Changes Made

### `job_ranker/app/pages/tracker.py`

**Recruiter data merged into the tracker table**
- `load_recruiter_lookup()` now returns `{norm_company: [list of recruiters]}` ordered by confidence — all recruiters per company, not just the best one
- `_primary_recruiter(company)` helper picks the best (first) for table display
- `_name_with_count(company, name)` appends `(+N more)` when multiple recruiters exist
- Two new table columns injected per row by matching on normalised company name:
  - **"Recruiter"** (`LinkColumn`) — best recruiter's name as clickable LinkedIn link; `+N more` hint if multiple
  - **"Email Recruiter"** (`LinkColumn`) — best recruiter's name as clickable Gmail compose link
- Old flat "Recruiter" text column dropped; "Recruiter LinkedIn" from CSV used as fallback when DB has no entry
- Gmail links use `url#Name` fragment trick so `display_text=r"#(.+)$"` renders the recruiter name instead of the raw URL

**Job URL resolution**
- `_best_job_url(indeed, board)` consolidates two CSV columns at load time:
  - Primary: `Company Board URL`
  - Secondary: `Indeed URL`
  - No Google search fallback (intentional — will be addressed in recruiter enrichment phase)
- Applied to `Indeed URL` column in `load_tracker()` so every downstream consumer (table Apply link, Gmail body) gets a real URL

**Email Composer section** (new, below the tracker table)
- Company + role selectors pre-filtered to rows in the current tracker view
- All recruiters for the selected company shown as **confidence-coloured cards** (green/yellow/red border)
- Click **Select** on any card to switch the email preview to that person
- Selected card is highlighted; session state persists selection within the page session
- Live HTML preview rendered in-app: proper hyperlinks for job posting, GitHub, LinkedIn, Portfolio
- **"Open in Gmail"** button — launches Gmail compose with plain-text body (Gmail URL scheme limitation)
- **"Copy HTML"** expander — full HTML body ready to paste into Gmail for rich formatting

**Cold email template**
- Subject: `Application for {role} at {company}` (was "Referral Request")
- Body rewritten as direct cold outreach (not referral ask)
- Job posting link included in body (`{job_url}`)
- Two template variants maintained:
  - `GMAIL_BODY_PLAIN` — for Gmail compose URL (plain text)
  - `GMAIL_BODY_HTML` — for in-app preview (full HTML with hyperlinks)
- Signature updated: 7+ years experience, formatted with → arrows for plain text, proper `<a>` tags for HTML

**Signature**
```
Example Candidate
(+91) 7020901969  |  examplecandidate@gmail.com
GitHub    → https://github.com/examplecandidate
LinkedIn  → https://linkedin.com/in/examplecandidate
Portfolio → https://examplecandidate.github.io
```

### `job_ranker/app/pages/recruiters.py`

**Deleted.** All recruiter functionality merged into `tracker.py`.

### `job_ranker/app/app.py`

- Recruiters page link removed from home page grid
- Tracker description updated to mention recruiter contacts

### `job_ranker/app/pages/dashboard.py` / `all_jobs.py`

- Stale `🤝 Recruiters` sidebar nav link removed from both pages

---

## Architecture Notes

- `load_recruiter_lookup()` is `@st.cache_data(ttl=60)` — safe to call multiple times per render
- Recruiter lookup keyed on `_norm_company()` (strips non-alphanumeric, lowercases) for fuzzy company matching
- The `#Name` URL fragment approach for `LinkColumn.display_text` is a Streamlit-specific trick; valid HTML and ignored by Gmail/LinkedIn
- Gmail compose URLs support plain text only — HTML body requires copy-paste workflow

---

## Known Gaps (Next Phase)

- Many tracker companies have no recruiter in the DB — recruiter enrichment needed
- Email addresses largely absent or guessed — need verified sources
- See: `docs/` → recruiter enrichment plan (upcoming)
