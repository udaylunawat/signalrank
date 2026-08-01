export function isDesktopMode() {
  return (
    process.env.NEXT_PUBLIC_SIGNALRANK_MODE === "desktop" ||
    (typeof window !== "undefined" && "__TAURI_INTERNALS__" in window)
  );
}

async function tauriInvoke<T>(command: string, args: Record<string, unknown>) {
  const { invoke, isTauri } = await import("@tauri-apps/api/core");
  if (!isTauri()) return null;
  return invoke<T>(command, args);
}

export async function openExternal(url: string) {
  const parsed = new URL(url);
  if (parsed.protocol !== "https:" || parsed.username || parsed.password) {
    throw new Error("Only absolute HTTPS job links without credentials can be opened");
  }
  if (isDesktopMode()) {
    const result = await tauriInvoke<void>("open_external", { url: parsed.href });
    if (result !== null) return;
  }
  window.open(parsed.href, "_blank", "noopener,noreferrer");
}

export async function saveDownload(blob: Blob, filename: string) {
  if (isDesktopMode()) {
    const data = Array.from(new Uint8Array(await blob.arrayBuffer()));
    const result = await tauriInvoke<void>("save_download", { filename, data });
    if (result !== null) return;
  }
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1_000);
}
