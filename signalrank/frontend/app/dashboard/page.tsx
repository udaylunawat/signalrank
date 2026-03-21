"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { api } from "@/lib/api";
import type { Job, Run } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

function scoreBadgeColor(score: number | null) {
  if (!score) return "secondary";
  if (score >= 0.8) return "default";
  if (score >= 0.6) return "secondary";
  return "destructive";
}

export default function DashboardPage() {
  const { data: session } = useSession();
  const token = (session as { accessToken?: string })?.accessToken ?? "";

  const [jobs, setJobs] = useState<Job[]>([]);
  const [run, setRun] = useState<Run | null>(null);
  const [triggering, setTriggering] = useState(false);

  useEffect(() => {
    if (!token) return;
    api.jobs.list(token, 1, 10).then((r) => setJobs(r.jobs));
    api.runs.latest(token).then(setRun).catch(() => null);
  }, [token]);

  async function triggerRun() {
    setTriggering(true);
    try {
      const res = await api.runs.trigger(token);
      setRun({ id: res.run_id, status: "pending", started_at: new Date().toISOString(), finished_at: null, job_count: null });
    } finally {
      setTriggering(false);
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <Button onClick={triggerRun} disabled={triggering}>
          {triggering ? "Starting..." : "Refresh jobs"}
        </Button>
      </div>

      {run && (
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Latest run:</span>
              <Badge variant={run.status === "done" ? "default" : "secondary"}>
                {run.status}
              </Badge>
              {run.job_count != null && (
                <span className="text-sm text-muted-foreground">
                  {run.job_count} jobs ranked
                </span>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      <div className="space-y-3">
        <h2 className="text-lg font-semibold">Top matches</h2>
        {jobs.length === 0 && (
          <p className="text-muted-foreground text-sm">
            No results yet. Click "Refresh jobs" to run your first ranking.
          </p>
        )}
        {jobs.map((job) => (
          <Card key={job.id}>
            <CardHeader className="pb-2">
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle className="text-base">{job.title}</CardTitle>
                  <p className="text-sm text-muted-foreground">
                    {job.company} {job.location ? `· ${job.location}` : ""}
                  </p>
                </div>
                <Badge variant={scoreBadgeColor(job.final_score)}>
                  {job.final_score != null ? (job.final_score * 100).toFixed(0) : "—"}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="flex gap-2 flex-wrap text-xs text-muted-foreground">
                {job.company_tier && <span>Tier {job.company_tier}</span>}
                {job.is_contract && <Badge variant="outline">Contract</Badge>}
                {job.site && <span>{job.site}</span>}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="flex gap-4">
        <a href="/jobs" className="text-sm underline">View all jobs</a>
        <a href="/tracker" className="text-sm underline">Job tracker</a>
      </div>
    </div>
  );
}
