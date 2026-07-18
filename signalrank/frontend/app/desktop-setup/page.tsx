"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getSession, useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  FileText,
  KeyRound,
  LoaderCircle,
  ShieldCheck,
  Sparkles,
  UploadCloud,
} from "lucide-react";
import { Brand } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { isDesktopMode } from "@/lib/desktop";
import { cn } from "@/lib/utils";
import type { DesktopStatus } from "@/types";

const MAX_RESUME_SIZE = 10 * 1024 * 1024;

export default function DesktopSetupPage() {
  const router = useRouter();
  const { data: currentSession } = useSession();
  const sessionToken =
    (currentSession as { accessToken?: string } | null)?.accessToken ?? "";
  const [token, setToken] = useState(sessionToken);
  const [status, setStatus] = useState<DesktopStatus | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [resume, setResume] = useState<File | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingKey, setSavingKey] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const ensureSession = useCallback(async () => {
    if (token) return token;
    const response = await fetch("/api/desktop-session", {
      method: "POST",
      cache: "no-store",
      signal: AbortSignal.timeout(30_000),
    });
    if (!response.ok) {
      throw new Error("The protected local session could not be started.");
    }
    const nextSession = await getSession();
    const nextToken =
      (nextSession as { accessToken?: string } | null)?.accessToken ?? "";
    if (!nextToken) {
      throw new Error("The local backend returned an invalid session.");
    }
    setToken(nextToken);
    return nextToken;
  }, [token]);

  const refreshStatus = useCallback(async (activeToken?: string) => {
    const nextStatus = await api.desktop.status(activeToken);
    setStatus(nextStatus);
    return nextStatus;
  }, []);

  useEffect(() => {
    if (!isDesktopMode()) {
      router.replace("/");
      return;
    }
    let active = true;
    async function boot() {
      try {
        const activeToken = await ensureSession();
        if (active) {
          const nextStatus = await refreshStatus(activeToken);
          if (nextStatus.onboarding_complete) {
            router.replace("/dashboard");
          }
        }
      } catch (bootError) {
        if (active) {
          setError(
            bootError instanceof Error
              ? bootError.message
              : "The local backend is not ready.",
          );
        }
      } finally {
        if (active) setLoading(false);
      }
    }
    void boot();
    return () => {
      active = false;
    };
  }, [ensureSession, refreshStatus, router]);

  const activeStep = useMemo(() => {
    if (!status?.provider_configured) return 0;
    if (!status.resume_uploaded || !status.onboarding_complete) return 1;
    return 2;
  }, [status]);

  async function saveProvider(event: React.FormEvent) {
    event.preventDefault();
    if (!apiKey.trim()) return;
    setSavingKey(true);
    setError("");
    setNotice("");
    try {
      const activeToken = await ensureSession();
      const response = await api.desktop.saveProviderKey(apiKey.trim(), activeToken);
      setApiKey("");
      await refreshStatus(activeToken);
      setNotice(
        response.persistence === "credential_store"
          ? "OpenRouter key validated and saved securely."
          : "OpenRouter key validated for this session. The operating system credential store was unavailable, so you will need to enter it again after restarting.",
      );
    } catch (saveError) {
      setError(
        saveError instanceof Error
          ? saveError.message
          : "OpenRouter could not validate that key.",
      );
    } finally {
      setSavingKey(false);
    }
  }

  async function uploadResume(event: React.FormEvent) {
    event.preventDefault();
    if (!resume) return;
    if (resume.size > MAX_RESUME_SIZE) {
      setError("That file is larger than 10 MB. Choose a smaller resume.");
      return;
    }
    setUploading(true);
    setError("");
    try {
      const activeToken = await ensureSession();
      await api.onboarding.uploadResume(activeToken, resume);
      await refreshStatus(activeToken);
      router.push("/onboarding");
    } catch (uploadError) {
      setError(
        uploadError instanceof Error
          ? uploadError.message
          : "The resume could not be processed.",
      );
    } finally {
      setUploading(false);
    }
  }

  return (
    <main className="min-h-screen px-4 py-6 sm:px-6 lg:px-10">
      <div className="mx-auto w-full max-w-5xl">
        <header className="flex items-center justify-between">
          <Brand />
          <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-800">
            Local desktop
          </span>
        </header>

        <section className="mt-12 max-w-2xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-primary/10 bg-primary/7 px-3 py-1.5 text-xs font-medium text-primary">
            <Sparkles className="size-3.5" />
            Private workspace setup
          </div>
          <h1 className="mt-4 text-3xl font-semibold tracking-[-0.045em] sm:text-4xl">
            Rank jobs on this computer.
          </h1>
          <p className="mt-3 text-sm leading-6 text-muted-foreground sm:text-base">
            SignalRank stores your profile, jobs, matches, and tracker in its local
            database. Scraping and OpenRouter requests are the only network work in
            this setup.
          </p>
        </section>

        <div className="mt-8 grid gap-3 sm:grid-cols-3">
          {["OpenRouter", "Resume and profile", "First scan"].map(
            (label, index) => (
              <div
                key={label}
                className={cn(
                  "rounded-2xl border px-4 py-3 text-sm font-medium",
                  activeStep === index
                    ? "border-primary/25 bg-primary/7 text-primary"
                    : activeStep > index
                      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                      : "border-border bg-white/60 text-muted-foreground",
                )}
              >
                <span className="mr-2 inline-grid size-5 place-items-center rounded-full bg-white/80 text-[11px] shadow-sm">
                  {activeStep > index ? <Check className="size-3" /> : index + 1}
                </span>
                {label}
              </div>
            ),
          )}
        </div>

        <section className="surface-panel mt-5 p-5 sm:p-7">
          {loading ? (
            <div className="grid min-h-72 place-items-center text-center">
              <div>
                <LoaderCircle className="mx-auto size-6 animate-spin text-primary" />
                <p className="mt-3 text-sm text-muted-foreground">
                  Starting the protected local session…
                </p>
              </div>
            </div>
          ) : activeStep === 0 ? (
            <form onSubmit={saveProvider} className="mx-auto max-w-xl">
              <span className="grid size-11 place-items-center rounded-2xl bg-secondary text-primary">
                <KeyRound className="size-5" />
              </span>
              <h2 className="mt-5 text-xl font-semibold tracking-[-0.03em]">
                Connect your OpenRouter key
              </h2>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                The local backend validates the key before saving it to your operating
                system credential store. SignalRank never stores it in the local database.
              </p>
              <div className="mt-6 space-y-2">
                <Label htmlFor="openrouter-key">OpenRouter API key</Label>
                <Input
                  id="openrouter-key"
                  type="password"
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  autoComplete="off"
                  placeholder="sk-or-v1-…"
                  className="h-11 rounded-xl bg-white"
                  required
                />
              </div>
              <div className="mt-4 flex gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
                <ShieldCheck className="mt-0.5 size-4 shrink-0" />
                <p>
                  Resume text used for AI parsing is sent to OpenRouter. Deterministic
                  parsing and ranking remain available if OpenRouter is unavailable.
                </p>
              </div>
              <Button
                type="submit"
                size="lg"
                className="mt-6 h-11 w-full rounded-xl"
                disabled={savingKey || !apiKey.trim()}
              >
                {savingKey && (
                  <LoaderCircle className="animate-spin" data-icon="inline-start" />
                )}
                {savingKey ? "Validating key…" : "Validate and save"}
                {!savingKey && <ArrowRight data-icon="inline-end" />}
              </Button>
            </form>
          ) : activeStep === 1 ? (
            <form onSubmit={uploadResume} className="mx-auto max-w-xl">
              <span className="grid size-11 place-items-center rounded-2xl bg-secondary text-primary">
                <FileText className="size-5" />
              </span>
              <h2 className="mt-5 text-xl font-semibold tracking-[-0.03em]">
                {status?.resume_uploaded
                  ? "Finish your local profile"
                  : "Add your resume"}
              </h2>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                {status?.resume_uploaded
                  ? "Your resume is already stored locally. Review the extracted signals and search preferences before the first scan."
                  : "Upload a PDF, DOCX, or TXT resume. It is stored in your local SignalRank data directory."}
              </p>

              {!status?.resume_uploaded && (
                <label className="mt-6 flex min-h-48 cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-muted/35 p-6 text-center transition-colors hover:border-primary/30">
                  <Input
                    type="file"
                    accept=".pdf,.docx,.txt"
                    onChange={(event) => {
                      const file = event.target.files?.[0] ?? null;
                      setResume(file);
                      setError(
                        file && file.size > MAX_RESUME_SIZE
                          ? "That file is larger than 10 MB. Choose a smaller resume."
                          : "",
                      );
                    }}
                    className="sr-only"
                  />
                  <span className="grid size-11 place-items-center rounded-2xl bg-white text-primary shadow-sm ring-1 ring-border/70">
                    <UploadCloud className="size-5" />
                  </span>
                  <span className="mt-3 text-sm font-semibold">
                    {resume?.name ?? "Choose your resume"}
                  </span>
                  <span className="mt-1 text-xs text-muted-foreground">
                    {resume ? `${Math.max(1, Math.round(resume.size / 1024))} KB` : "Up to 10 MB"}
                  </span>
                </label>
              )}

              {status?.resume_uploaded ? (
                <Button
                  type="button"
                  size="lg"
                  className="mt-6 h-11 w-full rounded-xl"
                  onClick={() => router.push("/onboarding")}
                >
                  Review profile
                  <ArrowRight data-icon="inline-end" />
                </Button>
              ) : (
                <Button
                  type="submit"
                  size="lg"
                  className="mt-6 h-11 w-full rounded-xl"
                  disabled={uploading || !resume || resume.size > MAX_RESUME_SIZE}
                >
                  {uploading && (
                    <LoaderCircle className="animate-spin" data-icon="inline-start" />
                  )}
                  {uploading ? "Building local profile…" : "Upload and review"}
                  {!uploading && <ArrowRight data-icon="inline-end" />}
                </Button>
              )}
            </form>
          ) : (
            <div className="mx-auto max-w-xl text-center">
              <span className="mx-auto grid size-12 place-items-center rounded-2xl bg-emerald-50 text-emerald-700">
                <Check className="size-5" />
              </span>
              <h2 className="mt-5 text-xl font-semibold tracking-[-0.03em]">
                Ready to scrape and rank locally
              </h2>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                SignalRank will scrape supported public job sources, store the results
                locally, and rank them against your profile.
              </p>
              <div className="mt-6 grid grid-cols-3 gap-2 text-xs font-medium text-muted-foreground">
                {[
                  ["1", "Scrape"],
                  ["2", "Normalize"],
                  ["3", "Rank"],
                ].map(([number, label]) => (
                  <div key={number} className="rounded-xl border border-border bg-white p-3">
                    <span className="text-primary">{number}</span> · {label}
                  </div>
                ))}
              </div>
              <Button
                size="lg"
                className="mt-6 h-11 w-full rounded-xl"
                onClick={() => router.replace("/dashboard")}
              >
                Open dashboard
                <ArrowRight data-icon="inline-end" />
              </Button>
            </div>
          )}

          {error && (
            <div
              role="alert"
              className="mx-auto mt-5 flex max-w-xl gap-3 rounded-xl border border-destructive/20 bg-destructive/5 p-4 text-sm text-destructive"
            >
              <AlertTriangle className="mt-0.5 size-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}
          {notice && <p className="mx-auto mt-4 max-w-xl text-sm text-amber-800">{notice}</p>}
        </section>
      </div>
    </main>
  );
}
