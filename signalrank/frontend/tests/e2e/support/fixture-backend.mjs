import { createServer } from "node:http";
import { randomUUID } from "node:crypto";

const JOBS = [
  {
    id: "11111111-1111-4111-8111-111111111111",
    title: "Senior Product Engineer",
    company: "Northstar Labs",
    location: "Remote",
    site: "remotive",
    job_url: "https://jobs.example.test/northstar-product-engineer",
    date_posted: "2026-07-31T08:00:00Z",
    description: "Build reliable product workflows with TypeScript, Python, and SQL.",
    final_score: 91,
    semantic_score: 89,
    skills_score: 94,
    company_score: 86,
    seniority_score: 90,
    location_score: 100,
    recency_score: 95,
    company_tier: "tier_s",
    company_reputation_confidence: 0.95,
    company_reputation_rationale: "Strong engineering reputation and durable product focus.",
    explanation: {
      role_fit: { lane: "primary", title_similarity: 0.92 },
      matched_skills: ["TypeScript", "Python", "SQL"],
      concerns: ["The role spans product and platform responsibilities."],
    },
    is_contract: false,
  },
  {
    id: "22222222-2222-4222-8222-222222222222",
    title: "Backend Engineer",
    company: "Acme Systems",
    location: "Bengaluru",
    site: "indeed",
    job_url: "https://jobs.example.test/acme-backend-engineer",
    date_posted: "2026-07-29T08:00:00Z",
    description: "Own APIs, background workers, and observability for a growing platform.",
    final_score: 76,
    semantic_score: 78,
    skills_score: 82,
    company_score: 70,
    seniority_score: 74,
    location_score: 80,
    recency_score: 90,
    company_tier: "tier_a",
    company_reputation_confidence: 0.82,
    company_reputation_rationale: "Established software organization with strong platform work.",
    explanation: {
      role_fit: { lane: "primary", title_similarity: 0.8 },
      matched_skills: ["Python", "APIs"],
      concerns: [],
    },
    is_contract: false,
  },
  {
    id: "33333333-3333-4333-8333-333333333333",
    title: "Data Platform Contractor",
    company: "Cedar Analytics",
    location: "Hyderabad",
    site: "linkedin",
    job_url: "https://jobs.example.test/cedar-data-platform",
    date_posted: "2026-07-20T08:00:00Z",
    description: "Improve data pipelines and analytics infrastructure for customer teams.",
    final_score: 62,
    semantic_score: 65,
    skills_score: 60,
    company_score: 64,
    seniority_score: 58,
    location_score: 55,
    recency_score: 75,
    company_tier: "tier_b",
    company_reputation_confidence: 0.8,
    company_reputation_rationale: "Established employer with limited public evidence.",
    explanation: {
      role_fit: { lane: "broader", title_similarity: 0.63 },
      matched_skills: ["SQL"],
      concerns: ["This role is more data-platform focused than the target role."],
    },
    is_contract: true,
  },
];

const SOURCE_STATS = [
  { source: "remotive", status: "success", jobs_found: 1, jobs_persisted: 1 },
  { source: "indeed", status: "success", jobs_found: 1, jobs_persisted: 1 },
  { source: "linkedin", status: "success", jobs_found: 1, jobs_persisted: 1 },
  { source: "himalayas", status: "cached", jobs_found: 0, jobs_persisted: 0, cached: true },
  { source: "jobicy", status: "cached", jobs_found: 0, jobs_persisted: 0, cached: true },
];

function json(response, status, body, headers = {}) {
  const payload = JSON.stringify(body);
  response.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    "content-length": Buffer.byteLength(payload),
    ...headers,
  });
  response.end(payload);
}

function readBody(request) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    request.on("data", (chunk) => chunks.push(chunk));
    request.on("end", () => resolve(Buffer.concat(chunks)));
    request.on("error", reject);
  });
}

