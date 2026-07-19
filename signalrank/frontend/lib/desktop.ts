export function isDesktopMode() {
  return (
    process.env.NEXT_PUBLIC_SIGNALRANK_MODE === "desktop" ||
    (typeof window !== "undefined" && "__TAURI_INTERNALS__" in window)
  );
}

async function tauriInvoke<T>(command: string, args: Record<string, unknown>) {
  const { invoke, isTauri } = await import("@tauri-apps/api/core");
  if (!isTauri()) return { handled: false as const, value: null };
  return { handled: true as const, value: await invoke<T>(command, args) };
}

export async function openExternal(url: string) {
  const parsed = new URL(url);
  if (!["http:", "https:"].includes(parsed.protocol)) {
    throw new Error("Only web links can be opened");
  }
  if (isDesktopMode() && parsed.protocol !== "https:") {
    throw new Error("Only secure job links can be opened");
  }
  if (isDesktopMode()) {
    const result = await tauriInvoke<void>("open_external", { url: parsed.href });
    if (result.handled) return;
  }
  const opened = window.open(parsed.href, "_blank", "noopener,noreferrer");
  if (!opened) throw new Error("Your browser blocked the new tab");
}

export async function saveDownload(blob: Blob, filename: string) {
  if (isDesktopMode()) {
    const data = Array.from(new Uint8Array(await blob.arrayBuffer()));
    const result = await tauriInvoke<boolean>("save_download", { filename, data });
    if (result.handled) return result.value;
  }
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1_000);
  return true;
}
