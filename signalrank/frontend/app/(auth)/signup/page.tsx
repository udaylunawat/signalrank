"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { signIn } from "next-auth/react";
import { ArrowRight, LoaderCircle } from "lucide-react";
import AuthShell from "@/components/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, api } from "@/lib/api";

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await api.auth.register(email, password);
      const response = await signIn("credentials", { email, password, redirect: false });
      if (response?.error) {
        setError("Your account was created, but sign-in failed. Try signing in directly.");
        return;
      }
      router.push("/onboarding");
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        setError("An account with that email already exists. Sign in instead.");
      } else if (error instanceof ApiError && error.status === 422) {
        setError("Check your email and password, then try again.");
      } else {
        setError("Signup is temporarily unavailable. Check that the server is running and try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell
      eyebrow="Create your workspace"
      title="Start with better-fit roles."
      description="Create an account, add your resume, and get a ranked shortlist built around your experience."
    >
      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="space-y-2">
          <Label htmlFor="email">Email address</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
            className="h-11 rounded-xl bg-white"
            required
          />
        </div>
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-3">
            <Label htmlFor="password">Password</Label>
            <span className="text-xs text-muted-foreground">At least 6 characters</span>
          </div>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Create a password"
            className="h-11 rounded-xl bg-white"
            required
            minLength={6}
          />
        </div>
        {error && (
          <p role="alert" className="rounded-xl border border-destructive/20 bg-destructive/5 px-3 py-2.5 text-sm text-destructive">
            {error}
          </p>
        )}
        <Button type="submit" size="lg" className="h-11 w-full rounded-xl" disabled={submitting}>
          {submitting && <LoaderCircle className="animate-spin" data-icon="inline-start" />}
          {submitting ? "Creating account…" : "Create account"}
          {!submitting && <ArrowRight data-icon="inline-end" />}
        </Button>
        <p className="text-center text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link href="/login" className="font-medium text-primary hover:underline">
            Sign in
          </Link>
        </p>
      </form>
    </AuthShell>
  );
}