function requestJson(body) {
  try {
    return JSON.parse(body.toString("utf8"));
  } catch {
    return {};
  }
}

function tokenFrom(request) {
  const header = request.headers.authorization ?? "";
  return header.startsWith("Bearer ") ? header.slice(7) : "";
}

function sourceCounts(jobs) {
  return Object.fromEntries(
    [...new Set(jobs.map((job) => job.site))].map((site) => [
      site,
      jobs.filter((job) => job.site === site).length,
    ]),
  );
}

function createState() {
  return {
    users: new Map(),
    tokens: new Map(),
    profiles: new Map(),
    runs: new Map(),
    applications: new Map(),
    feedback: new Map(),
    desktopKey: false,
    desktopSavedKey: false,
    scenario: "success",
    providerScenario: "success",
    runPolls: 0,
  };
}

function resetState(state) {
  state.users.clear();
  state.tokens.clear();
  state.profiles.clear();
  state.runs.clear();
  state.applications.clear();
  state.feedback.clear();
  state.desktopKey = false;
  state.desktopSavedKey = false;
  state.scenario = "success";
  state.providerScenario = "success";
  state.runPolls = 0;
}

function createProfile() {
  return {
    resume_text: null,
    distilled_text: null,
    target_roles: [],
    target_companies: [],
    preferred_locations: [],
    config_overrides: {},
    onboarding_draft: null,
    resume_parse_status: null,
    resume_parse_error: null,
    resume_parse_confidence: null,
    resume_parser_model: null,
    onboarding_complete: false,
  };
}

function ensureUser(state, email, password = "fixture-password") {
  let user = [...state.users.values()].find((item) => item.email === email);
  if (!user) {
    user = { id: randomUUID(), email, password };
    state.users.set(user.id, user);
    state.profiles.set(user.id, createProfile());
    state.applications.set(user.id, []);
    state.feedback.set(user.id, new Map());
  }
  return user;
}

function authUser(state, request) {
  const token = tokenFrom(request);
  const userId = state.tokens.get(token);
  return userId ? state.users.get(userId) : null;
}

function requireUser(state, request, response) {
  const user = authUser(state, request);
  if (!user) {
    json(response, 401, { detail: "Not authenticated" });
    return null;
  }
  return user;
}

function draftFor(profile) {
  const degraded = profile.resume_parse_status === "degraded";
  return {
    extracted: {
      skills: degraded ? [] : ["TypeScript", "Python", "SQL"],
      years_of_experience: degraded ? 0 : 5,
      recent_titles: degraded ? [] : ["Product Engineer", "Backend Engineer"],
      industries: degraded ? [] : ["Software"],
      location: "Remote",
      parse_status: profile.resume_parse_status ?? "complete",
      parse_confidence: profile.resume_parse_confidence ?? (degraded ? 0.3 : 0.94),
      parse_source: "fixture",
      parser_model: "fixture/model",
      parse_error: degraded ? "OpenRouter was unavailable during extraction" : undefined,
      warnings: degraded ? ["Only deterministic resume text was retained"] : [],
    },
    questions: [
      {
        id: "target_roles",
        text: "What roles are you targeting?",
        type: "multiselect",
        options: ["Product Engineer", "Backend Engineer"],
      },
      {
        id: "preferred_locations",
        text: "Preferred locations? Open to remote?",
        type: "multiselect",
        options: ["Remote only", "Bangalore", "Hyderabad", "Any India"],
      },
      {
        id: "company_tiers",
        text: "Which AI-assessed company reputation tiers should be eligible?",
        type: "multiselect",
        options: ["S-tier (exceptional reputation)", "A-tier (strong reputation)", "Any company"],
      },
      {
        id: "preferred_companies",
        text: "Any companies you especially want to see? Separate names with commas.",
        type: "text",
      },
      {
        id: "excluded_companies",
        text: "Any companies to exclude? Separate names with commas.",
        type: "text",
      },
      {
        id: "excluded_titles",
        text: "Any job titles to exclude? Separate titles with commas.",
        type: "text",
      },
    ],
    answers: profile.onboarding_draft?.answers ?? {},
    current_step: "questions",
    resume_filename: profile.onboarding_draft?.resume_filename ?? "synthetic-resume.txt",
    parser_version: "fixture-v1",
  };
}

