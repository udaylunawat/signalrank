import type {
  Application,
  JobFeedbackRequest,
  JobFeedbackResponse,
  Job,
  JobPreferencesResponse,
  JobsResponse,
  ProfileFreshRequest,
  ProfileFreshResponse,
  TrackerStats,
  InboxBucket,
  InboxResponse,
  InboxSummary,
  ReviewDecision,
} from "@/types";

import { request } from "./core";

export type JobsListParams = {
  runId?: string;
  page?: number;
  limit?: number;
  sort?: "final_score" | "semantic_score" | "skills_score" | "company_score" | "seniority_score" | "location_score" | "recency_score" | "date_posted";
  sortDir?: "asc" | "desc";
  search?: string;
  showArchived?: boolean;
  minScore?: number;
  tiers?: string[];
  jobType?: "all" | "fte" | "contract";
  sites?: string[];
  dateRange?: "any" | "24h" | "week" | "month";
  matchQuality?: "all" | "strong" | "review";
};

export const jobsApi = {
  list: (token: string, params: JobsListParams = {}) => {
    const {
      page = 1,
      limit = 50,
      sort = "final_score",
      sortDir = "desc",
      runId,
      search = "",
      showArchived = false,
      minScore = 0,
      tiers = [],
      jobType = "all",
      sites = [],
      dateRange = "any",
      matchQuality = "all",
    } = params;
    const qs = new URLSearchParams({
      page: String(page),
      limit: String(limit),
      sort,
      sort_dir: sortDir,
      show_archived: String(showArchived),
      min_score: String(minScore),
      job_type: jobType,
      date_range: dateRange,
      match_quality: matchQuality,
    });
    if (runId) qs.set("run_id", runId);
    if (search) qs.set("search", search);
    for (const tier of tiers) qs.append("tiers", tier);
    for (const site of sites) qs.append("sites", site);
    return request<JobsResponse>(`/api/jobs?${qs.toString()}`, { token });
  },
  get: (token: string, id: string) => request<Job>(`/api/jobs/${id}`, { token }),
  analytics: (token: string) =>
    request<{
      score_distribution: { range: string; count: number }[];
      top_companies: { company: string; count: number }[];
      sites: { site: string; count: number }[];
      total: number;
    }>("/api/jobs/analytics", { token }),
  archiveUnsuitable: (token: string) =>
    request<{ queued: number; message?: string }>("/api/jobs/archive-unsuitable", {
      method: "POST",
      token,
    }),
  archiveStatus: (token: string) =>
    request<{ total: number; done: number; pending: number; running: number; failed: number }>(
      "/api/jobs/archive-status",
      { token }
    ),
  preferences: (token: string) =>
    request<JobPreferencesResponse>("/api/jobs/preferences", { token }),
  feedback: (token: string, data: JobFeedbackRequest) =>
    request<JobFeedbackResponse>("/api/jobs/feedback", {
      method: "POST",
      token,
      body: JSON.stringify({
        run_id: data.runId ?? null,
        feedback_text: data.feedbackText ?? null,
        quick_actions: data.quickActions ?? [],
        job_ids: data.jobIds ?? [],
        session_intent: data.sessionIntent ?? null,
        page: data.page ?? 1,
        limit: data.limit ?? 50,
        sort: data.sort ?? "final_score",
        sort_dir: data.sortDir ?? "desc",
        search: data.search ?? "",
        show_archived: data.showArchived ?? false,
        min_score: data.minScore ?? 0,
        tiers: data.tiers ?? [],
        job_type: data.jobType ?? "all",
        sites: data.sites ?? [],
        date_range: data.dateRange ?? "any",
        match_quality: data.matchQuality ?? "all",
      }),
    }),
  resetPreferences: (token: string, data: { clearAll?: boolean; categories?: string[] } = {}) =>
    request<JobPreferencesResponse>("/api/jobs/preferences/reset", {
      method: "POST",
      token,
      body: JSON.stringify({
        clear_all: data.clearAll ?? false,
        categories: data.categories ?? [],
      }),
    }),
  profileFresh: (token: string, data: ProfileFreshRequest = {}) =>
    request<ProfileFreshResponse>("/api/jobs/profile-fresh", {
      method: "POST",
      token,
      body: JSON.stringify({
        limit: data.limit ?? 30,
        country: data.country ?? "India",
        queries: data.queries ?? [],
        locations: data.locations ?? [],
        sources: data.sources ?? [],
        companies: data.companies ?? [],
      }),
    }),
};

