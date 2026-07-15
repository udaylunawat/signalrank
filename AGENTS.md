# SignalRank engineering guide

## Scope

The active product is the SaaS application under `signalrank/`:

- `signalrank/backend`: FastAPI, PostgreSQL/pgvector, Alembic, durable worker, discovery, ranking, and OpenRouter integrations.
- `signalrank/frontend`: Next.js application for onboarding, matches, preferences, and tracking.

Legacy Job Ranker implementations and archived artifacts are intentionally absent from `main`. Use the dated backup branch when historical material is needed; do not restore it to the active tree.

## Product invariants

1. Resume parsing, onboarding, discovery, and ranking must remain profession- and role-agnostic.
2. Target roles are user-editable free text, never a fixed preset catalog.
3. Company reputation is assessed independently of candidate fit using free OpenRouter models.
4. LLM and source failures must degrade visibly without discarding resumes or crashing complete refresh runs.
5. Ranking combines semantic relevance with bounded, explainable deterministic signals.
6. Personal resumes, credentials, local databases, caches, and generated output must never be committed.

## Commands

Backend:

```bash
cd signalrank/backend
uv sync --extra dev
uv run alembic upgrade head
uv run pytest -q
uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd signalrank/frontend
npm ci
npm run lint
npm run build
npm run dev
```

## Code style

- Python 3.11+, Black/Ruff/isort conventions, line length 88.
- TypeScript should pass ESLint and the production Next.js build.
- Prefer editing existing files and deleting dead paths over compatibility shims.
- Keep comments for non-obvious constraints rather than narrating straightforward code.
- Run the relevant full test and build gates before committing to `main`.

## Security

- Load secrets only from environment variables or ignored `.env` files.
- Never print, commit, or copy API keys, auth tokens, passwords, or resume contents into logs and documentation.
- Treat live OpenRouter and job-source checks as separate probes because they use external services and quotas.