function runFor(state, userId) {
  return state.runs.get(userId) ?? null;
}

function jobPayload(state, user, job, includeDescription = false) {
  const feedback = state.feedback.get(user.id)?.get(job.id) ?? null;
  const payload = { ...job, feedback };
  if (!includeDescription) delete payload.description;
  return payload;
}

function visibleJobs(state, user) {
  return runFor(state, user.id) ? JOBS : [];
}

function fixtureProviderResponse(response, scenario, kind) {
  if (scenario === "malformed") {
    response.writeHead(200, { "content-type": "application/json" });
    response.end('{"choices":');
    return;
  }
  if (scenario === "auth") {
    json(response, 401, { error: { type: "authentication_error" } });
    return;
  }
  if (scenario === "rate_limit") {
    json(response, 429, { error: { type: "rate_limit_error" } }, { "retry-after": "1" });
    return;
  }
  if (scenario === "timeout") {
    json(response, 504, { error: { type: "timeout", provider: kind } });
    return;
  }
  if (kind === "openrouter") {
    json(response, 200, {
      id: "fixture-completion",
      model: "fixture/model",
      choices: [{ message: { content: '{"skills":["Python","SQL"]}' }, finish_reason: "stop" }],
    });
    return;
  }
  json(response, 200, {
    source: kind,
    jobs: JOBS.filter((job) => job.site === kind || kind === "all").map((job) => ({
      title: job.title,
      company: job.company,
      job_url: job.job_url,
    })),
  });
}

