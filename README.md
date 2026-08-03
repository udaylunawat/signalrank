# SignalRank

SignalRank is a resume- and role-agnostic job discovery, ranking, and match-tracking application. A user uploads a resume, confirms any roles or locations they want, refreshes the job catalog, and receives explainable ranked matches. It runs either as a fully local macOS/Windows desktop app or as the web deployment.

The active application lives in [`signalrank/`](signalrank/). Historical Job Ranker implementations and archived artifacts are preserved on `backup/main-2026-07-15` instead of being carried in the production branch.

## Product principles

- Any resume and any free-text role title must work; there is no fixed role catalog.
- Resume parsing should improve the experience, not block it. Deterministic extraction remains available when an LLM is unavailable.
- Discovery favors recall, while ranking remains deterministic and explainable.
- Company reputation is assessed independently of candidate role, seniority, resume, or location.
- Model failures degrade visibly and safely instead of breaking onboarding or ranking.

## Current capabilities

### Onboarding and profiles

- Email/password accounts with per-user profiles.
- PDF, DOCX, and TXT resume upload.
- Strict structured extraction of skills, experience, titles, industries, and education through OpenRouter.
- Deterministic fallback parsing and explicit parse status, confidence, model, and error metadata.
- Editable free-text target roles, preferred locations, preferred companies, and exclusions.
- Degraded parses are retried after model or credential recovery instead of being cached permanently.

### Discovery and ranking

- Durable database-backed refresh runs with leases, retries, stages, and source telemetry.
- Independent discovery through Indeed and LinkedIn via JobSpy plus Remotive, Himalayas, and Jobicy.
- Canonicalization, URL deduplication, freshness tracking, and active-job state.
- Semantic resume-to-job scoring combined with deterministic role, explicit skill, seniority, location, company, recency, and contract signals.
- Primary and broader-match lanes without profession-specific role presets.
- Per-match explanations, matched skills, score dimensions, concerns, source links, and CSV export.
- Native-safe job-link opening from both web and desktop.
- Per-role application kits with truthful AI-tailored PDF resumes and editable recruiter outreach drafts.
- Application tracking across saved, applied, interviewing, offered, rejected, and withdrawn states.

### AI-driven company reputation

The **Top reputed** filter is powered by free OpenRouter models rather than a hard-coded company list.

- SignalRank discovers currently available free models that support structured output.
- Companies are evaluated with one global, role-independent rubric covering credibility, product or engineering reputation, organizational maturity, durable standing, and career development.
- Assessments include a score, S/A/B/C tier, confidence, rationale, model identifier, rubric version, and expiry time.
- Results are persisted and reused for 60 days by default.
- **Top reputed** includes assessed S/A employers with confidence of at least `0.7`, plus companies the user explicitly prefers.
- **All companies** keeps assessed and unassessed employers visible.

OpenRouter is advisory: an unavailable key or model does not prevent resume storage, profile editing, catalog refresh, or ranking in **All companies** mode.

## Architecture

Desktop builds keep the resume, profile, SQLite database, job catalog, ranking, and tracker on the user's device. They bundle a Tauri shell, local FastAPI/Python service, local Next.js service, and embedding model. OpenRouter and job-source scraping are the only normal network paths.

Tailored resumes are rendered by the bundled Python service, so desktop users do not need Typst, a browser print service, Microsoft Word, or another system dependency. Generated PDFs are saved through the native file dialog; external job and Gmail links are validated by the native shell before they open.

```text
Tauri 2 shell
    ├── Next.js workspace on a random loopback port
    └── FastAPI worker on a random loopback port
          ├── SQLite
          ├── local scraping and ranking
          ├── bundled embedding model
          └── user-provided OpenRouter key
```

The web deployment uses:

```text
Next.js 16 frontend
        |
        v
FastAPI API + durable background worker
        |
        +-- PostgreSQL + pgvector
        +-- JobSpy and public job APIs
        +-- OpenRouter free models
```

```text
signalrank/
├── backend/
│   ├── api/          # FastAPI routes, auth, database models
│   ├── batch/        # Discovery, company enrichment, ranking, worker
│   ├── domain/       # Deterministic scoring functions
│   ├── llm/          # OpenRouter, resume parsing, reputation assessment
│   ├── alembic/      # PostgreSQL migrations
│   └── tests/
├── frontend/
    ├── app/          # Next.js routes
    ├── components/
    ├── lib/          # Typed API client
│   └── types/
└── desktop/          # Tauri shell, sidecar builds, packaging, smoke tests
```

## Local development

### Requirements

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/)
- Node.js 20+
- PostgreSQL with permission to enable the `vector` extension
- An OpenRouter key for structured resume extraction and company reputation assessment

### 1. Start the backend

```bash
cd signalrank/backend
cp .env.example .env
uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Configure `signalrank/backend/.env`:

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/signalrank
NEXTAUTH_SECRET=replace-with-a-long-random-secret
ALLOWED_ORIGINS=["http://localhost:3000"]
OPENROUTER_API_KEY=replace-with-your-openrouter-key
```

The API health check is available at `http://localhost:8000/health`.

### 2. Start the frontend

```bash
cd signalrank/frontend
npm ci
npm run dev
```

Create `signalrank/frontend/.env.local`:

```env
AUTH_SECRET=replace-with-a-long-random-secret
NEXTAUTH_SECRET=replace-with-a-long-random-secret
AUTH_URL=http://localhost:3000
AUTH_TRUST_HOST=true
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Open `http://localhost:3000` and register a local account.

## Database migrations

Run migrations from `signalrank/backend`:

```bash
uv run alembic upgrade head
uv run alembic current
```

The current schema includes durable run state, job freshness and source telemetry, embedding storage, resume parse metadata, and cached company-reputation assessments.

## Verification

Backend:

```bash
cd signalrank/backend
uv run pytest -q
```

Frontend:

```bash
cd signalrank/frontend
npm run lint
npm run build
```

Tests use isolated dependencies where appropriate. The backend suite also verifies role-agnostic outreach, tailored PDF rendering, and download headers. Live source probes and OpenRouter preflight checks should be run separately because they consume external quotas and depend on current provider availability.

## Deployment

- Backend configuration: [`signalrank/backend/railway.toml`](signalrank/backend/railway.toml)
- Frontend configuration: [`signalrank/frontend/vercel.json`](signalrank/frontend/vercel.json)
- Apply Alembic migrations before serving a new backend revision.
- Keep API keys and database credentials in deployment secrets; never commit `.env` files or resumes.

## Project documentation

- [Changelog](CHANGELOG.md)
- [Recall, relevance, and robustness roadmap](docs/2026-07-15-saas-recall-relevance-roadmap.md)
- [Engineering guidance](AGENTS.md)
