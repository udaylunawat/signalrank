import type {
  Application,
  ApplicationStatus,
  Job,
  JobListParams,
  JobsResponse,
  OnboardingResumeResponse,
  OnboardingStatus,
  Profile,
  ProfileResponse,
  Run,
  DesktopStatus,
} from "@/types";

function baseUrl() {
  if (typeof window !== "undefined") return "/api/backend";
  const configured =
    process.env.BACKEND_URL ??
    process.env.API_URL_SERVER ??
    process.env.NEXT_PUBLIC_API_URL;
  const desktopMode =
    process.env.SIGNALRANK_MODE === "desktop" ||
    process.env.NEXT_PUBLIC_SIGNALRANK_MODE === "desktop";
  if (desktopMode && !configured) {
    throw new Error("BACKEND_URL is required in desktop mode");
  }
  return (configured ?? "http://localhost:8000").replace(/\/+$/, "");
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function errorDetail(res: Response) {
  const fallback = `Request failed with status ${res.status}`;
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return body.detail;
  } catch {
    return fallback;
  }
  return fallback;
}

async function request<T>(
  path: string,
  options: RequestInit & { token?: string } = {}
): Promise<T> {
  const { token, ...init } = options;
  const headers: Record<string, string> = {
    ...(init.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (
    typeof window === "undefined" &&
    process.env.SIGNALRANK_MODE === "desktop" &&
    process.env.SIGNALRANK_DESKTOP_BOOTSTRAP_TOKEN
  ) {
    headers["X-SignalRank-Desktop-Token"] =
      process.env.SIGNALRANK_DESKTOP_BOOTSTRAP_TOKEN;
  }
  if (!(init.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${baseUrl()}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
  if (!res.ok) {
    throw new ApiError(res.status, await errorDetail(res));
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

async function download(path: string, token: string) {
  const res = await fetch(`${baseUrl()}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new ApiError(res.status, await errorDetail(res));
  }
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1]
    ?? "signalrank-jobs.csv";
  return { blob: await res.blob(), filename };
}

export const api = {
  desktop: {
    status: (token?: string) =>
      request<DesktopStatus>("/api/desktop/status", { token }),
    session: () =>
      request<{ access_token: string; token_type: "bearer" }>(
        "/api/desktop/session",
        { method: "POST" },
      ),
    saveProviderKey: (apiKey: string, token?: string) =>
      request<{
        status: "ok";
        provider: "openrouter";
        persistence: "credential_store" | "session";
      }>("/api/desktop/provider-key", {
        method: "POST",
        token,
        body: JSON.stringify({ provider: "openrouter", api_key: apiKey }),
      }),
    deleteProviderKey: (token?: string) =>
      request<void>("/api/desktop/provider-key", {
        method: "DELETE",
        token,
      }),
  },

  auth: {
    register: (email: string, password: string) =>
      request<{ id: string; email: string }>("/api/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      }),
    login: (email: string, password: string) =>
      request<{ access_token: string; token_type: string }>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      }),
  },

  profile: {
    get: (token: string) =>
      request<ProfileResponse>("/api/profile", { token }),
    patch: (token: string, data: Partial<Profile>) =>
      request<{ status: string }>("/api/profile", {
        method: "PATCH",
        token,
        body: JSON.stringify(data),
      }),
  },

  jobs: {
    list: (token: string, params: JobListParams = {}) => {
      const query = new URLSearchParams();
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== "") query.set(key, String(value));
      });
      const suffix = query.size ? `?${query.toString()}` : "";
      return request<JobsResponse>(`/api/jobs${suffix}`, { token });
    },
    get: (token: string, id: string) =>
      request<Job>(`/api/jobs/${id}`, { token }),
    exportCsv: (token: string) => download("/api/jobs/export.csv", token),
  },

  runs: {
    trigger: (token: string) =>
      request<{ run_id: string; status: string }>("/api/runs/trigger", {
        method: "POST",
        token,
      }),
    latest: (token: string) =>
      request<Run>("/api/runs/latest", { token }),
    status: (token: string, runId: string) =>
      request<Run>(`/api/runs/${runId}/status`, { token }),
  },

  applications: {
    list: (token: string) =>
      request<Application[]>("/api/applications", { token }),
    create: (token: string, data: Partial<Application>) =>
      request<{ id: string; status: ApplicationStatus }>("/api/applications", {
        method: "POST",
        token,
        body: JSON.stringify(data),
      }),
    update: (token: string, id: string, data: Partial<Application>) =>
      request<{ status: "updated" }>(`/api/applications/${id}`, {
        method: "PATCH",
        token,
        body: JSON.stringify(data),
      }),
    delete: (token: string, id: string) =>
      request<void>(`/api/applications/${id}`, {
        method: "DELETE",
        token,
      }),
  },

  onboarding: {
    status: (token: string) =>
      request<OnboardingStatus>("/api/onboarding/status", { token }),
    uploadResume: (token: string, file: File) => {
      const form = new FormData();
      form.append("file", file);
      return request<OnboardingResumeResponse>(
        "/api/onboarding/resume",
        { method: "POST", token, body: form }
      );
    },
    refine: (token: string, question_id: string, answer: string | string[]) =>
      request<{ status: string }>("/api/onboarding/refine", {
        method: "POST",
        token,
        body: JSON.stringify({ question_id, answer }),
      }),
  },
};
