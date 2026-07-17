"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSession } from "next-auth/react";
import {
  AlertTriangle,
  ArrowRight,
  BriefcaseBusiness,
  CheckCircle2,
  Clock3,
  DatabaseZap,
  RefreshCw,
  Sparkles,
  Target,
} from "lucide-react";
import AppShell from "@/components/app-shell";
import JobCard from "@/components/job-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { Job, JobsResponse, Run, SourceRunStat } from "@/types";

const ACTIVE_STATUSES = new Set<Run["status"]>(["pending", "running"]);

function runLabel(status: Run["status"]) {
  return {
    pending: "Queued",
    running: "Search in progress",
    success: "Search is fresh",
    partial: "Partial coverage",
    failed: "Search failed",
    cancelled: "Search cancelled",
  }[status];
}

function stageLabel(run: Run) {
  if (run.message) return run.message;
  const stage = run.stage?.toLowerCase();
  if (stage?.includes("plan")) return "Planning search queries";
  if (stage?.includes("search") || stage?.includes("ingest")) return "Searching job sources";
  if (stage?.includes("dedup")) return "Removing duplicate roles";
  if (stage?.includes("assess") || stage?.includes("compan")) {
    return "Checking top employers with OpenRouter";
  }
  if (stage?.includes("rank") || stage?.includes("score")) return "Ranking matches";
  return run.status === "pending" ? "Waiting for a worker" : "Updating your matches";
}

function sourceName(stat: SourceRunStat) {
  return stat.provider ?? stat.source ?? "Unknown source";
}

