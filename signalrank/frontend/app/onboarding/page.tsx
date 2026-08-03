"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  FileText,
  LoaderCircle,
  Plus,
  ShieldCheck,
  UploadCloud,
  X,
} from "lucide-react";
import { Brand } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { isDesktopMode } from "@/lib/desktop";
import type {
  OnboardingAnswer,
  OnboardingQuestion,
  Profile,
  ResumeExtraction,
  ResumeParseStatus,
} from "@/types";

const MAX_RESUME_SIZE = 10 * 1024 * 1024;

const DEFAULT_QUESTIONS: OnboardingQuestion[] = [
  {
    id: "target_roles",
    text: "Which role titles would you seriously consider?",
    type: "tags",
  },
  {
    id: "preferred_locations",
    text: "Where would you like to work?",
    type: "text",
  },
  {
    id: "company_tiers",
    text: "Should we show every company or focus on highly reputed employers?",
    type: "multiselect",
  },
  {
    id: "preferred_companies",
    text: "Any companies you especially want to see?",
    type: "text",
  },
  {
    id: "excluded_companies",
    text: "Any companies to exclude?",
    type: "text",
  },
  {
    id: "excluded_titles",
    text: "Any job titles or kinds of work to exclude?",
    type: "text",
  },
];

type Step = "upload" | "questions";

function uniqueValues(values: string[]) {
  return Array.from(
    new Map(
      values
        .map((value) => value.trim())
        .filter(Boolean)
        .map((value) => [value.toLocaleLowerCase(), value]),
    ).values(),
  );
}

function mergeQuestions(questions: OnboardingQuestion[] | undefined) {
  const incoming = new Map((questions ?? []).map((question) => [question.id, question]));
  const known = DEFAULT_QUESTIONS.map((question) => ({
    ...incoming.get(question.id),
    ...question,
  }));
  const extras = (questions ?? []).filter(
    (question) => !DEFAULT_QUESTIONS.some((knownQuestion) => knownQuestion.id === question.id),
  );
  return [...known, ...extras];
}

function answersFromProfile(profile: Profile | null): Record<string, OnboardingAnswer> {
  const config = profile?.config_overrides ?? {};
  return {
    target_roles: config.profile_intent?.roles ?? [],
    preferred_locations:
      config.location_scoring?.preferred_locations ?? config.scraping?.locations ?? [],
    company_tiers: config.company_preferences?.tiers ?? [],
    company_filter_mode: config.company_preferences?.filter_mode ?? "all",
    preferred_companies: config.company_preferences?.preferred_companies ?? [],
    excluded_companies: config.company_preferences?.excluded_companies ?? [],
    excluded_titles: config.title_blocklist ?? [],
    ...(profile?.min_salary ? { salary_expectations: String(profile.min_salary) } : {}),
  };
}

function hasExtractionSignal(extracted: ResumeExtraction | null) {
  return Boolean(
    extracted?.skills?.length ||
      extracted?.recent_titles?.length ||
      extracted?.years_of_experience ||
      extracted?.industries?.length,
  );
}

function isDegraded(status: ResumeParseStatus | undefined) {
  return Boolean(
    status && ["partial", "degraded", "llm_unavailable", "failed"].includes(status),
  );
}

