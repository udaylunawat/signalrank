"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Question = {
  id: string;
  text: string;
  type: "text" | "multiselect";
  options?: string[];
};

export default function OnboardingPage() {
  const { data: session } = useSession();
  const router = useRouter();
  const token = (session as { accessToken?: string })?.accessToken ?? "";

  const [step, setStep] = useState<"upload" | "questions" | "done">("upload");
  const [file, setFile] = useState<File | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      const res = await api.onboarding.uploadResume(token, file);
      setQuestions(res.questions as Question[]);
      setStep("questions");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function handleFinish(e: React.FormEvent) {
    e.preventDefault();
    for (const [qid, answer] of Object.entries(answers)) {
      if (answer.trim()) {
        await api.onboarding.refine(token, qid, answer);
      }
    }
    await api.onboarding.refine(token, "onboarding_complete", "true");
    await api.runs.trigger(token);
    router.push("/dashboard");
  }

  if (step === "upload") {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <Card className="w-full max-w-lg">
          <CardHeader>
            <CardTitle>Upload your resume</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleUpload} className="space-y-4">
              <div className="space-y-1">
                <Label htmlFor="resume">PDF, DOCX, or TXT</Label>
                <Input
                  id="resume"
                  type="file"
                  accept=".pdf,.docx,.txt"
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  required
                />
              </div>
              {error && <p className="text-sm text-red-500">{error}</p>}
              <Button type="submit" disabled={uploading || !file} className="w-full">
                {uploading ? "Parsing..." : "Continue"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <Card className="w-full max-w-lg">
        <CardHeader>
          <CardTitle>Tell us about your preferences</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleFinish} className="space-y-6">
            {questions.map((q: Question) => (
              <div key={q.id} className="space-y-1">
                <Label htmlFor={q.id}>{q.text}</Label>
                <Input
                  id={q.id}
                  value={answers[q.id] ?? ""}
                  onChange={(e) =>
                    setAnswers((a) => ({ ...a, [q.id]: e.target.value }))
                  }
                  placeholder="Your answer"
                />
              </div>
            ))}
            <Button type="submit" className="w-full">
              Finish setup
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
