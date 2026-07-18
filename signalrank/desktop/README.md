# SignalRank Desktop

The Tauri 2 shell runs the SignalRank Next.js UI and FastAPI API entirely on
the user's machine. Both services bind to random `127.0.0.1` ports. The shell
generates a fresh bootstrap token for each launch and shares a persistent,
installation-local session secret with the bundled sidecars.

No SignalRank cloud service, PostgreSQL server, system Node.js, or system
Python installation is used by a packaged build. Job-source scraping and
OpenRouter are the only application network paths, apart from signed update
checks and HTTPS job links opened by the user.

## OpenRouter key

During first-run setup, enter an OpenRouter API key before uploading the resume.
SignalRank validates it against OpenRouter, then saves it in the operating
system credential store under the SignalRank Desktop entry. The key is never
written to the local SQLite database or sent to SignalRank cloud services.

To replace or remove it later, open Settings → Local OpenRouter. If the
operating system credential store is unavailable, the validated key remains in
memory for the current app session and the UI reports that fallback.

## Development

Install the frontend, backend, and desktop dependencies, then run:

```bash
cd signalrank/desktop
npm run dev
```

The development launcher uses an isolated `signalrank/.desktop-data` directory,
a random backend port, and a per-launch bootstrap token. Next.js remains on
`127.0.0.1:3000` because Tauri's development URL is fixed.

## Packaging

```bash
cd signalrank/desktop
npm run build
npm run smoke:packaged
```

The build packages FastAPI with PyInstaller, builds Next.js in standalone mode,
stages the platform-native backend and Node runtimes as Tauri sidecars, and
bundles the local MiniLM embedding model before creating the native installers
for the current OS. Build on each target OS; PyInstaller and the bundled Node
runtime are platform-native.

Release CI builds macOS, Windows, and Linux artifacts. The Tauri signing key
must be configured as `TAURI_SIGNING_PRIVATE_KEY` and
`TAURI_SIGNING_PRIVATE_KEY_PASSWORD`. Platform signing and notarization use the
standard Apple and Windows signing secrets referenced by the workflow.

## Native boundary

The renderer can invoke only two application commands:

- `open_external` accepts an absolute HTTPS URL.
- `save_download` opens a native save dialog and sanitizes the proposed name.

There is no generic shell, filesystem, or arbitrary URL capability exposed to
the renderer.
