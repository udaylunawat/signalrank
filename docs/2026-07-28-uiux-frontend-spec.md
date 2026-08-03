# SignalRank UI/UX and Frontend Specification

## Status

Validated implementation specification.

Validated against the active checkout on 2026-07-28. This specification covers
both frontend work and the additive backend contracts required to deliver the
defined user experience. It does not authorize changes to retrieval, ranking
weights, score calibration, or company-reputation assessment.

## Product outcome

SignalRank should help a user answer three questions quickly:

1. Which roles deserve attention?
2. Why does SignalRank recommend each role?
3. What should I do next?

The primary product loop is:

```text
resume and preferences
        |
        v
freshness-aware search
        |
        v
explainable matches -> save / give feedback -> application tracker
```

Negative feedback does not mean permanent dismissal. A job may be hidden from
the current view after feedback, but persistent dismissal requires a separately
approved contract defining its effect on search, export, and future ranking.

## Reference direction

Mobbin references were inspected on 2026-07-28:

- [Wellfound job-seeker onboarding](https://mobbin.com/flows/1d7a9eae-bcf5-4c08-ad57-f0a1199dde0d)
- [Wellfound preference setup](https://mobbin.com/flows/a8f36212-29e3-424f-92de-cdb1caaa3008)
- [Glassdoor onboarding completion](https://mobbin.com/flows/ead2edf6-a86f-42dc-bcbf-db97b28ce1b5)
- [Glassdoor job-results screen](https://mobbin.com/screens/1752785a-6589-481a-9fb3-93099d783924)

Adopt only these interaction patterns:

- progressive onboarding with stable, visible progress;
- one primary decision per onboarding section;
- persistent, URL-backed result filters;
- list/detail evaluation on desktop;
- a focused detail surface on mobile.

The links are design inspiration, not acceptance evidence. Do not copy branding,
visual assets, proprietary content, or app-specific behavior.

## Scope

### In scope

- `/onboarding`, `/dashboard`, `/jobs`, `/tracker`, and `/settings`.
- Shared navigation, page headers, cards, alerts, skeletons, filters, sheets,
  dialogs, inline action status, tag inputs, and empty states.
- Match explanation and feedback workflows.
- Additive jobs, feedback, onboarding, run-delta, and application contracts
  explicitly identified in this document.
- SaaS authentication and Tauri local-session behavior.
- Responsive browser behavior and packaged Tauri smoke coverage.
- Accessibility, browser E2E, and visual-regression coverage for changed flows.

### Out of scope

- Changing ranking weights, feedback penalties, score calibration, retrieval,
  job selection, or company-scoring semantics.
- Making structured feedback reasons affect ranking without frozen evaluation
  gates and a separate ranking decision.
- Adding job sources or changing scraper behavior.
- Persistent job dismissal.
- Gmail/email notifications, recruiter discovery, or analytics dashboards.
- Default product telemetry in the local-first desktop application.
- Replacing Next.js, React, Tailwind, Base UI, or the Tauri shell.
- A separate native desktop UI.

## Product invariants

- Target roles remain editable free text and profession-agnostic.
- Company reputation remains independent of candidate fit.
- OpenRouter and source failures remain visible and degrade gracefully.
- Resume-only ranking remains a supported path.
- Job text is untrusted content and must render as plain text.
- SaaS and desktop share components without weakening desktop session, native
  external-link, download, credential, or local-data boundaries.

## Current architecture

- Next.js 16 App Router, React 19, TypeScript, Tailwind CSS 4,
  Base UI/shadcn primitives, Lucide, and NextAuth.
- SaaS and Tauri desktop share the same pages and components.
- Pages own request state, polling, loading, errors, and optimistic updates;
  there is no shared query/cache layer.
- Design tokens and utilities live in
  `signalrank/frontend/app/globals.css`.
- Desktop external links and downloads use
  `signalrank/frontend/lib/desktop.ts`.
- The checkout contains unrelated backend and benchmark changes. Implementation
  commits must stage only the approved slice.

## Validated contract baseline

| Capability | Current support | Required change | Delivery |
| --- | --- | --- | --- |
| Match list | Scores, explanation, source, posted date, contract flag, feedback | Preserve | Slice 1 |
| Match detail | Raw job and description only; not scoped to the user's result | User-scoped detail response containing raw job, latest result, explanation, and feedback | Slice 1 |
| Result filters | Query, minimum score, source, match/newest/company sort | Add contract, saved-only, location, posted-within, and work-mode filters before exposing them | Slice 1 and 1B |
| Feedback reasons | Wrong role, wrong seniority, wrong location, other | Preserve initial enum; defer additional reasons | Slice 1 |
| Onboarding draft | Answers and last question ID | Stable section ID and explicit progress state | Slice 2 |
| Protected routing | Authentication only | Resolve desktop setup and onboarding completion before workspace render | Slice 2 |
| Dashboard | Latest run, latest result totals, source coverage | Add run history/delta only for “what changed” | Slice 3 |
| Tracker | Status, notes, automatic applied date | Fix applied-date update; add next action and interview date fields | Slice 3 |
| Tracker delete | Immediate permanent delete | Delay DELETE during the undo window; soft delete is deferred | Slice 3 |
| Frontend tests | Lint and build only | Establish component, accessibility, browser, and visual test harness | Slice 0 |
| Product metrics | No product-event measurement | Privacy-approved SaaS events or controlled usability study; no default desktop telemetry | Measurement plan |

## Information architecture

Keep the existing top-level navigation:

| Route | Primary job | Primary action |
| --- | --- | --- |
| `/dashboard` | Understand freshness and current opportunity volume | Refresh matches |
| `/jobs` | Evaluate and shortlist roles | Open details, save, give feedback |
| `/tracker` | Move saved roles toward an outcome | Set status or next action |
| `/settings` | Tune search intent | Save preferences |

The dashboard is a status and triage surface. Matches is the evaluation
workspace. Tracker is an execution surface. Settings is configuration, not a
second onboarding form.

## Functional requirements

### FR-01: Explainable match evaluation

Each match detail surface must display:

- final score and qualitative label;
- every non-null score dimension returned for that result;
- matched skills or an explicit unavailable state;
- concerns or an explicit “No concerns identified” state;
- role lane when available;
- company reputation tier, confidence, and rationale when available;
- source, posted date, and search-completion time;
- a plain-text description excerpt;
- external apply action;
- save and feedback actions.

Desktop uses a list/detail layout at widths of 1024px and above. Mobile uses a
sheet or full-screen detail surface. Closing detail restores focus to the
trigger, preserves list scroll position, and retains all URL filter state.

#### Required contract

Replace the current partial detail behavior with a user-scoped
`GET /api/jobs/{job_id}` response that:

- joins the current user's latest completed `JobResult` to `JobRaw`;
- returns the same score, explanation, company, contract, and feedback fields as
  the list response plus the description;
- returns 404 when the job is not in the current user's latest completed result;
- never exposes another user's result or feedback.

Tracker continues using its application response for roles no longer present in
the latest result.

#### Acceptance criteria

- The detail surface renders the final score, every non-null score dimension,
  at least one matched signal or its unavailable state, source/date,
  description excerpt, and apply action.
- The API rejects a job ID outside the current user's latest completed result.
- Missing or degraded fields render explicit unavailable states; the client
  never fabricates values.
- Escape closes the detail surface and focus returns to the opening control.
- A 10,000-character description renders safely as plain text without layout
  overflow or HTML execution.

### FR-02: Efficient match triage

#### Slice 1 filters

Deliver with current server semantics:

- search across role, company, and location;
- match-quality filter;
- source filter;
- sort by match, newest, and company;
- removable filter chips and clear-all;
- compact and comfortable density;
- result range, total count, and pagination.

#### Slice 1B filters

Expose only after additive server-side query parameters exist:

- contract status;
- saved-only;
- location;
- posted-within days;
- canonical work mode: remote, hybrid, onsite, or unknown.

Client-only filtering is prohibited because it would produce incorrect totals,
counts, and pagination. Saved-only must join the current user's applications.
Work mode must use a canonical backend field; it must not depend on frontend
substring guessing.

#### Acceptance criteria

- Filters are represented in the URL and survive refresh and back/forward
  navigation.
- Server responses calculate totals and pagination after every active filter.
- Rapid query/filter changes cancel or ignore stale responses; an older request
  cannot replace newer results.
- Removing the final item from a non-first page navigates to the nearest valid
  page.
- No action target is smaller than 40x40 CSS pixels on touch layouts; 44x44 is
  preferred.
- Action rows do not overflow at 390px viewport width.
- Loading, empty, request error, partial-run, and stale-result states each have a
  semantic label and distinct recovery action.

### FR-03: Corrective feedback

The initial reason picker uses the existing enum:

- Wrong role;
- Wrong seniority;
- Wrong location or work mode;
- Other.

“Company concern” and “Already applied or duplicate” remain deferred until an
additive enum migration and explicit product behavior are approved. Already
applied is primarily a tracker state, not ranking feedback.

After successful negative feedback, the client may hide the card for the
current view and provide Undo by clearing that feedback. The role remains
available after refresh, in search, and in CSV export.

Preference correction is excluded from Slice 1. A future correction flow must
define explicit, user-confirmed mappings. Company concern may add a company to
personal exclusions but must never alter company-reputation assessment.

#### Acceptance criteria

- The API accepts all four displayed reasons and rejects unknown reasons.
- Reason selection persists after a failed submission and remains retryable.
- Card-level feedback uses inline saving, success, and failure states.
- Undo clears the feedback and restores a locally hidden card.
- Feedback does not silently modify preferences, ranking weights, or company
  reputation.

### FR-04: Progressive onboarding

Keep resume upload as the first step, then use stable sections:

1. `profile`: confirm extracted profile and suggested roles.
2. `intent`: choose target roles and locations.
3. `companies`: choose company breadth and exclusions.
4. `review`: review the final profile before starting the first search.

Each section shows progress, optional versus recommended fields, and saving,
saved, or failed-to-sync state. The user can continue with resume-only ranking,
replace the resume, or return to an earlier section without losing saved data.

#### Required contract

- Persist `current_section` separately from the last answered question.
- Accept only `profile`, `intent`, `companies`, `review`, or `complete`.
- Continue storing answers in the existing onboarding draft.
- Do not infer section position from question order or the last question ID.

#### Acceptance criteria

- Refresh restores the persisted section and saved answers.
- Autosave announces saving, saved, and failed-to-sync states.
- The review lists target roles, locations, company mode, and exclusions, and
  labels optional missing values.
- Resume-only completion succeeds without target roles or optional preferences.
- Onboarding completion and first-run trigger have explicit independent failure
  states; a saved profile is not reported as lost when run triggering fails.

### FR-05: Structured preferences

Use the same tag-input behavior for roles, locations, preferred companies,
excluded companies, and excluded titles in onboarding and Settings.

Requirements:

- Enter or comma creates a chip.
- Chips support visible removal, Backspace removal, and screen-reader labels.
- Duplicate values normalize case-insensitively.
- Empty values are not persisted.
- Existing array-backed values load as chips without a data migration.
- A legacy string value, if encountered, normalizes client-side and persists as
  an array only after explicit save.

#### Acceptance criteria

- Onboarding and Settings serialize identical arrays for identical input.
- Duplicate and whitespace-only entries cannot be saved.
- Keyboard-only users can create, focus, and remove every chip.
- Save failure leaves the edited values present and offers retry.

### FR-06: Dashboard triage

Using current contracts, the dashboard displays:

- latest search completion time;
- freshness label derived from `JobsResponse.completed_at`;
- current match count and strong-match count;
- source coverage and partial failure impact;
- a non-blocking universal setup checklist;
- direct links to corresponding filtered Matches views.

The setup checklist may include only:

- resume present;
- at least one target role;
- optional locations configured;
- optional company preferences configured.

Do not display a numeric completeness score.

Use a shared UTC-aware `STALE_AFTER_HOURS = 24` threshold until an authoritative
backend stale flag is approved. The boundary is stale when elapsed time is
greater than or equal to 24 hours.

“What changed since the previous run” is delivered only after an additive
run-history/delta endpoint defines new, removed, and materially score-changed
roles. It is not inferred from the current page of results.

#### Acceptance criteria

- At 1440x900, the first viewport includes completion time, freshness label,
  total, strong count, primary refresh action, and coverage warning when
  applicable.
- Partial coverage names affected sources and states that available results
  remain usable.
- Freshness boundary tests cover 23:59:59, 24:00:00, missing completion time,
  and timezone conversion.
- Refresh progress remains visible and updates until terminal state.
- Any “new” or “changed” count is backed by the approved delta endpoint.

### FR-07: Action-oriented tracker

#### Existing-contract work

- Responsive list view on mobile instead of a forced 1080px board.
- Drag/drop status changes on desktop with a select or menu fallback.
- Notes editing.
- Archive and reject statuses.
- Delayed delete: remove locally, show Undo for 8 seconds, and call DELETE only
  after the window expires.

#### Additive contract work

Fix the existing application update handler so an explicit `applied_at` value is
validated and persisted. Add:

- `next_action: string | null`;
- `next_action_at: datetime | null`;
- `interview_at: datetime | null`;
- corresponding schema migration, API request/response fields, frontend types,
  and desktop database migration.

#### Acceptance criteria

- Mobile uses a single-column list at 390px with no horizontal page scrolling.
- Drag/drop and keyboard status changes persist the same status values.
- Status and notes show saving and retryable failure states.
- Undo within 8 seconds prevents DELETE from being sent.
- Every active item renders its next-action label/date or an “Add next action”
  control.
- Desktop migration testing preserves existing applications, statuses, notes,
  and applied dates.

### FR-08: Account, session, and onboarding access

Provide account/session access in the mobile header:

- SaaS displays the current account and sign-out.
- Tauri displays local-workspace state and provider/setup access without a SaaS
  sign-out action.

After authentication, resolve desktop setup and onboarding status before
rendering protected workspace pages.

Routing order:

1. Unauthenticated SaaS users go to login with the intended destination.
2. Desktop users with incomplete provider/resume setup go to `/desktop-setup`.
3. Users with a resume but incomplete onboarding go to `/onboarding`.
4. Complete users continue to the intended workspace route.

Status-fetch failure shows a recoverable error. It must not be interpreted as
incomplete onboarding and must not cause a redirect loop.

#### Acceptance criteria

- Intended destination is preserved through SaaS login and onboarding.
- Desktop setup takes precedence over the shared onboarding guard.
- A failed status request renders Retry and does not redirect.
- Mobile SaaS users can sign out from every protected route.
- Desktop local session bootstrap behavior remains unchanged.

## Shared component specification

| Component | Required behavior |
| --- | --- |
| `PageHeader` | Eyebrow, title, supporting copy, primary/secondary actions |
| `StatusAlert` | Info, success, warning, error, partial, stale variants |
| `EmptyState` | Icon, title, explanation, primary action, optional recovery |
| `LoadingSkeleton` | Route-specific layout-preserving skeletons |
| `SegmentedControl` | Arrow-key navigation, selected state, mobile wrapping |
| `TagInput` | Chip creation, deletion, deduplication, accessible labels |
| `FilterBar` | URL-backed filters, chips, clear-all, mobile sheet |
| `InlineActionStatus` | Saving, success, retryable error adjacent to card action |
| `Toast` | Export confirmation and delayed-delete Undo only |
| `JobDetailSheet` | Explanation, apply, save, feedback, focus/escape behavior |
| `ConfirmDialog` | Destructive action confirmation and cancel path |
| `TrackerItem` | Shared board/list content and action affordances |

Use inline status for card-level save and feedback actions. Do not use a toast
for a retryable failure that belongs to a specific control.

All components use design tokens rather than page-specific hardcoded colors.
Existing shadcn/Base UI primitives remain the implementation base.

## Non-functional requirements

### Accessibility

Changed flows conform to WCAG 2.2 AA:

- automated axe checks have zero serious or critical violations;
- sheets and dialogs expose names, trap focus, close on Escape, and restore focus
  to the trigger;
- all actions are keyboard operable;
- status is communicated by text or accessible name in addition to color;
- text contrast is at least 4.5:1 and large-text/UI contrast is at least 3:1;
- controls are at least 40x40 CSS pixels on touch layouts;
- reduced-motion users receive equivalent, non-animated state information.

### Responsive matrix

Required browser viewports:

- mobile: 390x844;
- tablet: 768x1024;
- desktop: 1440x900.

Browser E2E runs in Chromium for every pull request. Critical authentication,
onboarding, Matches, and tracker journeys also run in current Firefox and
WebKit before release.

### Request and state integrity

- Abort or ignore stale requests when URL filters change.
- Prevent duplicate save, feedback, refresh, and status-update submissions.
- Preserve filter, pagination, density, and selected-detail state through
  expected navigation.
- Define recovery for every request mutation.

### Content and navigation security

- Render job descriptions and explanations as text, never unsanitized HTML.
- Validate external URLs through the existing desktop-aware helper.
- Open only approved `https://` job URLs; reject unsupported schemes.
- Do not log resume content, job-description content, credentials, or
  authorization headers from UI flows.

### Performance

Using a seeded local environment with 50 returned jobs:

- the filter bar remains interactive while results load;
- opening already-fetched detail UI responds within 200ms at P95;
- filter changes show a pending state within 100ms;
- list rendering introduces no horizontal layout shift at required viewports;
- visual snapshots use deterministic data, fonts, and animation disabling.

Network and backend latency are recorded separately from client interaction
budgets.

## Visual and interaction rules

- Maintain the existing restrained violet/indigo visual language.
- Reduce decorative glass effects where they compete with information hierarchy.
- Use one dominant action per surface.
- Keep headings, scores, and action labels readable at mobile widths.
- Use semantic status labels plus color, never color alone.
- Respect `prefers-reduced-motion`.
- Either complete dark mode for every shared component or keep theme switching
  unsupported; do not ship partial dark mode.

## Delivery sequence

### Slice 0: Contracts and quality harness

Deliver before the first redesign:

- finalize the user-scoped job-detail response;
- document additive filter query parameters and pagination semantics;
- add component-test and Playwright configuration;
- add axe integration and deterministic visual fixtures;
- establish SaaS browser and desktop-configured browser test modes;
- preserve the existing lint and production-build gates.

Exit criteria:

- The current critical onboarding-to-Matches journey runs in Chromium.
- At least one shared component test, axe test, and visual snapshot runs in CI.
- Contract tests cover user-scoped job detail and every supported feedback enum.

### Slice 1: Matches foundation

Primary files:

- `signalrank/frontend/components/job-card.tsx`;
- `signalrank/frontend/app/jobs/page.tsx`;
- `signalrank/frontend/lib/api.ts`;
- `signalrank/frontend/types/index.ts`;
- `signalrank/backend/api/routes/jobs.py`;
- shared components under `signalrank/frontend/components/`.

Deliver FR-01, FR-02 Slice 1 filters, and FR-03.

Exit criteria:

- Top matches are explainable in-app.
- Current-contract filters, details, feedback, loading, errors, and mobile
  actions satisfy their objective acceptance criteria.
- CSV export, desktop-aware external links/downloads, and tracking still work.
- No ranking score, weight, penalty, or job selection changes.

### Slice 1B: Additive match filters

Add and test server-side contract status, saved-only, location, posted-within,
and canonical work-mode filters. Defer any filter lacking a stable backend
field.

Exit criteria:

- Counts and pagination reflect every filter.
- API contract tests cover individual and combined filters.
- Browser tests cover URL restoration and rapid-filter race handling.

### Slice 2: Onboarding, Settings, and guards

Primary files:

- `signalrank/frontend/app/onboarding/page.tsx`;
- `signalrank/frontend/app/settings/page.tsx`;
- `signalrank/frontend/components/app-shell.tsx`;
- route/session guard code;
- `signalrank/backend/api/routes/onboarding.py`;
- shared UI components and design tokens.

Deliver FR-04, FR-05, and FR-08.

Exit criteria:

- Stable onboarding sections restore correctly.
- Array-backed chips replace comma-field editing.
- Resume-only, degraded extraction, autosave failure, first-run failure, and
  resume replacement remain recoverable.
- Routing tests prove SaaS, desktop setup, incomplete onboarding, status-fetch
  failure, and intended-destination behavior.

### Slice 3: Dashboard and Tracker

Primary files:

- `signalrank/frontend/app/dashboard/page.tsx`;
- `signalrank/frontend/app/tracker/page.tsx`;
- run and application API routes, models, migrations, and types.

Deliver FR-06 and FR-07. Add “what changed” only with its delta contract.

Exit criteria:

- Dashboard freshness, coverage, and next action satisfy FR-06.
- Tracker is usable at all required viewports.
- Application migrations preserve SaaS and desktop data.
- Delete Undo, applied-date editing, notes, next action, and interview date have
  API and browser coverage.

### Slice 4: Release hardening

- Run full cross-browser browser journeys.
- Complete accessibility and manual screen-reader checks.
- Review visual snapshots at every required viewport.
- Run packaged Tauri smoke tests separately from desktop-configured browser E2E.
- Validate migration and data preservation on packaged desktop upgrades.

Packaged Tauri smoke tests cover:

- local-session bootstrap;
- credential persistence or documented session-only fallback;
- native external job links;
- native CSV downloads;
- application-data migration and preservation.

Passing Next.js with a desktop environment variable does not prove packaged
Tauri behavior.

## Validation matrix

| Area | Required checks |
| --- | --- |
| Auth | Login, signup errors, session expiry, SaaS sign-out, intended destination |
| Desktop setup | Local-session bootstrap, provider state, setup precedence |
| Onboarding | Upload, complete/degraded parse, stable section restore, autosave failure, resume replacement, resume-only path |
| Refresh | Start, coalescing, poll, partial source failure, stale boundary, terminal failure |
| Matches | Search, filters, pagination, request race, detail focus/scroll, save, feedback/undo, export |
| Job content | Long text, plain-text rendering, unsupported external URL scheme |
| Tracker | Empty state, save from Matches, status/notes/dates, mobile list, delayed delete/undo |
| Settings | Load arrays as chips, keyboard editing, duplicate normalization, save failure |
| Accessibility | Keyboard-only flow, focus trap/return, labels, axe, contrast, reduced motion |
| Visual | 390x844, 768x1024, 1440x900 with deterministic data |
| Regression | Existing backend contracts, desktop helpers, unchanged ranking results |
| Packaged Tauri | Local session, native links/downloads, migration and data preservation |

## Measurement plan

Behavioral product metrics are not an implementation gate until a
privacy-approved measurement method exists.

### SaaS

If approved, use named, minimal UI events with no resume text, job description,
credentials, or sensitive free text. Define event, denominator, observation
window, viewport cohort, minimum sample, baseline, target, and guardrail before
collection.

Candidate measures:

| Measure | Definition | Initial target |
| --- | --- | --- |
| Time to first save | Median time from Matches rendered to first successful save | Improve at least 20% from baseline |
| Explained outbound click | Outbound apply clicks preceded by opening job detail | Observe; do not treat as completed application |
| Actionable feedback rate | Negative feedback with wrong-role, wrong-seniority, or wrong-location reason / all negative feedback | At least 70% |
| Onboarding completion | Completed onboarding / valid resume uploads in the same seven-day window | Improve without reducing resume-only success |
| Mutation error rate | Failed save, feedback, status, refresh, or export requests / attempts | Below 1% |

### Desktop

Do not add default SignalRank telemetry. Measure through:

- automated local test output;
- controlled usability sessions;
- optional future opt-in diagnostics approved separately.

### Guardrails

- UI changes do not claim ranking-quality improvement.
- Ranking metrics remain governed by the frozen relevance evaluation process.
- Feedback reasons remain diagnostic unless a separate evaluated ranking change
  is approved.

## Definition of done

- Every delivered requirement has automated acceptance coverage in the same
  slice; testing is not deferred to Slice 4.
- Additive contracts have backend tests, migrations where required, and updated
  frontend types.
- SaaS and Tauri paths preserve session and external-action boundaries.
- `npm run lint` and `npm run build` pass from `signalrank/frontend`.
- Relevant backend tests pass.
- Chromium journeys pass at all required viewport sizes.
- Release candidates pass Firefox, WebKit, and packaged Tauri gates.
- Changed flows meet WCAG 2.2 AA criteria defined in this document.
- Visual-regression changes are reviewed intentionally.
- No unrelated backend, benchmark, resume, credential, database, cache, or
  generated files are included in implementation commits.
