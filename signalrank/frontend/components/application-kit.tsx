"use client";

import { useEffect, useState } from "react";
import {
  Check,
  Copy,
  ExternalLink,
  FileDown,
  Loader2,
  Mail,
  Sparkles,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { openExternal, saveDownload } from "@/lib/desktop";

export interface ApplicationKitTarget {
  jobId: string;
  title: string;
  company: string;
}

function messageFrom(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}

function gmailComposeUrl(subject: string, body: string) {
  const params = new URLSearchParams({ view: "cm", su: subject, body });
  return `https://mail.google.com/mail/?${params.toString()}`;
}

export default function ApplicationKit({
  target,
  token,
  iconOnly = false,
}: {
  target: ApplicationKitTarget;
  token: string;
  iconOnly?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [recipientName, setRecipientName] = useState("");
  const [template, setTemplate] = useState("classic");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [generatingResume, setGeneratingResume] = useState(false);
  const [generatingEmail, setGeneratingEmail] = useState(false);
  const [copied, setCopied] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open]);

  async function generateResume() {
    if (!token || generatingResume) return;
    setGeneratingResume(true);
    setError("");
    setNotice("");
    try {
      await api.resume.tailor(token, { job_id: target.jobId, template });
      const download = await api.resume.download(token, target.jobId);
      const saved = await saveDownload(download.blob, download.filename);
      setNotice(saved ? "Tailored resume saved." : "Save cancelled.");
    } catch (generationError) {
      setError(messageFrom(generationError));
    } finally {
      setGeneratingResume(false);
    }
  }

  async function generateEmail() {
    if (!token || generatingEmail) return;
    setGeneratingEmail(true);
    setError("");
    setNotice("");
    try {
      const email = await api.resume.email(token, {
        job_id: target.jobId,
        recipient_name: recipientName.trim() || "Hiring team",
      });
      setSubject(email.subject);
      setBody(email.body);
      setNotice("Outreach draft ready. Review it before sending.");
    } catch (generationError) {
      setError(messageFrom(generationError));
    } finally {
      setGeneratingEmail(false);
    }
  }

  async function copyEmail() {
    try {
      await navigator.clipboard.writeText(`Subject: ${subject}\n\n${body}`);
      setCopied(true);
      setError("");
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setError("Clipboard access was unavailable. Select and copy the draft manually.");
    }
  }

  async function openGmail() {
    try {
      await openExternal(gmailComposeUrl(subject, body));
      setError("");
    } catch (openError) {
      setError(messageFrom(openError));
    }
  }

  return (
    <>
      <Button
        type="button"
        size={iconOnly ? "icon-sm" : "sm"}
        variant="outline"
        className="rounded-xl"
        disabled={!token}
        aria-label={iconOnly ? `Prepare application for ${target.title}` : undefined}
        onClick={() => setOpen(true)}
      >
        <Sparkles />
        {!iconOnly && "Application kit"}
      </Button>

      {open && (
        <div
          className="fixed inset-0 z-[100] grid place-items-center bg-slate-950/35 p-4 backdrop-blur-sm"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setOpen(false);
          }}
        >
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby={`application-kit-${target.jobId}`}
            className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-border bg-background p-5 shadow-2xl sm:p-6"
          >
            <div className="flex items-start gap-4">
              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary">
                  Application kit
                </p>
                <h2
                  id={`application-kit-${target.jobId}`}
                  className="mt-1 truncate text-lg font-semibold tracking-[-0.025em]"
                >
                  {target.title}
                </h2>
                <p className="text-sm text-muted-foreground">{target.company}</p>
              </div>
              <Button
                type="button"
                size="icon-sm"
                variant="ghost"
                aria-label="Close application kit"
                onClick={() => setOpen(false)}
              >
                <X />
              </Button>
            </div>

            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              <div className="rounded-xl border border-border/80 bg-muted/25 p-4">
                <div className="flex items-center gap-2">
                  <FileDown className="size-4 text-primary" />
                  <h3 className="text-sm font-semibold">Tailored resume</h3>
                </div>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                  Rewrites your saved resume for this role without inventing experience.
                </p>
                <label className="mt-4 block text-xs font-medium text-muted-foreground">
                  Layout
                  <select
                    value={template}
                    onChange={(event) => setTemplate(event.target.value)}
                    className="mt-1 h-9 w-full rounded-lg border border-input bg-background px-2.5 text-sm outline-none focus:border-ring"
                  >
                    <option value="classic">Classic</option>
                    <option value="modern">Modern</option>
                    <option value="minimal">Minimal</option>
                  </select>
                </label>
                <Button
                  type="button"
                  className="mt-4 w-full rounded-xl"
                  disabled={generatingResume}
                  onClick={generateResume}
                >
                  {generatingResume ? <Loader2 className="animate-spin" /> : <FileDown />}
                  {generatingResume ? "Generating…" : "Generate and save PDF"}
                </Button>
              </div>

              <div className="rounded-xl border border-border/80 bg-muted/25 p-4">
                <div className="flex items-center gap-2">
                  <Mail className="size-4 text-primary" />
                  <h3 className="text-sm font-semibold">Outreach email</h3>
                </div>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                  Creates a concise draft from your resume and this job description.
                </p>
                <label className="mt-4 block text-xs font-medium text-muted-foreground">
                  Recipient name, optional
                  <Input
                    value={recipientName}
                    onChange={(event) => setRecipientName(event.target.value)}
                    placeholder="Hiring manager or recruiter"
                    className="mt-1 h-9 bg-background"
                    maxLength={100}
                  />
                </label>
                <Button
                  type="button"
                  variant="outline"
                  className="mt-4 w-full rounded-xl"
                  disabled={generatingEmail}
                  onClick={generateEmail}
                >
                  {generatingEmail ? <Loader2 className="animate-spin" /> : <Sparkles />}
                  {generatingEmail ? "Generating…" : "Generate email"}
                </Button>
              </div>
            </div>

            {error && (
              <div role="alert" className="mt-4 rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                {error}
              </div>
            )}
            {notice && !error && (
              <div role="status" className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
                {notice}
              </div>
            )}

            {(subject || body) && (
              <div className="mt-5 rounded-xl border border-border/80 p-4">
                <label className="block text-xs font-medium text-muted-foreground">
                  Subject
                  <Input
                    value={subject}
                    onChange={(event) => setSubject(event.target.value)}
                    className="mt-1 h-9"
                  />
                </label>
                <label className="mt-3 block text-xs font-medium text-muted-foreground">
                  Body
                  <textarea
                    value={body}
                    onChange={(event) => setBody(event.target.value)}
                    rows={9}
                    className="mt-1 w-full resize-y rounded-lg border border-input bg-transparent px-3 py-2 text-sm leading-6 outline-none focus:border-ring focus:ring-3 focus:ring-ring/30"
                  />
                </label>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button type="button" variant="outline" onClick={copyEmail} disabled={!subject || !body}>
                    {copied ? <Check /> : <Copy />}
                    {copied ? "Copied" : "Copy email"}
                  </Button>
                  <Button type="button" onClick={openGmail} disabled={!subject || !body}>
                    <ExternalLink />
                    Open in Gmail
                  </Button>
                </div>
              </div>
            )}
          </section>
        </div>
      )}
    </>
  );
}
