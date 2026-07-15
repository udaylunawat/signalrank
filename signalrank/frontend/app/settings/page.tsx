"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { Check, LoaderCircle, Save, Settings2 } from "lucide-react";
import AppShell from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ProfileConfig } from "@/types";

const COMPANY_TIERS = [
  ["tier_s", "S · Exceptional reputation"],
  ["tier_a", "A · Strong reputation"],
  ["tier_b", "B · Established reputation"],
  ["tier_c", "C · Limited reputation evidence"],
] as const;

function asText(values: string[] | undefined) {
  return values?.join(", ") ?? "";
}

function asList(value: string) {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

export default function SettingsPage() {
  const { data: session } = useSession();
  const token = (session as { accessToken?: string })?.accessToken ?? "";
  const [config, setConfig] = useState<ProfileConfig>({});
  const [roles, setRoles] = useState("");
  const [locations, setLocations] = useState("");
  const [preferredCompanies, setPreferredCompanies] = useState("");
  const [excludedCompanies, setExcludedCompanies] = useState("");
  const [excludedTitles, setExcludedTitles] = useState("");
  const [companyTiers, setCompanyTiers] = useState<string[]>([]);
  const [companyFilterMode, setCompanyFilterMode] = useState<
    "all" | "top_reputed" | "selected_tiers"
  >("all");
  const [hasResume, setHasResume] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) return;
    let active = true;
    api.profile.get(token)
      .then((response) => {
        if (!active) return;
        const profile = response.profile;
        const nextConfig = profile?.config_overrides ?? {};
        setConfig(nextConfig);
        setRoles(asText(nextConfig.profile_intent?.roles));
        setLocations(asText(nextConfig.location_scoring?.preferred_locations ?? nextConfig.scraping?.locations));
        setPreferredCompanies(asText(nextConfig.company_preferences?.preferred_companies));
        const titleExclusions = nextConfig.title_blocklist ?? [];
        const companyExclusions = nextConfig.company_preferences?.excluded_companies ?? [];
        const legacyCombined =
          titleExclusions.length > 0 &&
          titleExclusions.join("\u0000") === companyExclusions.join("\u0000");
        setExcludedCompanies(legacyCombined ? "" : asText(companyExclusions));
        setExcludedTitles(asText(titleExclusions));
        setCompanyTiers(nextConfig.company_preferences?.tiers ?? []);
        setCompanyFilterMode(nextConfig.company_preferences?.filter_mode ?? "all");
        setHasResume(Boolean(profile?.resume_text || profile?.distilled_text));
      })
      .catch(() => active && setError("We couldn’t load your preferences."))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [token]);

  function toggleTier(tier: string) {
    setCompanyFilterMode("selected_tiers");
    setCompanyTiers((current) => {
      const withoutAny = current.filter((item) => item !== "any");
      return withoutAny.includes(tier)
        ? withoutAny.filter((item) => item !== tier)
        : [...withoutAny, tier];
    });
  }

  async function savePreferences(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setSaved(false);
    setError("");
    const preferredLocations = asList(locations);
    const targetRoles = asList(roles);
    const excludedCompanyValues = asList(excludedCompanies);
    const excludedTitleValues = asList(excludedTitles);
    const profileIntent = {
      ...config.profile_intent,
      roles: targetRoles,
    };
    delete profileIntent.preset;
    const nextConfig: ProfileConfig = {
      ...config,
      profile_intent: profileIntent,
      scraping: {
        ...config.scraping,
        locations: preferredLocations,
      },
      location_scoring: {
        ...config.location_scoring,
        preferred_locations: preferredLocations,
        preferred_weight: config.location_scoring?.preferred_weight ?? 1.4,
      },
      company_preferences: {
        ...config.company_preferences,
        filter_mode: companyFilterMode,
        tiers:
          companyFilterMode === "all"
            ? ["any"]
            : companyFilterMode === "top_reputed"
              ? ["tier_s", "tier_a"]
              : companyTiers,
        preferred_companies: asList(preferredCompanies),
        excluded_companies: excludedCompanyValues,
      },
      title_blocklist: excludedTitleValues,
    };

    try {
      await api.profile.patch(token, {
        target_roles: targetRoles,
        preferred_locations: preferredLocations,
        config_overrides: nextConfig,
      });
      setConfig(nextConfig);
      setSaved(true);
    } catch {
      setError("Your preferences weren’t saved. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <AppShell>
      <section>
        <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-primary/10 bg-primary/7 px-3 py-1.5 text-xs font-medium text-primary">
          <Settings2 className="size-3.5" />
          Ranking preferences
        </div>
        <h1 className="page-title">Tune what SignalRank looks for.</h1>
        <p className="page-copy max-w-2xl">
          These preferences shape discovery and ranking on your next refresh. Separate multiple entries with commas.
        </p>
      </section>

      {loading ? (
        <div className="mt-8 space-y-3" aria-label="Loading preferences">
          {Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="h-36 animate-pulse rounded-2xl border border-border/70 bg-white/60" />
          ))}
        </div>
      ) : (
        <form onSubmit={savePreferences} className="mt-8 space-y-5">
          <section className="surface-panel p-5 sm:p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="font-semibold tracking-[-0.02em]">Roles and search intent</h2>
                <p className="mt-1 text-sm text-muted-foreground">Include adjacent titles you would seriously consider.</p>
              </div>
              <span className={cn(
                "rounded-full px-2.5 py-1 text-[11px] font-medium",
                hasResume ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-800"
              )}>
                {hasResume ? "Resume on file" : "Resume missing"}
              </span>
            </div>
            <div className="mt-5 max-w-2xl">
              <div className="space-y-2">
                <Label htmlFor="roles">Target roles</Label>
                <Input
                  id="roles"
                  value={roles}
                  onChange={(event) => setRoles(event.target.value)}
                  placeholder="QA Engineer, Product Designer, Financial Analyst"
                  className="h-10 rounded-xl bg-white"
                />
              </div>
            </div>
          </section>

          <section className="surface-panel p-5 sm:p-6">
            <h2 className="font-semibold tracking-[-0.02em]">Location preferences</h2>
            <p className="mt-1 text-sm text-muted-foreground">Used for both source queries and location scoring.</p>
            <div className="mt-5 max-w-xl">
              <div className="space-y-2">
                <Label htmlFor="locations">Preferred locations</Label>
                <Input
                  id="locations"
                  value={locations}
                  onChange={(event) => setLocations(event.target.value)}
                  placeholder="Bengaluru, Remote, India"
                  className="h-10 rounded-xl bg-white"
                />
              </div>
            </div>
          </section>

          <section className="surface-panel p-5 sm:p-6">
            <h2 className="font-semibold tracking-[-0.02em]">Companies and exclusions</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Reputation is assessed by a free OpenRouter model using the same role-independent rubric for every company.
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              {([
                ["all", "All companies"],
                ["top_reputed", "Top reputed (AI)"],
                ["selected_tiers", "Choose AI tiers"],
              ] as const).map(([mode, label]) => (
                <button
                  key={mode}
                  type="button"
                  aria-pressed={companyFilterMode === mode}
                  onClick={() => setCompanyFilterMode(mode)}
                  className={cn(
                    "rounded-xl border px-3 py-2 text-sm font-medium transition-colors",
                    companyFilterMode === mode
                      ? "border-primary/25 bg-primary/8 text-primary"
                      : "border-border bg-white text-muted-foreground hover:border-primary/20 hover:text-foreground",
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
            <fieldset className="mt-5">
              <legend className="text-sm font-medium">Eligible reputation tiers</legend>
              <div className="mt-2 flex flex-wrap gap-2">
                {COMPANY_TIERS.map(([tier, label]) => {
                  const selected = companyTiers.includes(tier);
                  return (
                    <button
                      key={tier}
                      type="button"
                      disabled={companyFilterMode !== "selected_tiers"}
                      aria-pressed={selected}
                      onClick={() => toggleTier(tier)}
                      className={cn(
                        "rounded-xl border px-3 py-2 text-sm font-medium transition-colors",
                        selected
                          ? "border-primary/25 bg-primary/8 text-primary"
                          : "border-border bg-white text-muted-foreground hover:border-primary/20 hover:text-foreground"
                      )}
                    >
                      {selected && <Check className="mr-1 inline size-3.5" />}
                      {label}
                    </button>
                  );
                })}
              </div>
            </fieldset>
            <div className="mt-5 grid gap-5 lg:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor="preferred-companies">Preferred companies</Label>
                <Input
                  id="preferred-companies"
                  value={preferredCompanies}
                  onChange={(event) => setPreferredCompanies(event.target.value)}
                  placeholder="OpenAI, Anthropic, Google"
                  className="h-10 rounded-xl bg-white"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="excluded-companies">Excluded companies</Label>
                <Input
                  id="excluded-companies"
                  value={excludedCompanies}
                  onChange={(event) => setExcludedCompanies(event.target.value)}
                  placeholder="Deloitte, staffing agency"
                  className="h-10 rounded-xl bg-white"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="excluded-titles">Excluded job titles</Label>
                <Input
                  id="excluded-titles"
                  value={excludedTitles}
                  onChange={(event) => setExcludedTitles(event.target.value)}
                  placeholder="Titles or work you do not want"
                  className="h-10 rounded-xl bg-white"
                />
              </div>
            </div>
          </section>

          {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
          <div className="flex items-center justify-end gap-3">
            {saved && <span className="flex items-center gap-1.5 text-sm font-medium text-emerald-700"><Check className="size-4" />Saved</span>}
            <Button type="submit" size="lg" className="h-10 rounded-xl px-5" disabled={saving || !token}>
              {saving ? <LoaderCircle className="animate-spin" data-icon="inline-start" /> : <Save data-icon="inline-start" />}
              {saving ? "Saving…" : "Save preferences"}
            </Button>
          </div>
        </form>
      )}
    </AppShell>
  );
}