export default function OnboardingPage() {
  const { data: session } = useSession();
  const router = useRouter();
  const token = (session as { accessToken?: string })?.accessToken ?? "";
  const desktopMode = isDesktopMode();

  const [step, setStep] = useState<Step>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [questions, setQuestions] = useState<OnboardingQuestion[]>(DEFAULT_QUESTIONS);
  const [answers, setAnswers] = useState<Record<string, OnboardingAnswer>>({});
  const [extracted, setExtracted] = useState<ResumeExtraction | null>(null);
  const [parseStatus, setParseStatus] = useState<ResumeParseStatus>();
  const [roleDraft, setRoleDraft] = useState("");
  const [loadingDraft, setLoadingDraft] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [finishing, setFinishing] = useState(false);
  const [draftWarning, setDraftWarning] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) return;
    let active = true;
    Promise.all([
      api.onboarding.status(token).catch(() => null),
      api.profile.get(token).catch(() => null),
    ])
      .then(([status, profileResponse]) => {
        if (!active) return;
        if (!status && !profileResponse) {
          setError("We couldn’t restore your onboarding progress.");
          return;
        }
        if (status?.onboarding_complete || profileResponse?.profile?.onboarding_complete) {
          router.replace("/dashboard");
          return;
        }
        const draft = status?.draft;
        const restoredExtraction = draft?.extracted ?? status?.extracted ?? null;
        const restoredStatus =
          draft?.parse_status ?? status?.parse_status ?? restoredExtraction?.parse_status;
        setExtracted(restoredExtraction);
        setParseStatus(restoredStatus);
        setQuestions(mergeQuestions(draft?.questions ?? status?.questions));
        setAnswers({
          ...answersFromProfile(profileResponse?.profile ?? null),
          ...(draft?.answers ?? {}),
        });
        if (status?.has_resume || profileResponse?.profile?.resume_text) {
          setStep("questions");
        }
      })
      .finally(() => active && setLoadingDraft(false));
    return () => {
      active = false;
    };
  }, [router, token]);

  const roleSuggestions = useMemo(
    () => uniqueValues(extracted?.recent_titles ?? []),
    [extracted?.recent_titles],
  );
  const selectedRoles = Array.isArray(answers.target_roles) ? answers.target_roles : [];
  const extractionUnavailable = parseStatus !== undefined && !hasExtractionSignal(extracted);
  const needsExtractionRetry = Boolean(extracted?.parse_error) || extractionUnavailable;
  const hybridExtraction = isDegraded(parseStatus) && !needsExtractionRetry;

  async function handleUpload(event: React.FormEvent) {
    event.preventDefault();
    if (!file) return;
    if (file.size > MAX_RESUME_SIZE) {
      setError("That file is larger than 10 MB. Choose a smaller resume.");
      return;
    }
    setUploading(true);
    setError("");
    try {
      const response = await api.onboarding.uploadResume(token, file);
      const responseStatus = response.parse_status ?? response.extracted.parse_status;
      setExtracted(response.extracted);
      setParseStatus(responseStatus ?? (hasExtractionSignal(response.extracted) ? "complete" : "degraded"));
      setQuestions(mergeQuestions(response.draft?.questions ?? response.questions));
      setAnswers((current) => ({
        ...current,
        ...(response.draft?.answers ?? {}),
      }));
      setStep("questions");
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message.replace(/^\d+:\s*/, "") : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function retryExtraction() {
    if (!token || retrying) return;
    setRetrying(true);
    setError("");
    try {
      const response = await api.onboarding.retryResume(token);
      const responseStatus = response.parse_status ?? response.extracted.parse_status;
      setExtracted(response.extracted);
      setParseStatus(responseStatus ?? (hasExtractionSignal(response.extracted) ? "complete" : "degraded"));
      setQuestions(mergeQuestions(response.questions));
      setAnswers((current) => ({
        ...current,
        ...(response.draft?.answers ?? {}),
      }));
    } catch (retryError) {
      setError(retryError instanceof Error ? retryError.message : "We couldn’t retry resume extraction.");
    } finally {
      setRetrying(false);
    }
  }

  async function persistAnswer(questionId: string, answer: OnboardingAnswer) {
    try {
      await api.onboarding.refine(token, questionId, answer);
      setDraftWarning("");
    } catch {
      setDraftWarning("This answer is saved in this form but could not sync yet. Finish setup to retry.");
    }
  }

  function updateAnswer(questionId: string, answer: OnboardingAnswer) {
    setAnswers((current) => ({ ...current, [questionId]: answer }));
  }

  function addRole(value = roleDraft) {
    const nextRoles = uniqueValues([...selectedRoles, ...value.split(/[,;\n]+/)]);
    if (nextRoles.length === selectedRoles.length) {
      setRoleDraft("");
      return;
    }
    updateAnswer("target_roles", nextRoles);
    setRoleDraft("");
    void persistAnswer("target_roles", nextRoles);
  }

  function removeRole(role: string) {
    const nextRoles = selectedRoles.filter((selectedRole) => selectedRole !== role);
    updateAnswer("target_roles", nextRoles);
    void persistAnswer("target_roles", nextRoles);
  }

  function selectCompanyMode(mode: "all" | "top_reputed") {
    const tiers = mode === "all" ? ["any"] : ["tier_s", "tier_a"];
    updateAnswer("company_tiers", tiers);
    updateAnswer("company_filter_mode", mode);
    void persistAnswer("company_tiers", tiers);
    void persistAnswer("company_filter_mode", mode);
  }

  async function finishOnboarding(usePreferences: boolean) {
    setFinishing(true);
    setError("");
    const pendingRoles = uniqueValues([...selectedRoles, ...roleDraft.split(/[,;\n]+/)]);
    const pendingAnswers: Record<string, OnboardingAnswer> = {
      ...answers,
      ...(pendingRoles.length ? { target_roles: pendingRoles } : {}),
    };
    try {
      if (usePreferences) {
        for (const [questionId, answer] of Object.entries(pendingAnswers)) {
          if ((typeof answer === "string" && answer.trim()) || (Array.isArray(answer) && answer.length)) {
            await api.onboarding.refine(token, questionId, answer);
          }
        }
      }
      await api.onboarding.refine(token, "onboarding_complete", "true");
      await api.runs.trigger(token);
      router.push("/dashboard");
    } catch {
      setError("Setup didn’t finish saving. Your resume is still on file—please try again.");
    } finally {
      setFinishing(false);
    }
  }

  function handleFinish(event: React.FormEvent) {
    event.preventDefault();
    void finishOnboarding(true);
  }

  const currentStep = step === "upload" ? 1 : 2;

  return (
    <main className="min-h-screen px-4 py-5 sm:px-6 lg:px-10">
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between">
        <Brand />
        <div className="flex items-center gap-3 text-xs font-medium text-muted-foreground">
          <span>Step {currentStep} of 2</span>
          <span className="h-1.5 w-20 overflow-hidden rounded-full bg-muted">
            <span
              className="block h-full rounded-full bg-primary transition-all duration-500"
              style={{ width: `${currentStep * 50}%` }}
            />
          </span>
        </div>
      </header>

      <div className="mx-auto mt-14 grid w-full max-w-6xl gap-8 lg:grid-cols-[minmax(0,0.8fr)_minmax(520px,1.2fr)] lg:items-start">
        <section className="max-w-lg pt-2 lg:sticky lg:top-16">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-primary">Make it personal</p>
          <h1 className="mt-4 text-3xl font-semibold leading-tight tracking-[-0.045em] sm:text-4xl">
            Your resume becomes the signal, not the application form.
          </h1>
          <p className="mt-4 text-sm leading-6 text-muted-foreground sm:text-base">
            We extract your experience and ask only the questions needed to tune your ranking.
          </p>
          <div className="mt-8 space-y-3 text-sm text-muted-foreground">
            <div className="flex items-center gap-3">
              <span className="grid size-8 place-items-center rounded-xl bg-emerald-50 text-emerald-700">
                <ShieldCheck className="size-4" />
              </span>
              {desktopMode
                ? "Your resume is stored in the local SignalRank database"
                : "Your resume stays private to your account"}
            </div>
            <div className="flex items-center gap-3">
              <span className="grid size-8 place-items-center rounded-xl bg-indigo-50 text-indigo-700">
                <Check className="size-4" />
              </span>
              Any role title works—there is no fixed role catalog
            </div>
          </div>
        </section>

        <section className="surface-panel p-5 sm:p-7">
          {loadingDraft ? (
            <div className="grid min-h-80 place-items-center" aria-label="Restoring onboarding progress">
              <LoaderCircle className="size-6 animate-spin text-primary" />
            </div>
          ) : step === "upload" ? (
            <form onSubmit={handleUpload}>
              <div>
                <p className="text-xs font-semibold text-primary">01 · Resume</p>
                <h2 className="mt-2 text-xl font-semibold tracking-[-0.03em]">Start with what you’ve already built.</h2>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">
                  Upload a PDF, DOCX, or TXT file. We’ll turn it into an editable profile.
                </p>
              </div>

              <label
                htmlFor="resume"
                className={cn(
                  "mt-7 flex min-h-56 cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed p-6 text-center transition-colors",
                  file
                    ? "border-primary/35 bg-primary/5"
                    : "border-border bg-muted/35 hover:border-primary/30 hover:bg-primary/4",
                )}
              >
                <Input
                  id="resume"
                  type="file"
                  accept=".pdf,.docx,.txt"
                  onChange={(event) => {
                    const nextFile = event.target.files?.[0] ?? null;
                    setFile(nextFile);
                    setError(
                      nextFile && nextFile.size > MAX_RESUME_SIZE
                        ? "That file is larger than 10 MB. Choose a smaller resume."
                        : "",
                    );
                  }}
                  required
                  className="sr-only"
                />
                <span className="grid size-12 place-items-center rounded-2xl bg-white text-primary shadow-sm ring-1 ring-border/70">
                  {file ? <FileText className="size-5" /> : <UploadCloud className="size-5" />}
                </span>
                <span className="mt-4 text-sm font-semibold">
                  {file ? file.name : "Choose a resume or drop it here"}
                </span>
                <span className="mt-1 text-xs text-muted-foreground">
                  {file ? `${Math.max(1, Math.round(file.size / 1024))} KB · Ready to parse` : "Up to 10 MB"}
                </span>
              </label>

              {error && <p role="alert" className="mt-4 text-sm text-destructive">{error}</p>}
              <Button
                type="submit"
                size="lg"
                disabled={uploading || !file || file.size > MAX_RESUME_SIZE || !token}
                className="mt-6 h-10 w-full rounded-xl"
              >
                {uploading ? <LoaderCircle className="animate-spin" data-icon="inline-start" /> : null}
                {uploading ? "Reading your experience…" : "Build my profile"}
                {!uploading && <ArrowRight data-icon="inline-end" />}
              </Button>
            </form>
          ) : (
            <form onSubmit={handleFinish}>
              <div>
                <p className="text-xs font-semibold text-primary">02 · Preferences</p>
                <h2 className="mt-2 text-xl font-semibold tracking-[-0.03em]">Confirm what you want next.</h2>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">
                  Suggestions come from your resume. Edit them freely or continue using the resume alone.
                </p>
              </div>

              {needsExtractionRetry && (
                <div className="mt-5 flex flex-col gap-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex gap-3">
                    <AlertTriangle className="mt-0.5 size-4 shrink-0" />
                    <p>
                      Your resume text is saved, but automatic extraction is limited right now. Retry through OpenRouter, add roles yourself, or continue using the resume text.
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    className="min-h-10 shrink-0 rounded-xl border-amber-300 bg-white/70"
                    disabled={retrying || !token}
                    onClick={() => void retryExtraction()}
                  >
                    {retrying && <LoaderCircle className="animate-spin" data-icon="inline-start" />}
                    {retrying ? "Retrying…" : "Retry with OpenRouter"}
                  </Button>
                </div>
              )}

              {hasExtractionSignal(extracted) && (
                <div className="mt-5 rounded-xl bg-muted/50 p-4 text-sm">
                  <p className="font-medium">Extracted profile</p>
                  <div className="mt-2 space-y-1 text-muted-foreground">
                    {extracted?.recent_titles?.length ? <p>Recent roles: {extracted.recent_titles.join(", ")}</p> : null}
                    {extracted?.skills?.length ? <p>Skills: {extracted.skills.slice(0, 10).join(", ")}</p> : null}
                    {extracted?.years_of_experience ? <p>Experience: {extracted.years_of_experience} years</p> : null}
                  </div>
                  {hybridExtraction && (
                    <p className="mt-3 text-xs leading-5 text-muted-foreground">
                      We supplemented some details with local parsing. Review these suggestions before continuing.
                    </p>
                  )}
                </div>
              )}

              <div className="mt-7 space-y-7">
                {questions.map((question) => {
                  if (question.id === "target_roles") {
                    return (
                      <fieldset key={question.id} className="space-y-3">
                        <legend className="text-sm font-medium">{question.text}</legend>
                        {roleSuggestions.length > 0 && (
                          <div>
                            <p className="mb-2 text-xs text-muted-foreground">Suggested from your resume</p>
                            <div className="flex flex-wrap gap-2">
                              {roleSuggestions.map((role) => (
                                <button
                                  key={role}
                                  type="button"
                                  onClick={() => addRole(role)}
                                  disabled={selectedRoles.some((selectedRole) => selectedRole.toLocaleLowerCase() === role.toLocaleLowerCase())}
                                  className="rounded-xl border border-border bg-white px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:border-primary/20 hover:text-foreground disabled:opacity-40"
                                >
                                  <Plus className="mr-1 inline size-3.5" />
                                  {role}
                                </button>
                              ))}
                            </div>
                          </div>
                        )}
                        {selectedRoles.length > 0 && (
                          <div className="flex flex-wrap gap-2" aria-label="Selected target roles">
                            {selectedRoles.map((role) => (
                              <span key={role} className="inline-flex items-center gap-1 rounded-xl bg-primary/8 px-3 py-2 text-sm font-medium text-primary">
                                {role}
                                <button type="button" onClick={() => removeRole(role)} aria-label={`Remove ${role}`}>
                                  <X className="size-3.5" />
                                </button>
                              </span>
                            ))}
                          </div>
                        )}
                        <div className="flex gap-2">
                          <Input
                            value={roleDraft}
                            onChange={(event) => setRoleDraft(event.target.value)}
                            onKeyDown={(event) => {
                              if (event.key === "Enter" || event.key === ",") {
                                event.preventDefault();
                                addRole();
                              }
                            }}
                            placeholder="Type any role title"
                            className="h-10 rounded-xl bg-white"
                          />
                          <Button type="button" variant="outline" className="rounded-xl" onClick={() => addRole()} disabled={!roleDraft.trim()}>
                            Add
                          </Button>
                        </div>
                      </fieldset>
                    );
                  }

                  if (question.id === "company_tiers") {
                    const selectedTiers = Array.isArray(answers.company_tiers) ? answers.company_tiers : [];
                    const companyMode = answers.company_filter_mode === "top_reputed"
                      ? "top_reputed"
                      : selectedTiers.includes("any")
                        ? "all"
                        : "";
                    return (
                      <fieldset key={question.id} className="space-y-3">
                        <legend className="text-sm font-medium">{question.text}</legend>
                        <div className="grid gap-2 sm:grid-cols-2">
                          {([
                            ["all", "All companies", "Keep assessed and unassessed employers visible."],
                            ["top_reputed", "Top reputed", "Use AI-assessed employer reputation to focus results."],
                          ] as const).map(([value, label, description]) => (
                            <button
                              key={value}
                              type="button"
                              aria-pressed={companyMode === value}
                              onClick={() => selectCompanyMode(value)}
                              className={cn(
                                "rounded-xl border p-3 text-left transition-colors",
                                companyMode === value
                                  ? "border-primary/25 bg-primary/8"
                                  : "border-border bg-white hover:border-primary/20",
                              )}
                            >
                              <span className="block text-sm font-medium">{label}</span>
                              <span className="mt-1 block text-xs leading-5 text-muted-foreground">{description}</span>
                            </button>
                          ))}
                        </div>
                      </fieldset>
                    );
                  }

                  const value = answers[question.id];
                  if (question.type === "multiselect" && question.options?.length) {
                    const selected = Array.isArray(value) ? value : [];
                    return (
                      <fieldset key={question.id} className="space-y-3">
                        <legend className="text-sm font-medium">{question.text}</legend>
                        <div className="flex flex-wrap gap-2">
                          {question.options.map((option) => {
                            const isSelected = selected.includes(option);
                            return (
                              <button
                                key={option}
                                type="button"
                                aria-pressed={isSelected}
                                onClick={() => {
                                  const next = isSelected
                                    ? selected.filter((item) => item !== option)
                                    : [...selected, option];
                                  updateAnswer(question.id, next);
                                  void persistAnswer(question.id, next);
                                }}
                                className={cn(
                                  "rounded-xl border px-3 py-2 text-sm font-medium transition-colors",
                                  isSelected
                                    ? "border-primary/25 bg-primary/8 text-primary"
                                    : "border-border bg-white text-muted-foreground hover:border-primary/20 hover:text-foreground",
                                )}
                              >
                                {option}
                              </button>
                            );
                          })}
                        </div>
                      </fieldset>
                    );
                  }

                  return (
                    <div key={question.id} className="space-y-3">
                      <Label htmlFor={question.id}>{question.text}</Label>
                      <Input
                        id={question.id}
                        value={Array.isArray(value) ? value.join(", ") : (value ?? "")}
                        onChange={(event) => updateAnswer(question.id, event.target.value)}
                        onBlur={() => {
                          const answer = answers[question.id];
                          if (answer !== undefined) void persistAnswer(question.id, answer);
                        }}
                        placeholder={question.id === "preferred_locations" ? "Cities, regions, remote, or relocation" : "Optional"}
                        className="h-10 rounded-xl bg-white"
                      />
                    </div>
                  );
                })}
              </div>

              {draftWarning && <p className="mt-5 text-sm text-amber-800">{draftWarning}</p>}
              {error && <p role="alert" className="mt-5 text-sm text-destructive">{error}</p>}

              <div className="mt-8 flex flex-col gap-3">
                <Button type="submit" size="lg" className="h-10 rounded-xl px-5" disabled={finishing}>
                  {finishing && <LoaderCircle className="animate-spin" data-icon="inline-start" />}
                  {finishing ? "Preparing matches…" : "Save preferences and rank jobs"}
                  {!finishing && <ArrowRight data-icon="inline-end" />}
                </Button>
                <Button type="button" variant="ghost" className="rounded-xl" onClick={() => void finishOnboarding(false)} disabled={finishing}>
                  Continue using resume only
                </Button>
                <Button type="button" variant="ghost" className="rounded-xl text-muted-foreground" onClick={() => setStep("upload")} disabled={finishing}>
                  Use a different resume
                </Button>
              </div>
            </form>
          )}
        </section>
      </div>
    </main>
  );
}
