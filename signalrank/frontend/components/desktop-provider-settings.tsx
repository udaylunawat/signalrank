"use client";

import { useEffect, useState } from "react";
import { Check, KeyRound, LoaderCircle, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, api } from "@/lib/api";
import { isDesktopMode } from "@/lib/desktop";
import type { DesktopStatus } from "@/types";

export default function DesktopProviderSettings({ token }: { token: string }) {
  const desktopMode = isDesktopMode();
  const [status, setStatus] = useState<DesktopStatus | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [loading, setLoading] = useState(desktopMode);
  const [saving, setSaving] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!desktopMode || !token) return;
    let active = true;
    api.desktop
      .status(token)
      .then((nextStatus) => active && setStatus(nextStatus))
      .catch(() => active && setError("OpenRouter status could not be loaded."))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [desktopMode, token]);

  if (!desktopMode) return null;

  async function saveKey() {
    if (!apiKey.trim()) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const response = await api.desktop.saveProviderKey(apiKey.trim(), token);
      const nextStatus = await api.desktop.status(token);
      setStatus(nextStatus);
      setApiKey("");
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
      setSaving(false);
    }
  }

  async function removeKey() {
    setRemoving(true);
    setError("");
    setNotice("");
    try {
      await api.desktop.deleteProviderKey(token);
      setStatus((current) =>
        current ? { ...current, provider_configured: false } : current,
      );
      setNotice("OpenRouter key removed from the credential store.");
    } catch (removeError) {
      if (
        removeError instanceof ApiError &&
        [404, 405, 501].includes(removeError.status)
      ) {
        setNotice(
          "This desktop build cannot remove the key here. Replacing it remains supported.",
        );
      } else {
        setError("The OpenRouter key could not be removed.");
      }
    } finally {
      setRemoving(false);
    }
  }

  return (
    <section className="surface-panel p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <KeyRound className="size-4 text-primary" />
            <h2 className="font-semibold tracking-[-0.02em]">Local OpenRouter</h2>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            The key is validated by the local backend and stored in your operating
            system credential store, never in the SignalRank database.
          </p>
        </div>
        <span className="rounded-full bg-muted px-2.5 py-1 text-[11px] font-medium text-muted-foreground">
          {loading
            ? "Checking…"
            : status?.provider_configured
              ? "Configured"
              : "Not configured"}
        </span>
      </div>

      <div className="mt-5 max-w-2xl">
        <Label htmlFor="settings-openrouter-key">
          {status?.provider_configured ? "Replace API key" : "OpenRouter API key"}
        </Label>
        <div className="mt-2 flex flex-col gap-2 sm:flex-row">
          <Input
            id="settings-openrouter-key"
            type="password"
            autoComplete="off"
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
            placeholder="sk-or-v1-…"
            className="h-10 rounded-xl bg-white"
          />
          <Button
            type="button"
            className="rounded-xl"
            disabled={saving || !apiKey.trim()}
            onClick={() => void saveKey()}
          >
            {saving ? (
              <LoaderCircle className="animate-spin" data-icon="inline-start" />
            ) : (
              <Check data-icon="inline-start" />
            )}
            {saving ? "Validating…" : "Validate and save"}
          </Button>
        </div>
      </div>

      {status?.provider_configured && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="mt-3 rounded-xl text-muted-foreground"
          onClick={removeKey}
          disabled={removing}
        >
          {removing ? (
            <LoaderCircle className="animate-spin" data-icon="inline-start" />
          ) : (
            <Trash2 data-icon="inline-start" />
          )}
          {removing ? "Removing…" : "Remove saved key"}
        </Button>
      )}

      {notice && <p className="mt-3 text-sm text-emerald-700">{notice}</p>}
      {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
    </section>
  );
}
