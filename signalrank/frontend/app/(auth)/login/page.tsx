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

export default function LoginPage() {
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
      const response = await signIn("credentials", {
        email,
        password,
        redirect: false,
      });
      if (response?.error) {
        setError("That email and password combination doesn’t match.");
        return;
      }
      const requestedPath = new URLSearchParams(window.location.search).get("callbackUrl");
      const destination = requestedPath?.startsWith("/") && !requestedPath.startsWith("//")
        ? requestedPath
        : "/dashboard";
      router.push(destination);
    } catch {
      setError("Sign-in is temporarily unavailable. Check that the server is running and try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell
      eyebrow="Welcome back"
      title="Continue your focused search."
      description="Sign in to review fresh matches and keep your application pipeline moving."
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
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Enter your password"
            className="h-11 rounded-xl bg-white"
            required
          />
        </div>
        {error && (
          <p role="alert" className="rounded-xl border border-destructive/20 bg-destructive/5 px-3 py-2.5 text-sm text-destructive">
            {error}
          </p>
        )}
        <Button type="submit" size="lg" className="h-11 w-full rounded-xl" disabled={submitting}>
          {submitting && <LoaderCircle className="animate-spin" data-icon="inline-start" />}
          {submitting ? "Signing in…" : "Sign in"}
          {!submitting && <ArrowRight data-icon="inline-end" />}
        </Button>
        <p className="text-center text-sm text-muted-foreground">
          New to SignalRank?{" "}
          <Link href="/signup" className="font-medium text-primary hover:underline">
            Create an account
          </Link>
        </p>
      </form>
    </AuthShell>
  );
}
