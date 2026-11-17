"use client";

import { useEffect, useRef, useState } from "react";
import { useSession } from "next-auth/react";
import Link from "next/link";
import { Archive, Check, Clock3, ExternalLink, Inbox, Loader2, RotateCcw, Save } from "lucide-react";

import { useToast } from "@/components/toast";
import { api } from "@/lib/api";
import type { InboxBucket, InboxJob, InboxSummary, ReviewDecision } from "@/types";

const TABS: { bucket: InboxBucket; label: string }[] = [
  { bucket: "since_visit", label: "New since last visit" },
  { bucket: "new", label: "Unreviewed" },
  { bucket: "due", label: "Resurfaced" },
  { bucket: "reviewed", label: "Undecided" },
  { bucket: "snoozed", label: "Snoozed" },
  { bucket: "dismissed", label: "Dismissed" },
  { bucket: "saved", label: "Saved" },
];

function localDate(date = new Date()): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function daysFromNow(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() + days);
  return localDate(date);
}

export default function InboxPage() {
  const { data: session, status } = useSession();
  const token = (session as { accessToken?: string })?.accessToken ?? "";
  const { toast } = useToast();
  const [bucket, setBucket] = useState<InboxBucket>("since_visit");
  const [visitReady, setVisitReady] = useState(false);
  const visitId = useRef<string | null>(null);
  const [page, setPage] = useState(1);
  const [minScore, setMinScore] = useState(65);
  const [summary, setSummary] = useState<InboxSummary | null>(null);
  const [jobs, setJobs] = useState<InboxJob[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [customDates, setCustomDates] = useState<Record<string, string>>({});
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    if (!token) return;
    let current = true;
    // The visit ID stays stable even if React replays this effect in dev mode.
    if (!visitId.current) visitId.current = crypto.randomUUID();
    api.inbox.visit(token, visitId.current)
      .then(() => { if (current) setVisitReady(true); })
      .catch((error: unknown) => {
        if (current) toast(error instanceof Error ? error.message : "Unable to initialize visit", "error");
      });
    return () => { current = false; };
  }, [token, toast]);

  useEffect(() => {
    if (!token || !visitReady) return;
    let current = true;
    const today = localDate();
    Promise.all([
      api.inbox.summary(token, minScore, today),
      api.inbox.list(token, bucket, page, minScore, today),
    ])
      .then(([nextSummary, response]) => {
        if (!current) return;
        setSummary(nextSummary);
        setJobs(response.jobs);
        setTotal(response.total);
      })
      .catch((error: unknown) => {
        if (current) toast(error instanceof Error ? error.message : "Unable to load review inbox", "error");
      })
      .finally(() => {
        if (current) setLoading(false);
      });
    return () => { current = false; };
  }, [token, visitReady, minScore, bucket, page, refreshKey, toast]);

  function refresh() {
    setPage(1);
    setRefreshKey((current) => current + 1);
  }

  async function decide(job: InboxJob, state: ReviewDecision, until?: string) {
    if (!token || busyId) return;
    setBusyId(job.id);
    try {
      await api.inbox.update(token, job.id, state, until);
      toast(
        state === "dismissed" ? "Dismissed and hidden from Matches"
          : state === "snoozed" ? `Resurfaces on ${until}`
          : state === "unreviewed" ? "Returned to your review queue"
          : "Marked as reviewed",
        "success",
      );
      refresh();
    } catch (error) {
      toast(error instanceof Error ? error.message : "Review could not be saved", "error");
    } finally {
      setBusyId(null);
    }
  }

  async function save(job: InboxJob) {
    if (!token || busyId) return;
    setBusyId(job.id);
    try {
      await api.applications.create(token, {
        job_id: job.id,
        company: job.company ?? "",
        title: job.title ?? "",
        status: "interested",
        system_score: job.score,
      });
      await api.inbox.update(token, job.id, "reviewed");
      toast("Saved to tracker", "success");
      refresh();
    } catch (error) {
      toast(error instanceof Error ? error.message : "Unable to save role", "error");
      refresh();
    } finally {
      setBusyId(null);
    }
  }

  async function markPageReviewed() {
    if (!token || busyId || !jobs.length) return;
    setBusyId("batch");
    try {
      const result = await api.inbox.markPageReviewed(token, jobs.map((job) => job.id));
      toast(`Reviewed ${result.reviewed} jobs`, "success");
      refresh();
    } catch (error) {
      toast(error instanceof Error ? error.message : "Batch review failed", "error");
    } finally {
      setBusyId(null);
    }
  }

  if (status === "loading") {
    return <div className="pt-24 text-center text-sm text-muted-foreground">Loading session...</div>;
  }

  return (
    <main className="pt-14 min-h-screen page-content">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8 space-y-6">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="section-label mb-1">daily workflow</div>
            <h1 className="text-2xl font-bold text-foreground tracking-tight">Review Inbox</h1>
            <p className="text-xs text-muted-foreground mt-2">
              New since last visit is separate from your unreviewed backlog. Decisions survive refreshes.
            </p>
          </div>
          <div className="flex gap-2 items-center">
            <label className="text-xs text-muted-foreground" htmlFor="inbox-min-score">Match floor</label>
            <select
              id="inbox-min-score"
              value={minScore}
              onChange={(event) => { setMinScore(Number(event.target.value)); setPage(1); }}
              className="bg-input border border-border text-foreground text-xs p-2"
            >
              <option value={65}>65+ points</option>
              <option value={0}>All scores</option>
            </select>
            <Link href="/tracker" className="border border-border px-3 py-2 text-xs text-foreground hover:text-primary hover:border-primary/40">
              Tracker
            </Link>
          </div>
        </header>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {[
            { label: "New since visit", count: summary?.since_visit, href: "since_visit" as InboxBucket },
            { label: "Unreviewed backlog", count: summary?.new, href: "new" as InboxBucket },
            { label: "Follow-ups due", count: summary?.followups_due, href: null },
            { label: "Interviews / 7d", count: summary?.upcoming_interviews, href: null },
          ].map((stat) => (
            stat.href ? (
              <button key={stat.label} onClick={() => { setBucket(stat.href!); setPage(1); }}
                className="bg-card border border-border px-4 py-3 text-left hover:border-primary/50">
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{stat.label}</div>
                <div className="text-2xl font-bold tabular-nums text-primary mt-1">{stat.count ?? "—"}</div>
              </button>
            ) : (
              <Link key={stat.label} href="/tracker" className="bg-card border border-border px-4 py-3 hover:border-primary/50">
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{stat.label}</div>
                <div className="text-2xl font-bold tabular-nums text-foreground mt-1">{stat.count ?? "—"}</div>
              </Link>
            )
          ))}
        </div>

        <div className="flex flex-wrap gap-1 border-b border-border pb-2" role="tablist" aria-label="Review state">
          {TABS.map((tab) => (
            <button
              key={tab.bucket}
              type="button"
              role="tab"
              aria-selected={bucket === tab.bucket}
              onClick={() => { setBucket(tab.bucket); setPage(1); }}
              className={`px-3 py-2 text-xs border transition-colors ${bucket === tab.bucket
                ? "border-primary/50 bg-primary/10 text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"}`}
            >
              {tab.label}
              <span className="ml-1.5 tabular-nums opacity-70">{summary?.[tab.bucket] ?? 0}</span>
            </button>
          ))}
        </div>

        <div className="flex items-center justify-between gap-3">
          <div className="text-xs text-muted-foreground">{loading ? "Loading..." : `${total} jobs in this queue`}</div>
          {(bucket === "new" || bucket === "since_visit") && jobs.length > 0 && (
            <button onClick={markPageReviewed} disabled={!!busyId}
              className="inline-flex items-center gap-1.5 px-3 py-2 text-xs border border-primary/40 text-primary hover:bg-primary/10 disabled:opacity-40">
              <Check size={13} /> Mark this page reviewed
            </button>
          )}
        </div>

        {(!visitReady || loading) ? (
          <div className="flex items-center gap-2 border border-border bg-card p-8 text-muted-foreground text-xs">
            <Loader2 size={16} className="animate-spin" /> Fetching your review queue...
          </div>
        ) : jobs.length === 0 ? (
          <div className="border border-dashed border-border bg-card px-6 py-14 text-center space-y-3">
            <Inbox size={26} className="mx-auto text-primary" />
            <h2 className="font-semibold text-foreground">
              {bucket === "new" && summary?.review_complete ? "Backlog is clear" : bucket === "since_visit" ? "No new matches since your previous visit" : "No jobs in this queue"}
            </h2>
            <p className="text-xs text-muted-foreground">
              {bucket === "since_visit" ? "All older unreviewed roles remain available in the Unreviewed tab." : bucket === "new" ? "New matches will appear here after the next ranking run." : "You can return to your unreviewed backlog or revisit past decisions."}
            </p>
            <Link href="/dashboard" className="inline-block text-xs text-primary underline underline-offset-4">
              Open command center
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {jobs.map((job) => (
              <article key={job.id} className="border border-border bg-card p-4 sm:p-5 space-y-3">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <a href={job.job_url} target="_blank" rel="noopener noreferrer"
                      className="text-base font-semibold text-foreground hover:text-primary break-words inline-flex items-center gap-1.5">
                      {job.title || "Untitled job"} <ExternalLink size={12} className="shrink-0" />
                    </a>
                    <div className="text-xs text-secondary-foreground mt-1">
                      {job.company || "Unknown company"} {job.location ? `· ${job.location}` : ""}
                    </div>
                    {job.snoozed_until && (
                      <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground mt-2">
                        <Clock3 size={11} /> Snoozed until {job.snoozed_until}
                      </span>
                    )}
                  </div>
                  <div className="shrink-0 text-primary text-xl font-bold tabular-nums">{Math.round(job.score * 100)}%</div>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {job.is_saved ? (
                    <Link href="/tracker" className="inline-flex gap-1.5 items-center border border-primary/30 px-3 py-1.5 text-xs text-primary">
                      <Save size={12} /> In tracker
                    </Link>
                  ) : (
                    <button disabled={!!busyId} onClick={() => save(job)}
                      className="inline-flex items-center gap-1.5 bg-primary text-primary-foreground px-3 py-1.5 text-xs font-semibold disabled:opacity-40">
                      <Save size={12} /> Save
                    </button>
                  )}
                  {bucket !== "saved" && (
                    <>
                      {bucket !== "reviewed" && (
                        <button disabled={!!busyId} onClick={() => decide(job, "reviewed")}
                          className="inline-flex gap-1 items-center border border-border px-3 py-1.5 text-xs text-foreground hover:border-primary/40 disabled:opacity-40">
                          <Check size={12} /> Reviewed
                        </button>
                      )}
                      {bucket !== "dismissed" && (
                        <button disabled={!!busyId} onClick={() => decide(job, "dismissed")}
                          className="inline-flex gap-1 items-center border border-border px-3 py-1.5 text-xs text-muted-foreground hover:text-destructive disabled:opacity-40">
                          <Archive size={12} /> Not a fit
                        </button>
                      )}
                      <button disabled={!!busyId} onClick={() => decide(job, "unreviewed")}
                        className="inline-flex gap-1 items-center border border-border px-3 py-1.5 text-xs text-muted-foreground hover:text-primary disabled:opacity-40">
                        <RotateCcw size={12} /> Restore
                      </button>
                      {bucket !== "snoozed" && bucket !== "dismissed" && (
                        <div className="flex items-center gap-1.5">
                          <input type="date" aria-label={`Snooze until for ${job.title || "job"}`}
                            min={daysFromNow(1)}
                            value={customDates[job.id] ?? ""}
                            onChange={(event) => setCustomDates((dates) => ({ ...dates, [job.id]: event.target.value }))}
                            className="bg-input border border-border px-1.5 py-1 text-xs text-foreground" />
                          <button disabled={!!busyId}
                            onClick={() => decide(job, "snoozed", customDates[job.id] || daysFromNow(7))}
                            className="inline-flex gap-1 items-center border border-border px-3 py-1.5 text-xs text-muted-foreground hover:text-primary disabled:opacity-40">
                            <Clock3 size={12} /> {customDates[job.id] ? "Snooze" : "7 days"}
                          </button>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </article>
            ))}
          </div>
        )}

        {total > 25 && (
          <div className="flex justify-between items-center border-t border-border pt-4 text-xs">
            <button disabled={page === 1 || loading} onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="border border-border px-3 py-2 text-foreground disabled:opacity-30">Previous</button>
            <span className="text-muted-foreground tabular-nums">Page {page} / {Math.ceil(total / 25)}</span>
            <button disabled={loading || page * 25 >= total} onClick={() => setPage((p) => p + 1)}
              className="border border-border px-3 py-2 text-foreground disabled:opacity-30">Next</button>
          </div>
        )}
      </div>
    </main>
  );
}
