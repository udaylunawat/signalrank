"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { signOut, useSession } from "next-auth/react";
import {
  BriefcaseBusiness,
  LayoutDashboard,
  LogOut,
  Radar,
  Settings,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { isDesktopMode } from "@/lib/desktop";

const navigation = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/jobs", label: "Matches", icon: Radar },
  { href: "/tracker", label: "Tracker", icon: BriefcaseBusiness },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <Link href="/dashboard" className="flex items-center gap-2.5" aria-label="SignalRank home">
      <span className="grid size-9 place-items-center rounded-xl bg-primary text-primary-foreground shadow-[0_8px_20px_rgba(89,73,205,0.25)]">
        <Sparkles className="size-4" strokeWidth={2.4} />
      </span>
      {!compact && (
        <span className="text-[15px] font-semibold tracking-[-0.03em]">SignalRank</span>
      )}
    </Link>
  );
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { data: session, status } = useSession();
  const desktopMode = isDesktopMode();
  const [sessionTimedOut, setSessionTimedOut] = useState(false);
  const accessToken = (session as { accessToken?: string } | null)?.accessToken;

  useEffect(() => {
    if (status === "unauthenticated") {
      if (desktopMode) router.replace("/desktop-setup");
      else router.replace(`/login?callbackUrl=${encodeURIComponent(pathname)}`);
    }
  }, [desktopMode, pathname, router, status]);

  useEffect(() => {
    if (status === "authenticated" && !accessToken) {
      router.replace(desktopMode ? "/desktop-setup" : "/login");
    }
  }, [accessToken, desktopMode, router, status]);

  useEffect(() => {
    const timeout = window.setTimeout(
      () => setSessionTimedOut(status === "loading"),
      status === "loading" ? 15_000 : 0,
    );
    return () => window.clearTimeout(timeout);
  }, [status]);

  if (status !== "authenticated" || !accessToken) {
    return (
      <main className="grid min-h-screen place-items-center px-4" aria-live="polite">
        <div className="text-center">
          <span className="mx-auto grid size-10 animate-pulse place-items-center rounded-xl bg-primary text-primary-foreground">
            <Sparkles className="size-4" />
          </span>
          <p className="mt-3 text-sm text-muted-foreground">
            {sessionTimedOut
              ? "The local session is taking too long to open."
              : status === "loading"
              ? "Opening your workspace…"
              : desktopMode
                ? "Starting your local session…"
                : "Taking you to sign in…"}
          </p>
          {sessionTimedOut && (
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="mt-4 rounded-xl bg-primary px-4 py-2 text-sm font-medium text-primary-foreground"
            >
              Retry
            </button>
          )}
        </div>
      </main>
    );
  }

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[236px_minmax(0,1fr)]">
      <aside className="sticky top-0 hidden h-screen border-r border-border/70 bg-white/72 px-4 py-5 backdrop-blur-xl lg:flex lg:flex-col">
        <div className="px-2">
          <Brand />
        </div>

        <nav className="mt-10 space-y-1" aria-label="Primary navigation">
          {navigation.map((item) => {
            const active = pathname === item.href;
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                  active
                    ? "bg-primary/9 text-primary"
                    : "text-muted-foreground hover:bg-white hover:text-foreground"
                )}
              >
                <Icon className="size-4" strokeWidth={active ? 2.3 : 1.9} />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="mt-auto rounded-2xl border border-border/70 bg-white/75 p-3">
          <p className="truncate text-xs font-medium text-foreground">
            {desktopMode ? "Local workspace" : session?.user?.email ?? "Your workspace"}
          </p>
          <p className="mt-0.5 text-[11px] text-muted-foreground">
            {desktopMode ? "Stored on this device" : "Personal search"}
          </p>
          {!desktopMode && (
            <button
              type="button"
              onClick={() => signOut({ callbackUrl: "/login" })}
              className="mt-3 flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <LogOut className="size-3.5" />
              Sign out
            </button>
          )}
        </div>
      </aside>

      <div className="min-w-0">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border/70 bg-background/85 px-4 backdrop-blur-xl lg:hidden">
          <Brand />
          <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-medium text-muted-foreground shadow-sm ring-1 ring-border/70">
            {desktopMode ? "Local" : "Personal"}
          </span>
        </header>

        <main className="mx-auto w-full max-w-[1180px] px-4 pb-28 pt-7 sm:px-6 lg:px-10 lg:pb-12 lg:pt-10">
          {children}
        </main>

        <nav
          className="fixed inset-x-3 bottom-3 z-40 grid grid-cols-4 rounded-2xl border border-white/80 bg-white/92 p-1.5 shadow-[0_14px_40px_rgba(35,30,75,0.18)] backdrop-blur-xl lg:hidden"
          aria-label="Mobile navigation"
        >
          {navigation.map((item) => {
            const active = pathname === item.href;
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex flex-col items-center gap-1 rounded-xl py-2 text-[11px] font-medium transition-colors",
                  active ? "bg-primary/9 text-primary" : "text-muted-foreground"
                )}
              >
                <Icon className="size-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </div>
  );
}
