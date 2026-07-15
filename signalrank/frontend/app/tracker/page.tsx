"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSession } from "next-auth/react";
import {
  ArrowRight,
  BriefcaseBusiness,
  ExternalLink,
  MoreHorizontal,
  Trash2,
} from "lucide-react";
import AppShell from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { Application, ApplicationStatus } from "@/types";

const columns: Array<{
  status: ApplicationStatus;
  label: string;
  dot: string;
  description: string;
}> = [
  { status: "interested", label: "Saved", dot: "bg-violet-500", description: "Worth a closer look" },
  { status: "applied", label: "Applied", dot: "bg-blue-500", description: "Application sent" },
  { status: "phone_screen", label: "Screen", dot: "bg-cyan-500", description: "First conversation" },
  { status: "interview", label: "Interview", dot: "bg-amber-500", description: "Active process" },
  { status: "offer", label: "Offer", dot: "bg-emerald-500", description: "Decision time" },
];

const secondaryStatuses: ApplicationStatus[] = ["rejected", "archived"];

function displayStatus(status: ApplicationStatus) {
  return status.replace("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export default function TrackerPage() {
  const { data: session } = useSession();
  const token = (session as { accessToken?: string })?.accessToken ?? "";
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) return;
    let active = true;
    api.applications
      .list(token)
      .then((items) => active && setApplications(items))
      .catch(() => active && setError("We couldn’t load your tracker."))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [token]);

  const byStatus = useMemo(
    () =>
      applications.reduce(
        (grouped, application) => {
          grouped[application.status].push(application);
          return grouped;
        },
        {
          interested: [],
          applied: [],
          phone_screen: [],
          interview: [],
          offer: [],
          rejected: [],
          archived: [],
        } as Record<ApplicationStatus, Application[]>
      ),
    [applications]
  );

  async function updateStatus(id: string, status: ApplicationStatus) {
    const previous = applications;
    setApplications((current) =>
      current.map((application) =>
        application.id === id ? { ...application, status } : application
      )
    );
    try {
      await api.applications.update(token, id, { status });
    } catch {
      setApplications(previous);
      setError("That status change didn’t save. Please try again.");
    }
  }

  async function deleteApplication(id: string) {
    const previous = applications;
    setApplications((current) => current.filter((application) => application.id !== id));
    try {
      await api.applications.delete(token, id);
    } catch {
      setApplications(previous);
      setError("We couldn’t remove that application.");
    }
  }

  return (
    <AppShell>
      <section className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-primary">Application pipeline</p>
          <h1 className="page-title">Keep every opportunity moving.</h1>
          <p className="page-copy">A simple view of what needs attention and what comes next.</p>
        </div>
        <Button render={<Link href="/jobs" />} nativeButton={false} className="rounded-xl">
          Browse matches
          <ArrowRight data-icon="inline-end" />
        </Button>
      </section>

      {error && (
        <div className="mt-5 rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {loading ? (
        <div className="mt-8 grid gap-4 md:grid-cols-3 xl:grid-cols-5">
          {Array.from({ length: 5 }).map((_, index) => (
            <div key={index} className="h-64 animate-pulse rounded-2xl border border-border/70 bg-white/60" />
          ))}
        </div>
      ) : applications.length === 0 ? (
        <div className="surface-panel mt-8 px-6 py-16 text-center">
          <span className="mx-auto grid size-14 place-items-center rounded-2xl bg-secondary text-primary">
            <BriefcaseBusiness className="size-6" />
          </span>
          <h2 className="mt-5 text-lg font-semibold tracking-[-0.025em]">Build your shortlist as you browse</h2>
          <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted-foreground">
            Save a promising match and it will appear here, ready to move from interest to offer.
          </p>
          <Button render={<Link href="/jobs" />} nativeButton={false} className="mt-6 rounded-xl">
            Find roles to track
          </Button>
        </div>
      ) : (
        <>
          <section className="-mx-4 mt-8 overflow-x-auto px-4 pb-4 sm:-mx-6 sm:px-6 lg:-mx-10 lg:px-10">
            <div className="grid min-w-[1080px] grid-cols-5 gap-3">
              {columns.map((column) => (
                <div key={column.status} className="rounded-2xl bg-white/52 p-2 ring-1 ring-border/65">
                  <div className="px-2 py-2">
                    <div className="flex items-center gap-2">
                      <span className={`size-2 rounded-full ${column.dot}`} />
                      <h2 className="text-sm font-semibold">{column.label}</h2>
                      <span className="ml-auto text-xs font-medium text-muted-foreground tabular-nums">
                        {byStatus[column.status].length}
                      </span>
                    </div>
                    <p className="mt-1 text-[11px] text-muted-foreground">{column.description}</p>
                  </div>

                  <div className="mt-1 space-y-2">
                    {byStatus[column.status].map((application) => (
                      <article
                        key={application.id}
                        className="rounded-xl border border-border/70 bg-white p-3 shadow-[0_1px_2px_rgba(20,20,35,0.04)]"
                      >
                        <div className="flex items-start gap-2">
                          <div className="min-w-0 flex-1">
                            <h3 className="line-clamp-2 text-sm font-semibold leading-5">{application.title}</h3>
                            <p className="mt-0.5 truncate text-xs text-muted-foreground">{application.company}</p>
                            {(application.source || application.date_posted) && (
                              <p className="mt-2 text-[10px] text-muted-foreground">
                                {application.source && `via ${application.source}`}
                                {application.source && application.date_posted && " · "}
                                {application.date_posted &&
                                  new Date(application.date_posted).toLocaleDateString(undefined, {
                                    month: "short",
                                    day: "numeric",
                                  })}
                              </p>
                            )}
                          </div>
                          <MoreHorizontal className="size-4 shrink-0 text-muted-foreground/60" />
                        </div>
                        <div className="mt-3 flex items-center gap-1.5">
                          {application.job_url && (
                            <a
                              href={application.job_url}
                              target="_blank"
                              rel="noreferrer"
                              aria-label={`Open ${application.title}`}
                              className="grid size-7 shrink-0 place-items-center rounded-lg border border-border text-muted-foreground transition-colors hover:text-foreground"
                            >
                              <ExternalLink className="size-3.5" />
                            </a>
                          )}
                          <select
                            aria-label={`Status for ${application.title}`}
                            value={application.status}
                            onChange={(event) =>
                              updateStatus(application.id, event.target.value as ApplicationStatus)
                            }
                            className="min-w-0 flex-1 rounded-lg border border-border bg-muted/45 px-2 py-1.5 text-[11px] font-medium outline-none focus:border-ring"
                          >
                            {[...columns.map((item) => item.status), ...secondaryStatuses].map((status) => (
                              <option key={status} value={status}>
                                {displayStatus(status)}
                              </option>
                            ))}
                          </select>
                          <button
                            type="button"
                            aria-label={`Remove ${application.title}`}
                            onClick={() => deleteApplication(application.id)}
                            className="grid size-7 shrink-0 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-destructive/8 hover:text-destructive"
                          >
                            <Trash2 className="size-3.5" />
                          </button>
                        </div>
                      </article>
                    ))}
                    {byStatus[column.status].length === 0 && (
                      <div className="rounded-xl border border-dashed border-border px-3 py-8 text-center text-[11px] text-muted-foreground">
                        No roles here yet
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </section>

          {secondaryStatuses.some((status) => byStatus[status].length > 0) && (
            <section className="mt-4 flex flex-wrap gap-2 border-t border-border/70 pt-5">
              {secondaryStatuses.map((status) =>
                byStatus[status].map((application) => (
                  <Badge key={application.id} variant="outline" className="h-auto gap-2 py-1.5">
                    <span className="font-medium">{application.title}</span>
                    <span className="text-muted-foreground">{displayStatus(status)}</span>
                  </Badge>
                ))
              )}
            </section>
          )}
        </>
      )}
    </AppShell>
  );
}