export const inboxApi = {
  visit: (token: string, visitId: string) =>
    request<{ last_visited_at: string; previous_visited_at: string | null }>(
      "/api/inbox/visit", {
        method: "POST",
        token,
        body: JSON.stringify({ client_visit_id: visitId }),
      },
    ),
  summary: (token: string, minScore = 65, today?: string) =>
    request<InboxSummary>(
      `/api/inbox/summary?min_score=${minScore}${today ? `&today=${today}` : ""}`,
      { token },
    ),
  list: (token: string, bucket: InboxBucket, page = 1, minScore = 65, today?: string) =>
    request<InboxResponse>(
      `/api/inbox?bucket=${bucket}&page=${page}&min_score=${minScore}${today ? `&today=${today}` : ""}`,
      { token },
    ),
  update: (
    token: string, jobId: string, state: ReviewDecision, snoozedUntil?: string
  ) =>
    request<{ job_id: string; state: ReviewDecision }>(
      `/api/inbox/${jobId}`,
      {
        token,
        method: "PUT",
        body: JSON.stringify({
          state,
          ...(snoozedUntil ? { snoozed_until: snoozedUntil } : {}),
        }),
      },
    ),
  markPageReviewed: (token: string, jobIds: string[]) =>
    request<{ reviewed: number }>("/api/inbox/mark-page-reviewed", {
      token,
      method: "POST",
      body: JSON.stringify({ job_ids: jobIds }),
    }),
};

export const applicationsApi = {
  list: (token: string) =>
    request<{ applications: Application[]; total: number }>("/api/applications?limit=200", { token })
      .then((r) => r.applications),
  trackedJobIds: (token: string) =>
    request<{ job_ids: string[] }>("/api/applications/tracked-job-ids", { token })
      .then((r) => r.job_ids),
  create: (token: string, data: Partial<Application>) =>
    request<Application>("/api/applications", {
      method: "POST",
      token,
      body: JSON.stringify(data),
    }),
  update: (token: string, id: string, data: Partial<Application>) =>
    request<Application>(`/api/applications/${id}`, {
      method: "PATCH",
      token,
      body: JSON.stringify(data),
    }),
  delete: (token: string, id: string) =>
    request<void>(`/api/applications/${id}`, {
      method: "DELETE",
      token,
    }),
  patchRecruiter: (
    token: string,
    id: string,
    data: {
      recruiter_name?: string;
      recruiter_email?: string;
      recruiter_linkedin_url?: string;
    }
  ) =>
    request<{ recruiter_id: string }>(`/api/applications/${id}/recruiter`, {
      method: "PATCH",
      token,
      body: JSON.stringify(data),
    }),
  stats: (token: string) => request<TrackerStats>("/api/applications/stats", { token }),
  importFromRun: (token: string, data: { run_id: string; min_score?: number; limit?: number }) =>
    request<{ created: number; skipped: number }>("/api/applications/import-from-run", {
      method: "POST",
      token,
      body: JSON.stringify(data),
    }),
  recruitersByCompany: (token: string, company: string) =>
    request<{ id: string; name: string | null; email: string; linkedin_url: string | null }[]>(
      `/api/applications/recruiters?company=${encodeURIComponent(company)}`,
      { token }
    ),
};

export const recruitersApi = {
  list: (token: string, company?: string) =>
    request<{ id: string; company: string; name: string | null; email: string | null; linkedin_url: string | null; domain: string | null }[]>(
      `/api/recruiters${company ? `?company=${encodeURIComponent(company)}` : ""}`,
      { token }
    ),
  find: (token: string, data: { company: string; domain?: string; max_results?: number }) =>
    request<{
      found: number;
      inserted: number;
      skipped: number;
      recruiters: { name: string | null; email: string | null; linkedin_url: string; domain: string | null; confidence: string }[];
    }>("/api/recruiters/find", {
      method: "POST",
      token,
      body: JSON.stringify(data),
    }),
};

export const ingestApi = {
  extract: (token: string, payload: { url?: string; text?: string }) =>
    request<{
      title: string;
      company: string;
      location: string;
      job_url: string;
      date_posted: string | null;
      description: string;
    }>("/api/jobs/ingest", {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    }),
  confirm: (
    token: string,
    payload: {
      title: string;
      company: string;
      location: string;
      job_url: string;
      date_posted: string | null;
      description: string;
    }
  ) =>
    request<
      | { application_id: string; priority: string }
      | { error: string; application_id?: string }
    >("/api/jobs/ingest/confirm", {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    }),
};