async function handleRequest(state, request, response) {
  const url = new URL(request.url, "http://fixture.local");
  const path = url.pathname.replace(/^\/+|\/+$/g, "");
  const segments = path ? path.split("/") : [];
  const method = request.method.toUpperCase();

  if (method === "OPTIONS") {
    response.writeHead(204);
    response.end();
    return;
  }
  if (path === "health") {
    json(response, 200, { status: "ok" });
    return;
  }
  if (path === "__fixture__/reset" && method === "POST") {
    resetState(state);
    json(response, 200, { status: "reset" });
    return;
  }
  if (path === "__fixture__/scenario" && method === "POST") {
    const body = requestJson(await readBody(request));
    const scenarios = new Set(["success", "partial", "failed", "cancelled", "running"]);
    state.scenario = scenarios.has(body.name) ? body.name : "success";
    state.runPolls = 0;
    json(response, 200, { status: "scenario-updated", name: state.scenario });
    return;
  }
  if (path === "__fixture__/provider-scenario" && method === "POST") {
    const body = requestJson(await readBody(request));
    const scenarios = new Set(["success", "auth", "rate_limit", "malformed", "timeout"]);
    state.providerScenario = scenarios.has(body.name) ? body.name : "success";
    json(response, 200, { status: "provider-scenario-updated", name: state.providerScenario });
    return;
  }
  if (path === "v1/chat/completions" && method === "POST") {
    await readBody(request);
    fixtureProviderResponse(response, state.providerScenario, "openrouter");
    return;
  }
  if (segments[0] === "__fixture__" && segments[1] === "providers" && segments[2] && method === "GET") {
    fixtureProviderResponse(response, state.providerScenario, segments[2]);
    return;
  }

  if (path === "api/auth/register" && method === "POST") {
    const body = requestJson(await readBody(request));
    if (typeof body.email !== "string" || !body.email.includes("@") || typeof body.password !== "string" || body.password.length < 6) {
      json(response, 422, { detail: "Check your email and password" });
      return;
    }
    if ([...state.users.values()].some((user) => user.email === body.email)) {
      json(response, 409, { detail: "Account already exists" });
      return;
    }
    const user = ensureUser(state, body.email, body.password);
    json(response, 201, { id: user.id, email: user.email });
    return;
  }

  if (path === "api/auth/login" && method === "POST") {
    const body = requestJson(await readBody(request));
    const user = [...state.users.values()].find((item) => item.email === body.email);
    if (!user || user.password !== body.password) {
      json(response, 401, { detail: "Invalid credentials" });
      return;
    }
    const token = `fixture-${randomUUID()}`;
    state.tokens.set(token, user.id);
    json(response, 200, { access_token: token, token_type: "bearer" });
    return;
  }

  if (path === "api/desktop/session" && method === "POST") {
    const user = ensureUser(state, "local@signalrank.desktop", "desktop");
    const token = `fixture-desktop-${randomUUID()}`;
    state.tokens.set(token, user.id);
    json(response, 200, { access_token: token, token_type: "bearer" });
    return;
  }

  if (path === "api/desktop/status" && method === "GET") {
    const user = authUser(state, request) ?? ensureUser(state, "local@signalrank.desktop", "desktop");
    const profile = state.profiles.get(user.id);
    json(response, 200, {
      mode: "desktop",
      provider_configured: state.desktopKey,
      resume_uploaded: Boolean(profile.resume_text),
      onboarding_complete: profile.onboarding_complete,
      user_id: user.id,
    });
    return;
  }

  if (path === "api/desktop/provider-key" && method === "POST") {
    const body = requestJson(await readBody(request));
    if (body.api_key === "invalid") {
      json(response, 400, { detail: "OpenRouter key could not be validated" });
      return;
    }
    state.desktopKey = Boolean(body.api_key);
    state.desktopSavedKey = Boolean(body.api_key);
    json(response, 200, { status: "ok", provider: "openrouter", persistence: "session" });
    return;
  }
  if (path === "api/desktop/provider-key/restore" && method === "POST") {
    if (!state.desktopSavedKey) {
      json(response, 404, { detail: "No saved OpenRouter key could be unlocked" });
      return;
    }
    state.desktopKey = true;
    json(response, 200, { status: "ok", provider: "openrouter" });
    return;
  }
  if (path === "api/desktop/provider-key" && method === "DELETE") {
    state.desktopKey = false;
    json(response, 200, { status: "ok", provider_configured: false });
    return;
  }

  const user = requireUser(state, request, response);
  if (!user) return;
  const profile = state.profiles.get(user.id);

  if (path === "api/profile" && method === "GET") {
    json(response, 200, { user_id: user.id, email: user.email, profile: { ...profile } });
    return;
  }
  if (path === "api/profile" && method === "PATCH") {
    const body = requestJson(await readBody(request));
    if (Array.isArray(body.target_roles)) profile.target_roles = body.target_roles;
    if (Array.isArray(body.preferred_locations)) profile.preferred_locations = body.preferred_locations;
    if (body.config_overrides && typeof body.config_overrides === "object") profile.config_overrides = body.config_overrides;
    json(response, 200, { status: "updated" });
    return;
  }

  if (path === "api/onboarding/status" && method === "GET") {
    json(response, 200, {
      onboarding_complete: profile.onboarding_complete,
      has_resume: Boolean(profile.resume_text),
      draft: profile.onboarding_draft,
      parse_status: profile.resume_parse_status,
      parse_confidence: profile.resume_parse_confidence,
      parse_error: profile.resume_parse_error,
    });
    return;
  }
  if (path === "api/onboarding/resume" && method === "POST") {
    const body = await readBody(request);
    const name = /filename="([^"]+)"/i.exec(body.toString("latin1"))?.[1] ?? "synthetic-resume.txt";
    if (!/\.(pdf|docx|txt)$/i.test(name)) {
      json(response, 422, { detail: "Supported formats: PDF, DOCX, TXT" });
      return;
    }
    if (body.length > 10 * 1024 * 1024) {
      json(response, 413, { detail: "Resume must be 10 MB or smaller" });
      return;
    }
    if (/^empty/i.test(name)) {
      json(response, 422, { detail: "Could not extract text from file" });
      return;
    }
    profile.resume_text = "Synthetic resume fixture. No personal contact details.";
    profile.resume_parse_status = /^degraded|empty/i.test(name) ? "degraded" : "complete";
    profile.resume_parse_confidence = profile.resume_parse_status === "degraded" ? 0.3 : 0.94;
    profile.resume_parser_model = "fixture/model";
    profile.onboarding_complete = false;
    profile.onboarding_draft = { ...draftFor(profile), resume_filename: name };
    json(response, 200, profile.onboarding_draft);
    return;
  }
  if (path === "api/onboarding/resume/retry" && method === "POST") {
    if (!profile.resume_text) {
      json(response, 404, { detail: "Upload a resume first" });
      return;
    }
    profile.resume_parse_status = "complete";
    profile.onboarding_draft = draftFor(profile);
    json(response, 200, profile.onboarding_draft);
    return;
  }
  if (path === "api/onboarding/refine" && method === "POST") {
    const body = requestJson(await readBody(request));
    const draft = profile.onboarding_draft ?? draftFor(profile);
    draft.answers = { ...(draft.answers ?? {}), [body.question_id]: body.answer };
    profile.onboarding_draft = draft;
    if (body.question_id === "target_roles") profile.target_roles = Array.isArray(body.answer) ? body.answer : [body.answer];
    if (body.question_id === "preferred_locations") profile.preferred_locations = Array.isArray(body.answer) ? body.answer : [body.answer];
    if (body.question_id === "onboarding_complete") profile.onboarding_complete = true;
    json(response, 200, { status: "updated" });
    return;
  }

  if (path === "api/runs/trigger" && method === "POST") {
    const current = runFor(state, user.id);
    if (current?.status === "pending" || current?.status === "running") {
      json(response, 202, { ...current, coalesced: true });
      return;
    }
    const scenario = state.scenario;
    const run = {
      run_id: randomUUID(),
      status: scenario === "running" ? "running" : scenario,
      stage: "complete",
      progress: scenario === "running" ? 45 : 100,
      job_count: JOBS.length,
      started_at: "2026-08-01T00:00:00Z",
      finished_at: "2026-08-01T00:00:03Z",
      attempt_count: 1,
      sources: SOURCE_STATS,
    };
    if (scenario === "partial") {
      run.sources = [
        ...SOURCE_STATS,
        {
          source: "indeed",
          status: "partial",
          jobs_found: 0,
          jobs_persisted: 0,
          error_summary: "One bounded query timed out",
        },
      ];
    }
    if (scenario === "failed") {
      run.failure_reason = "All configured job sources failed";
      run.sources = SOURCE_STATS.map((source) => ({
        ...source,
        status: "failed",
        jobs_found: 0,
        jobs_persisted: 0,
        error_summary: "Fixture provider unavailable",
      }));
    }
    if (scenario === "cancelled") run.failure_reason = "The search was cancelled";
    state.runs.set(user.id, run);
    json(response, 202, { ...run, coalesced: false });
    return;
  }
  if (path === "api/runs/latest" && method === "GET") {
    const run = runFor(state, user.id);
    if (!run) {
      json(response, 404, { detail: "No runs found" });
      return;
    }
    json(response, 200, run);
    return;
  }
  if (segments[0] === "api" && segments[1] === "runs" && segments[3] === "status" && method === "GET") {
    const run = runFor(state, user.id);
    if (!run || run.run_id !== segments[2]) {
      json(response, 404, { detail: "Run not found" });
      return;
    }
    if (state.scenario === "running") {
      state.runPolls += 1;
      if (state.runPolls >= 1) {
        run.status = "success";
        run.stage = "complete";
        run.progress = 100;
        run.finished_at = "2026-08-01T00:00:03Z";
      }
    }
    json(response, 200, run);
    return;
  }

  if (path === "api/jobs" && method === "GET") {
    let jobs = visibleJobs(state, user);
    const query = (url.searchParams.get("q") ?? "").trim().toLowerCase();
    const minScore = Number(url.searchParams.get("min_score"));
    const source = (url.searchParams.get("source") ?? "").toLowerCase();
    if (query) jobs = jobs.filter((job) => [job.title, job.company, job.location].some((value) => value.toLowerCase().includes(query)));
    if (Number.isFinite(minScore) && minScore > 0) jobs = jobs.filter((job) => job.final_score >= minScore);
    if (source) jobs = jobs.filter((job) => job.site.toLowerCase() === source);
    const sort = url.searchParams.get("sort") ?? "match";
    if (sort === "newest") jobs.sort((a, b) => b.date_posted.localeCompare(a.date_posted));
    if (sort === "company") jobs.sort((a, b) => a.company.localeCompare(b.company));
    const page = Math.max(1, Number(url.searchParams.get("page")) || 1);
    const limit = Math.min(200, Math.max(1, Number(url.searchParams.get("limit")) || 50));
    const allJobs = visibleJobs(state, user);
    json(response, 200, {
      jobs: jobs.slice((page - 1) * limit, page * limit).map((job) => jobPayload(state, user, job)),
      total: jobs.length,
      page,
      limit,
      run_id: runFor(state, user.id)?.run_id ?? null,
      completed_at: runFor(state, user.id)?.finished_at ?? null,
      strong_count: allJobs.filter((job) => job.final_score >= 70).length,
      source_counts: sourceCounts(allJobs),
    });
    return;
  }
  if (path === "api/jobs/export.csv" && method === "GET") {
    const rows = visibleJobs(state, user);
    const csv = [
      "run_id,run_completed_at,job_id,title,company,location,source,job_url,final_score,score_explanation_json",
      ...rows.map((job) => [runFor(state, user.id)?.run_id ?? "", "2026-08-01T00:00:03Z", job.id, job.title, job.company, job.location, job.site, job.job_url, job.final_score, JSON.stringify(job.explanation)].map((value) => `"${String(value).replaceAll('"', '""')}"`).join(",")),
    ].join("\r\n");
    const payload = `\ufeff${csv}\r\n`;
    response.writeHead(200, {
      "content-type": "text/csv; charset=utf-8",
      "content-disposition": 'attachment; filename="signalrank-jobs-2026-08-01.csv"',
      "content-length": Buffer.byteLength(payload),
    });
    response.end(payload);
    return;
  }
  if (segments[0] === "api" && segments[1] === "jobs" && segments.length === 3 && method === "GET") {
    const job = visibleJobs(state, user).find((item) => item.id === segments[2]);
    if (!job) {
      json(response, 404, { detail: "Job not found" });
      return;
    }
    json(response, 200, { ...jobPayload(state, user, job, true), run_id: runFor(state, user.id)?.run_id, completed_at: runFor(state, user.id)?.finished_at });
    return;
  }
  if (segments[0] === "api" && segments[1] === "jobs" && segments[3] === "feedback") {
    const job = JOBS.find((item) => item.id === segments[2]);
    if (!job) {
      json(response, 404, { detail: "Job not found" });
      return;
    }
    const userFeedback = state.feedback.get(user.id);
    if (method === "PUT") {
      const body = requestJson(await readBody(request));
      const value = { value: body.value, reason: body.reason ?? null };
      userFeedback.set(job.id, value);
      json(response, 200, { job_id: job.id, ...value });
      return;
    }
    if (method === "DELETE") {
      if (!userFeedback.has(job.id)) {
        json(response, 404, { detail: "Feedback not found" });
        return;
      }
      userFeedback.delete(job.id);
      response.writeHead(204);
      response.end();
      return;
    }
  }

  if (path === "api/applications" && method === "GET") {
    json(response, 200, state.applications.get(user.id));
    return;
  }
  if (path === "api/applications" && method === "POST") {
    const body = requestJson(await readBody(request));
    const items = state.applications.get(user.id);
    const existing = items.find((item) => item.job_id && item.job_id === body.job_id);
    if (existing) {
      existing.status = body.status ?? existing.status;
      json(response, 201, { id: existing.id, status: existing.status, created: false });
      return;
    }
    const job = JOBS.find((item) => item.id === body.job_id);
    const item = {
      id: randomUUID(),
      job_id: body.job_id ?? null,
      company: body.company ?? job?.company ?? "",
      title: body.title ?? job?.title ?? "",
      status: body.status ?? "interested",
      applied_at: null,
      notes: body.notes ?? null,
      job_url: job?.job_url ?? null,
      source: job?.site ?? null,
      date_posted: job?.date_posted ?? null,
    };
    items.push(item);
    json(response, 201, { id: item.id, status: item.status, created: true });
    return;
  }
  if (segments[0] === "api" && segments[1] === "applications" && segments.length === 3) {
    const items = state.applications.get(user.id);
    const item = items.find((application) => application.id === segments[2]);
    if (!item) {
      json(response, 404, { detail: "Application not found" });
      return;
    }
    if (method === "PATCH") {
      const body = requestJson(await readBody(request));
      if (body.status) {
        item.status = body.status;
        if (body.status === "applied" && !item.applied_at) item.applied_at = "2026-08-01T00:00:00Z";
      }
      if (body.notes !== undefined) item.notes = body.notes;
      json(response, 200, { status: "updated" });
      return;
    }
    if (method === "DELETE") {
      state.applications.set(user.id, items.filter((application) => application.id !== item.id));
      response.writeHead(204);
      response.end();
      return;
    }
  }

  if (path === "api/resume/templates" && method === "GET") {
    json(response, 200, { templates: ["classic", "minimal", "modern"] });
    return;
  }
  if (path === "api/resume/tailor" && method === "POST") {
    const body = requestJson(await readBody(request));
    if (!["classic", "minimal", "modern"].includes(body.template ?? "classic")) {
      json(response, 422, { detail: "Invalid template" });
      return;
    }
    if (!profile.resume_text) {
      json(response, 404, { detail: "Upload a resume first" });
      return;
    }
    const job = JOBS.find((item) => item.id === body.job_id);
    if (!job) {
      json(response, 404, { detail: "Job not found" });
      return;
    }
    json(response, 200, {
      status: "ok",
      job_id: job.id,
      template: body.template ?? "classic",
      pdf_available: true,
      content: { name: "Synthetic Candidate", position: job.title, skills: ["TypeScript", "Python"] },
    });
    return;
  }

  json(response, 404, { detail: "Not found" });
}

export function createFixtureBackend({ port = 8111 } = {}) {
  const state = createState();
  const server = createServer((request, response) => {
    handleRequest(state, request, response).catch((error) => {
      json(response, 500, { detail: error instanceof Error ? error.message : "Fixture failure" });
    });
  });
  return {
    server,
    state,
    listen() {
      return new Promise((resolve) => server.listen(port, "127.0.0.1", resolve));
    },
    close() {
      return new Promise((resolve) => server.close(resolve));
    },
  };
}

if (process.argv[1]?.endsWith("fixture-backend.mjs")) {
  const fixture = createFixtureBackend({ port: Number(process.env.E2E_FIXTURE_PORT ?? 8111) });
  await fixture.listen();
  process.stdout.write(`fixture-backend-ready:${process.env.E2E_FIXTURE_PORT ?? 8111}\n`);
}
