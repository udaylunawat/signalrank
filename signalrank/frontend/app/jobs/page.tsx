"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useSession } from "next-auth/react";
import { Search, SlidersHorizontal, Sparkles } from "lucide-react";
import AppShell from "@/components/app-shell";
import JobCard from "@/components/job-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { Job, JobListParams } from "@/types";

type ScoreFilter = "all" | "excellent" | "strong";
type SortOption = NonNullable<JobListParams["sort"]>;

function scoreFromFilter(filter: ScoreFilter) {
  if (filter === "excellent") return 80;
  if (filter === "strong") return 65;
  return undefined;
}

function filterFromScore(score: string | null): ScoreFilter {
  if (score === "80") return "excellent";
  if (score === "65") return "strong";
  return "all";
}

function JobsPageContent() {
  const { data: session } = useSession();
  const token = (session as { accessToken?: string })?.accessToken ?? "";
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const page = Math.max(1, Number(searchParams.get("page")) || 1);
  const scoreFilter = filterFromScore(searchParams.get("min_score"));
  const sortParam = searchParams.get("sort");
  const sort: SortOption = sortParam === "newest" || sortParam === "company" ? sortParam : "match";
  const source = searchParams.get("source") ?? "";

  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState(searchParams.get("q") ?? "");
  const [sourceCounts, setSourceCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tracked, setTracked] = useState<Set<string>>(new Set());
  const [trackingId, setTrackingId] = useState<string | null>(null);
  const limit = 50;

  function updateParams(updates: Record<string, string | number | undefined>, resetPage = true) {
    const next = new URLSearchParams(searchParams.toString());
    Object.entries(updates).forEach(([key, value]) => {
      if (value === undefined || value === "") next.delete(key);
      else next.set(key, String(value));
    });
    if (resetPage && !("page" in updates)) next.delete("page");
    const nextQuery = next.toString();
    router.replace(nextQuery ? `${pathname}?${nextQuery}` : pathname, { scroll: false });
  }

  useEffect(() => {
    const urlQuery = searchParams.get("q") ?? "";
    if (urlQuery !== query) setQuery(urlQuery);
    // Only synchronize when browser navigation changes the URL.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  useEffect(() => {
    const urlQuery = searchParams.get("q") ?? "";
    if (query.trim() === urlQuery) return;
    const timeout = setTimeout(() => updateParams({ q: query.trim() }), 350);
    return () => clearTimeout(timeout);
    // updateParams intentionally reflects the latest URL snapshot.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  useEffect(() => {
    if (!token) return;
    let active = true;
    api.applications
      .list(token)
      .then((applications) => {
        if (!active) return;
        setTracked(
          new Set(
            applications
              .map((application) => application.job_id)
              .filter((jobId): jobId is string => Boolean(jobId)),
          ),
        );
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [token]);

  useEffect(() => {
    if (!token) return;
    let active = true;
    setLoading(true);
    setError("");
    api.jobs
      .list(token, {
        page,
        limit,
        q: searchParams.get("q")?.trim() || undefined,
        min_score: scoreFromFilter(scoreFilter),
        source: source || undefined,
        sort,
      })
      .then((response) => {
        if (!active) return;
        setJobs(response.jobs);
        setTotal(response.total);
        if (response.source_counts) {
          setSourceCounts((current) => ({ ...current, ...response.source_counts }));
        }
      })
      .catch(() => active && setError("We couldn’t load these matches. Check your connection and try again."))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [page, scoreFilter, searchParams, sort, source, token]);

  const sourceOptions = useMemo(() => Object.entries(sourceCounts).sort(([a], [b]) => a.localeCompare(b)), [sourceCounts]);

  async function trackJob(job: Job) {
    if (trackingId) return;
    setTrackingId(job.id);
    setError("");
    try {
      await api.applications.create(token, {
        job_id: job.id,
        company: job.company,
        title: job.title,
        status: "interested",
      });
      setTracked((current) => new Set(current).add(job.id));
    } catch {
      setError("We couldn’t add that role to your tracker.");
    } finally {
      setTrackingId(null);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / limit));

  return (
    <AppShell>
      <section className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-primary/10 bg-primary/7 px-3 py-1.5 text-xs font-medium text-primary">
            <Sparkles className="size-3.5" />
            Ranked for you
          </div>
          <h1 className="page-title">Your matches</h1>
          <p className="page-copy">Search every ranked role, save the promising ones, skip the noise.</p>
        </div>
        <p className="text-sm font-medium text-muted-foreground">
          <span className="text-foreground tabular-nums">{total}</span> ranked roles
        </p>
      </section>

      <section className="surface-panel mt-7 p-3 sm:p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <label className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <span className="sr-only">Search all matches</span>
            <Input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search every role, company, or location"
              className="h-10 rounded-xl border-transparent bg-muted/70 pl-9 shadow-none focus-visible:bg-white"
            />
          </label>

          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1 rounded-xl bg-muted/70 p-1" aria-label="Match quality filter">
              {([
                ["all", "All"],
                ["excellent", "80%+"],
                ["strong", "65%+"],
              ] as const).map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => updateParams({ min_score: scoreFromFilter(value) })}
                  aria-pressed={scoreFilter === value}
                  className={scoreFilter === value
                    ? "rounded-lg bg-white px-3 py-1.5 text-xs font-medium text-foreground shadow-sm"
                    : "rounded-lg px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"}
                >
                  {label}
                </button>
              ))}
            </div>
            {sourceOptions.length > 1 && (
              <label className="flex items-center gap-2 rounded-xl border border-border/80 bg-white px-3 py-2 text-xs font-medium text-muted-foreground">
                <span className="sr-only">Source</span>
                <select
                  value={source}
                  onChange={(event) => updateParams({ source: event.target.value })}
                  className="max-w-32 bg-transparent text-foreground outline-none"
                >
                  <option value="">All sources</option>
                  {sourceOptions.map(([name, count]) => (
                    <option key={name} value={name}>{name} ({count})</option>
                  ))}
                </select>
              </label>
            )}
            <label className="flex items-center gap-2 rounded-xl border border-border/80 bg-white px-3 py-2 text-xs font-medium text-muted-foreground">
              <SlidersHorizontal className="size-3.5" />
              <span className="sr-only sm:not-sr-only">Sort</span>
              <select
                value={sort}
                onChange={(event) => updateParams({ sort: event.target.value === "match" ? undefined : event.target.value })}
                className="bg-transparent text-foreground outline-none"
              >
                <option value="match">Best match</option>
                <option value="newest">Newest</option>
                <option value="company">Company</option>
              </select>
            </label>
          </div>
        </div>
      </section>

      {error && (
        <div role="alert" className="mt-5 rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <section className="mt-5 space-y-3" aria-live="polite" aria-busy={loading}>
        {loading && Array.from({ length: 5 }).map((_, index) => (
          <div key={index} className="h-48 animate-pulse rounded-2xl border border-border/70 bg-white/60" />
        ))}
        {!loading && jobs.map((job) => (
          <JobCard
            key={job.id}
            job={job}
            tracked={tracked.has(job.id)}
            tracking={trackingId === job.id}
            onTrack={trackJob}
          />
        ))}
        {!loading && jobs.length === 0 && (
          <div className="surface-panel px-6 py-14 text-center">
            <span className="mx-auto grid size-12 place-items-center rounded-2xl bg-secondary text-primary">
              <Search className="size-5" />
            </span>
            <h2 className="mt-4 font-semibold">No matches in this view</h2>
            <p className="mt-1 text-sm text-muted-foreground">Try a broader search or reset the match filters.</p>
            <Button
              variant="outline"
              className="mt-5 rounded-xl"
              onClick={() => {
                setQuery("");
                router.replace(pathname, { scroll: false });
              }}
            >
              Clear filters
            </Button>
          </div>
        )}
      </section>

      <footer className="mt-7 flex items-center justify-between border-t border-border/70 pt-5">
        <p className="text-sm text-muted-foreground">
          Page <span className="font-medium text-foreground">{page}</span> of {totalPages}
        </p>
        <div className="flex gap-2">
          <Button
            variant="outline"
            className="rounded-xl"
            onClick={() => updateParams({ page: Math.max(1, page - 1) }, false)}
            disabled={page === 1 || loading}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            className="rounded-xl"
            onClick={() => updateParams({ page: page + 1 }, false)}
            disabled={page >= totalPages || loading}
          >
            Next
          </Button>
        </div>
      </footer>
    </AppShell>
  );
}

export default function JobsPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-background" />}>
      <JobsPageContent />
    </Suspense>
  );
}
