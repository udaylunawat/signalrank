# SignalRank frontend

The SignalRank frontend is a Next.js 16 application for onboarding, profile preferences, ranked job matches, refresh progress, CSV export, and application tracking.

See the [repository README](../../README.md) for architecture, backend setup, environment variables, migrations, and product behavior.

## Run locally

```bash
npm ci
npm run dev
```

Create `.env.local` before starting:

```env
AUTH_SECRET=replace-with-a-long-random-secret
NEXTAUTH_SECRET=replace-with-a-long-random-secret
AUTH_URL=http://localhost:3000
AUTH_TRUST_HOST=true
NEXT_PUBLIC_API_URL=http://localhost:8000
```

The app runs at `http://localhost:3000` by default.

## Verify

```bash
npm run lint
npm run build
```