export default function DashboardPage() {
  const { data: session } = useSession();
  const token = (session as { accessToken?: string })?.accessToken ?? "";

  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobsMeta, setJobsMeta] = useState<JobsResponse | null>(null);
  const [run, setRun] = useState<Run | null>(null);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [error, setError] = useState("");
  const runId = run?.run_id;
  const runStatus = run?.status;

  const loadJobs = useCallback(async () => {
    if (!token) return;
    const response = await api.jobs.list(token, { page: 1, limit: 10, sort: "match" });
    setJobs(response.jobs);
    setJobsMeta(response);
  }, [token]);

  useEffect(() => {
    if (!token) return;
    let active = true;
    Promise.all([
      api.jobs.list(token, { page: 1, limit: 10, sort: "match" }),
      api.runs.latest(token).catch(() => null),
    ])
      .then(([jobsResponse, latestRun]) => {
        if (!active) return;
        setJobs(jobsResponse.jobs);
        setJobsMeta(jobsResponse);
        setRun(latestRun);
      })
      .catch(() => active && setError("We couldn’t load your latest matches."))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [token]);

  useEffect(() => {
    if (!token || !runId || !runStatus || !ACTIVE_STATUSES.has(runStatus)) return;
    const activeRunId = runId;
    let active = true;
    let timeout: ReturnType<typeof setTimeout> | undefined;

    async function poll() {
      try {
        const nextRun = await api.runs.status(token, activeRunId);
        if (!active) return;
        setRun(nextRun);
        if (ACTIVE_STATUSES.has(nextRun.status)) {
          timeout = setTimeout(poll, 2000);
          return;
        }
        await loadJobs();
        if (nextRun.status === "failed") {
          setError(nextRun.failure_reason || nextRun.error_summary || "The search failed before new matches were ready.");
        }
      } catch {
        if (active) timeout = setTimeout(poll, 4000);
      }
    }

    timeout = setTimeout(poll, 800);
    return () => {
      active = false;
      if (timeout) clearTimeout(timeout);
    };
  }, [loadJobs, runId, runStatus, token]);

  const strongMatches = jobsMeta?.strong_count ?? jobs.filter((job) => (job.final_score ?? 0) >= 70).length;
  const runActive = Boolean(run && ACTIVE_STATUSES.has(run.status));
  const progress = run?.progress == null
    ? run?.status === "pending" ? 8 : 45
    : Math.min(100, Math.max(0, run.progress <= 1 ? run.progress * 100 : run.progress));
  const sourceStats = useMemo(() => {
    if (run?.source_stats?.length) return run.source_stats;
    if (run?.sources?.length) {
      const bySource = new Map<string, SourceRunStat>();
      run.sources.forEach((stat) => {
        const name = sourceName(stat);
        const current = bySource.get(name);
        const statuses = [current?.status, stat.status].filter(Boolean);
        const mixedFailure = statuses.includes("failed") && statuses.some((status) => status !== "failed");
        bySource.set(name, {
          source: name,
          status: mixedFailure || current?.status === "partial" ? "partial" : stat.status,
          jobs_found: (current?.jobs_found ?? 0) + (stat.jobs_found ?? 0),
          jobs_persisted: (current?.jobs_persisted ?? 0) + (stat.jobs_persisted ?? 0),
          error_summary: current?.error_summary ?? stat.error_summary,
          cached: current?.cached || stat.cached,
        });
      });
      return Array.from(bySource.values());
    }
    return Object.entries(run?.source_counts ?? jobsMeta?.source_counts ?? {}).map(([source, count]): SourceRunStat => ({
      source,
      status: "success",
      normalized_count: count,
    }));
  }, [jobsMeta?.source_counts, run?.source_counts, run?.source_stats, run?.sources]);

  async function triggerRun() {
    if (!token || triggering || runActive) return;
    setTriggering(true);
    setError("");
    try {
      const response = await api.runs.trigger(token);
      setRun({
        run_id: response.run_id,
        status: response.status as Run["status"],
        started_at: new Date().toISOString(),
        finished_at: null,
        job_count: null,
        stage: "planning",
      });
    } catch {
      setError("We couldn’t start a new search. Try again in a moment.");
    } finally {
      setTriggering(false);
    }
  }

  return (
    <AppShell>
      <section className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-primary/10 bg-primary/7 px-3 py-1.5 text-xs font-medium text-primary">
            <Sparkles className="size-3.5" />
            Your search, distilled
          </div>
          <h1 className="page-title">Focus on the roles that fit.</h1>
          <p className="page-copy max-w-2xl">
            SignalRank weighs relevance, skills, seniority, and company quality so you can decide faster.
          </p>
        </div>
        <Button
          type="button"
          size="lg"
          className="h-10 rounded-xl px-4 shadow-[0_8px_22px_rgba(83,65,195,0.2)]"
          onClick={triggerRun}
          disabled={triggering || runActive || !token}
        >
          <RefreshCw className={triggering || runActive ? "animate-spin" : ""} data-icon="inline-start" />
          {triggering ? "Starting search…" : runActive ? "Refreshing matches…" : "Refresh matches"}
        </Button>
      </section>

      {error && (
        <div role="alert" className="mt-6 rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {runActive && run && (
        <section className="surface-panel mt-6 overflow-hidden p-4 sm:p-5" aria-live="polite">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
                <RefreshCw className="size-4 animate-spin" />
              </span>
              <div>
                <p className="text-sm font-semibold">{stageLabel(run)}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Results will update automatically. It’s safe to leave this page.
                </p>
              </div>
            </div>
            <span className="text-xs font-semibold tabular-nums text-primary">{Math.round(progress)}%</span>
          </div>
          <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-muted">
            <div className="h-full rounded-full bg-primary transition-[width] duration-500" style={{ width: `${progress}%` }} />
          </div>
        </section>
      )}

      {run?.status === "partial" && (
        <div className="mt-6 flex gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          <div>
            <p className="font-medium">Some sources could not be refreshed.</p>
            <p className="mt-0.5 text-xs text-amber-800">Available matches are shown below; source details identify any gaps.</p>
          </div>
        </div>
      )}

      <section className="mt-8 grid gap-3 sm:grid-cols-3">
        <div className="surface-panel p-4 sm:p-5">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Ranked roles</span>
            <BriefcaseBusiness className="size-4 text-primary" />
          </div>
          <p className="mt-3 text-2xl font-semibold tracking-[-0.04em] tabular-nums">
            {loading ? "—" : jobsMeta?.total ?? run?.job_count ?? jobs.length}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">From your latest completed search</p>
        </div>
        <div className="surface-panel p-4 sm:p-5">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Strong matches</span>
            <Target className="size-4 text-emerald-600" />
          </div>
          <p className="mt-3 text-2xl font-semibold tracking-[-0.04em] tabular-nums">
            {loading ? "—" : strongMatches}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">70% match or better</p>
        </div>
        <div className="surface-panel p-4 sm:p-5">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Search status</span>
            {run?.status === "failed" || run?.status === "partial" ? (
              <AlertTriangle className="size-4 text-amber-600" />
            ) : (
              <CheckCircle2 className="size-4 text-indigo-600" />
            )}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Badge variant={run?.status === "failed" ? "destructive" : "secondary"}>
              {run ? runLabel(run.status) : "Not started"}
            </Badge>
            {run?.cached && <Badge variant="outline">Cached results</Badge>}
            {run?.stale && <Badge variant="outline">May be stale</Badge>}
          </div>
          <p className="mt-2 flex items-center gap-1 text-xs text-muted-foreground">
            <Clock3 className="size-3" />
            {jobsMeta?.completed_at ? `Completed ${new Date(jobsMeta.completed_at).toLocaleString()}` : "Ready when you are"}
          </p>
        </div>
      </section>

      {sourceStats.length > 0 && (
        <section className="mt-6 surface-panel p-4 sm:p-5">
          <div className="flex items-center gap-2">
            <DatabaseZap className="size-4 text-primary" />
            <h2 className="text-sm font-semibold">Source coverage</h2>
          </div>
          <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {sourceStats.map((stat, index) => {
              const failed = stat.status === "failed" || (!stat.status && Boolean(stat.error || stat.error_summary));
              const degraded = stat.status === "partial";
              const cached = stat.status === "cached" || stat.cached;
              const count = stat.jobs_persisted ?? stat.deduped_count ?? stat.normalized_count ?? stat.jobs_found ?? stat.raw_count;
              return (
                <div key={`${sourceName(stat)}-${index}`} className="rounded-xl border border-border/70 bg-muted/30 px-3 py-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-xs font-semibold capitalize">{sourceName(stat)}</span>
                    <span className={failed ? "text-[11px] font-medium text-destructive" : degraded || cached ? "text-[11px] font-medium text-amber-700" : "text-[11px] font-medium text-emerald-700"}>
                      {failed ? "Failed" : degraded ? "Degraded" : cached ? "Cached" : "Healthy"}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {failed ? stat.error || stat.error_summary || "No fresh results" : `${count ?? 0} roles found${degraded ? " · some queries failed" : ""}`}
                  </p>
                </div>
              );
            })}
          </div>
        </section>
      )}

      <section className="mt-10">
        <div className="mb-4 flex items-end justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold tracking-[-0.025em]">Best matches right now</h2>
            <p className="mt-1 text-sm text-muted-foreground">The highest-signal roles from your latest completed run.</p>
          </div>
          <Link href="/jobs" className="hidden items-center gap-1 text-sm font-medium text-primary sm:flex">
            View all
            <ArrowRight className="size-4" />
          </Link>
        </div>

        <div className="space-y-3">
          {loading && Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="h-40 animate-pulse rounded-2xl border border-border/70 bg-white/60" />
          ))}
          {!loading && jobs.slice(0, 5).map((job) => <JobCard key={job.id} job={job} compact />)}
          {!loading && jobs.length === 0 && (
            <div className="surface-panel px-6 py-12 text-center">
              <span className="mx-auto grid size-12 place-items-center rounded-2xl bg-secondary text-primary">
                <Target className="size-5" />
              </span>
              <h3 className="mt-4 font-semibold">Your first shortlist starts here</h3>
              <p className="mx-auto mt-1 max-w-md text-sm leading-6 text-muted-foreground">
                Run a search and we’ll surface the roles most aligned with your profile.
              </p>
              <Button className="mt-5 rounded-xl" onClick={triggerRun} disabled={triggering || runActive || !token}>
                Refresh matches
              </Button>
            </div>
          )}
        </div>

        <Link href="/jobs" className="mt-4 flex items-center justify-center gap-1 text-sm font-medium text-primary sm:hidden">
          View all matches
          <ArrowRight className="size-4" />
        </Link>
      </section>
    </AppShell>
  );
}
