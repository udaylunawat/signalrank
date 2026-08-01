import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { delimiter, dirname, resolve } from "node:path";
import { createFixtureBackend } from "./fixture-backend.mjs";

const frontendDir = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
const mode = process.env.E2E_MODE === "desktop" ? "desktop" : "saas";
const port = Number(process.env.E2E_PORT ?? 3011);
const fixturePort = Number(process.env.E2E_FIXTURE_PORT ?? (mode === "desktop" ? 8112 : 8111));
const secret = "e2e-only-signalrank-secret-32-chars";
const nodePath = `${dirname(process.execPath)}${delimiter}${process.env.PATH ?? ""}`;
const fixture = createFixtureBackend({ port: fixturePort });
await fixture.listen();

const child = spawn(
  process.execPath,
  [resolve(frontendDir, "node_modules/next/dist/bin/next"), "dev", "-p", String(port)],
  {
    cwd: frontendDir,
    env: {
      ...process.env,
      BACKEND_URL: `http://127.0.0.1:${fixturePort}`,
      NEXT_PUBLIC_API_URL: `http://127.0.0.1:${fixturePort}`,
      AUTH_SECRET: secret,
      NEXTAUTH_SECRET: secret,
      AUTH_URL: `http://127.0.0.1:${port}`,
      NEXTAUTH_URL: `http://127.0.0.1:${port}`,
      SIGNALRANK_MODE: mode === "desktop" ? "desktop" : "server",
      NEXT_PUBLIC_SIGNALRANK_MODE: mode === "desktop" ? "desktop" : "server",
      SIGNALRANK_DESKTOP_BOOTSTRAP_TOKEN: "fixture-desktop-bootstrap",
      E2E_FIXTURE_MODE: "1",
      PATH: nodePath,
    },
    stdio: "inherit",
  },
);

function shutdown(code = 0) {
  child.kill("SIGTERM");
  void fixture.close().finally(() => process.exit(code));
}

process.once("SIGINT", () => shutdown(0));
process.once("SIGTERM", () => shutdown(0));
child.once("exit", (code, signal) => {
  if (signal) return shutdown(0);
  shutdown(code ?? 1);
});
