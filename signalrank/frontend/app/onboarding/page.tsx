"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { ArrowRight, Check, FileText, LoaderCircle, ShieldCheck, UploadCloud } from "lucide-react";
import { Brand } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

type Question = {
  id: string;
  text: string;
  type: "text" | "multiselect";
  options?: string[];
};

type Answer = string | string[];

export default function OnboardingPage() {
  const { data: session } = useSession();
  const router = useRouter();
  const token = (session as { accessToken?: string })?.accessToken ?? "";

  const [step, setStep] = useState<"upload" | "questions">("upload");
  const [file, setFile] = useState<File | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Record<string, Answer>>({});
  const [uploading, setUploading] = useState(false);
  const [finishing, setFinishing] = useState(false);
  const [error, setError] = useState("");

  async function handleUpload(event: React.FormEvent) {
    event.preventDefault();
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      const response = await api.onboarding.uploadResume(token, file);
      setQuestions(response.questions as Question[]);
      setStep("questions");
    } catch {
      setError("We couldn’t read that resume. Check the file and try again.");
    } finally {
      setUploading(false);
    }
  }

  function toggleOption(questionId: string, option: string) {
    setAnswers((current) => {
      const selected = Array.isArray(current[questionId]) ? (current[questionId] as string[]) : [];
      if (questionId === "company_tiers") {
        if (option === "Any company") {
          return {
            ...current,
            [questionId]: selected.includes(option) ? [] : [option],
          };
        }
        const withoutAny = selected.filter((item) => item !== "Any company");
        return {
          ...current,
          [questionId]: withoutAny.includes(option)
            ? withoutAny.filter((item) => item !== option)
            : [...withoutAny, option],
        };
      }
      return {
        ...current,
        [questionId]: selected.includes(option)
          ? selected.filter((item) => item !== option)
          : [...selected, option],
      };
    });
  }

  async function handleFinish(event: React.FormEvent) {
    event.preventDefault();
    setFinishing(true);
    setError("");
    try {
      for (const [questionId, answer] of Object.entries(answers)) {
        if ((typeof answer === "string" && answer.trim()) || (Array.isArray(answer) && answer.length)) {
          await api.onboarding.refine(token, questionId, answer);
        }
      }
      await api.onboarding.refine(token, "onboarding_complete", "true");
      await api.runs.trigger(token);
      router.push("/dashboard");
    } catch {
      setError("Your preferences didn’t finish saving. Nothing was lost—please try again.");
    } finally {
      setFinishing(false);
    }
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
              Your resume stays private to your account
            </div>
            <div className="flex items-center gap-3">
              <span className="grid size-8 place-items-center rounded-xl bg-indigo-50 text-indigo-700">
                <Check className="size-4" />
              </span>
              You can refine preferences after setup
            </div>
          </div>
        </section>

        <section className="surface-panel p-5 sm:p-7">
          {step === "upload" ? (
            <form onSubmit={handleUpload}>
              <div>
                <p className="text-xs font-semibold text-primary">01 · Resume</p>
                <h2 className="mt-2 text-xl font-semibold tracking-[-0.03em]">Start with what you’ve already built.</h2>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">
                  Upload a PDF, DOCX, or TXT file. We’ll turn it into a structured profile.
                </p>
              </div>

              <label
                htmlFor="resume"
                className={cn(
                  "mt-7 flex min-h-56 cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed p-6 text-center transition-colors",
                  file
                    ? "border-primary/35 bg-primary/5"
                    : "border-border bg-muted/35 hover:border-primary/30 hover:bg-primary/4"
                )}
              >
                <Input
                  id="resume"
                  type="file"
                  accept=".pdf,.docx,.txt"
                  onChange={(event) => setFile(event.target.files?.[0] ?? null)}
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

              {error && <p className="mt-4 text-sm text-destructive">{error}</p>}
              <Button
                type="submit"
                size="lg"
                disabled={uploading || !file || !token}
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
                <h2 className="mt-2 text-xl font-semibold tracking-[-0.03em]">A few details to sharpen the ranking.</h2>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">
                  Skip anything you’re unsure about. You can adjust these later.
                </p>
              </div>

              <div className="mt-7 space-y-7">
                {questions.map((question) => (
                  <fieldset key={question.id} className="space-y-3">
                    <Label htmlFor={question.type === "text" ? question.id : undefined}>
                      {question.text}
                    </Label>
                    {question.type === "multiselect" && question.options?.length ? (
                      <div className="flex flex-wrap gap-2">
                        {question.options.map((option) => {
                          const selected = Array.isArray(answers[question.id])
                            ? answers[question.id].includes(option)
                            : false;
                          return (
                            <button
                              key={option}
                              type="button"
                              aria-pressed={selected}
                              onClick={() => toggleOption(question.id, option)}
                              className={cn(
                                "rounded-xl border px-3 py-2 text-sm font-medium transition-colors",
                                selected
                                  ? "border-primary/25 bg-primary/8 text-primary"
                                  : "border-border bg-white text-muted-foreground hover:border-primary/20 hover:text-foreground"
                              )}
                            >
                              {option}
                            </button>
                          );
                        })}
                      </div>
                    ) : (
                      <Input
                        id={question.id}
                        value={typeof answers[question.id] === "string" ? answers[question.id] : ""}
                        onChange={(event) =>
                          setAnswers((current) => ({ ...current, [question.id]: event.target.value }))
                        }
                        placeholder="Type your answer"
                        className="h-10 rounded-xl bg-white"
                      />
                    )}
                  </fieldset>
                ))}
              </div>

              {questions.length === 0 && (
                <div className="mt-7 rounded-xl bg-muted/50 p-4 text-sm text-muted-foreground">
                  Your profile looks complete. We have enough signal to start ranking.
                </div>
              )}
              {error && <p className="mt-5 text-sm text-destructive">{error}</p>}

              <div className="mt-8 flex flex-col-reverse gap-2 sm:flex-row sm:justify-between">
                <Button type="button" variant="ghost" className="rounded-xl" onClick={() => setStep("upload")}>
                  Use a different resume
                </Button>
                <Button type="submit" size="lg" className="h-10 rounded-xl px-5" disabled={finishing}>
                  {finishing && <LoaderCircle className="animate-spin" data-icon="inline-start" />}
                  {finishing ? "Preparing matches…" : "Finish and rank jobs"}
                  {!finishing && <ArrowRight data-icon="inline-end" />}
                </Button>
              </div>
            </form>
          )}
        </section>
      </div>
    </main>
  );
}
