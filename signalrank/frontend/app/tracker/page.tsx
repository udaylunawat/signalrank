"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { api } from "@/lib/api";
import type { Application, ApplicationStatus } from "@/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const STATUSES: ApplicationStatus[] = [
  "interested",
  "applied",
  "phone_screen",
  "interview",
  "offer",
  "rejected",
  "withdrawn",
];

const STATUS_COLORS: Record<ApplicationStatus, "default" | "secondary" | "destructive" | "outline"> = {
  interested: "secondary",
  applied: "default",
  phone_screen: "default",
  interview: "default",
  offer: "default",
  rejected: "destructive",
  withdrawn: "outline",
};

export default function TrackerPage() {
  const { data: session } = useSession();
  const token = (session as { accessToken?: string })?.accessToken ?? "";

  const [applications, setApplications] = useState<Application[]>([]);

  useEffect(() => {
    if (!token) return;
    api.applications.list(token).then(setApplications);
  }, [token]);

  async function updateStatus(id: string, status: ApplicationStatus) {
    const updated = await api.applications.update(token, id, { status });
    setApplications((apps) => apps.map((a) => (a.id === id ? { ...a, ...updated } : a)));
  }

  async function deleteApp(id: string) {
    await api.applications.delete(token, id);
    setApplications((apps) => apps.filter((a) => a.id !== id));
  }

  const byStatus = STATUSES.reduce(
    (acc, s) => ({ ...acc, [s]: applications.filter((a) => a.status === s) }),
    {} as Record<ApplicationStatus, Application[]>
  );

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Job Tracker</h1>
        <a href="/dashboard" className="text-sm underline">Dashboard</a>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {STATUSES.filter((s) => byStatus[s].length > 0 || ["interested", "applied", "interview"].includes(s)).map((status) => (
          <div key={status} className="space-y-2">
            <div className="flex items-center gap-2">
              <Badge variant={STATUS_COLORS[status]}>{status.replace("_", " ")}</Badge>
              <span className="text-sm text-muted-foreground">{byStatus[status].length}</span>
            </div>
            {byStatus[status].map((app) => (
              <Card key={app.id} className="text-sm">
                <CardHeader className="pb-1 pt-3 px-3">
                  <CardTitle className="text-sm">{app.title}</CardTitle>
                  <p className="text-xs text-muted-foreground">{app.company}</p>
                </CardHeader>
                <CardContent className="pb-3 px-3 space-y-2">
                  <select
                    value={app.status}
                    onChange={(e) => updateStatus(app.id, e.target.value as ApplicationStatus)}
                    className="w-full text-xs border rounded px-1 py-0.5"
                  >
                    {STATUSES.map((s) => (
                      <option key={s} value={s}>
                        {s.replace("_", " ")}
                      </option>
                    ))}
                  </select>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-xs h-6 px-2 text-destructive"
                    onClick={() => deleteApp(app.id)}
                  >
                    Remove
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
