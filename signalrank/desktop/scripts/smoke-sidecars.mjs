import { spawn, spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { existsSync, mkdtempSync, readdirSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const desktopDir = resolve(scriptDir, "..");
const executableSuffix = process.platform === "win32" ? ".exe" : "";
const backend = resolve(
  desktopDir,
  "dist",
  "backend",
  `signalrank-backend${executableSuffix}`,
);
const webRoot = resolve(desktopDir, "dist", "web");

function findServer(directory) {
  const direct = resolve(directory, "server.js");
  if (existsSync(direct)) return direct;
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const path = resolve(directory, entry.name);
    if (entry.isDirectory()) {
      const nested = findServer(path);
      if (nested) return nested;
    }
  }
  return null;
}

function freePort() {
  return new Promise((resolvePort, reject) => {
    const server = createServer();
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      const port = typeof address === "object" && address ? address.port : 0;
      server.close(() => resolvePort(port));
    });
  });
}

if (!existsSync(backend)) throw new Error(`Missing backend sidecar: ${backend}`);
const serverJs = findServer(webRoot);
if (!serverJs) throw new Error(`Missing standalone server.js under ${webRoot}`);

const [backendPort, webPort] = await Promise.all([freePort(), freePort()]);
const dataDir = mkdtempSync(resolve(tmpdir(), "signalrank-sidecar-smoke-"));
const bootstrapToken = randomBytes(32).toString("base64url");
const authSecret = randomBytes(32).toString("base64url");
const backendUrl = `http://127.0.0.1:${backendPort}`;
const webUrl = `http://127.0.0.1:${webPort}`;
const children = [];
let stopping = false;

function launch(name, command, args, env) {
  const child = spawn(command, args, {
    detached: process.platform !== "win32",
    env,
    stdio: ["ignore", "pipe", "pipe"],
  });
  child.stdout.pipe(process.stdout);
  child.stderr.pipe(process.stderr);
  child.on("error", (error) => {
    console.error(`${name}-spawn-error`, error);
  });
  child.on("exit", (code, signal) => {
    if (!stopping) console.error(`${name}-exited code=${code} signal=${signal}`);
  });
  children.push(child);
}

function stop(child, force = false) {
  if (!child.pid) return;
  try {
    if (process.platform === "win32") {
      spawnSync(
        "taskkill",
        ["/PID", String(child.pid), "/T", ...(force ? ["/F"] : [])],
        { stdio: "ignore" },
      );
    } else {
      process.kill(-child.pid, force ? "SIGKILL" : "SIGTERM");
    }
  } catch {
  }
}

const common = {
  ...process.env,
  SIGNALRANK_MODE: "desktop",
  SIGNALRANK_APP_DATA_DIR: dataDir,
  SIGNALRANK_DESKTOP_AUTH_SECRET: authSecret,
  SIGNALRANK_DESKTOP_BOOTSTRAP_TOKEN: bootstrapToken,
};
if (process.platform === "darwin") {
  common.PYTHON_KEYRING_BACKEND = "keyring.backends.macOS.Keyring";
}

console.log(`sidecars-starting backend=${backendUrl} web=${webUrl}`);

launch("backend", backend, [], {
  ...common,
  HOST: "127.0.0.1",
  PORT: String(backendPort),
});
launch("web", process.execPath, [serverJs], {
  ...common,
  AUTH_SECRET: authSecret,
  AUTH_URL: webUrl,
  BACKEND_URL: backendUrl,
  HOSTNAME: "127.0.0.1",
  NEXTAUTH_SECRET: authSecret,
  NEXTAUTH_URL: webUrl,
  NEXT_PUBLIC_SIGNALRANK_MODE: "desktop",
  PORT: String(webPort),
});

async function waitFor(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return response;
    } catch {
    }
    await new Promise((resolveTimer) => setTimeout(resolveTimer, 300));
  }
  throw new Error(`Timed out waiting for ${url}`);
}

try {
  await waitFor(`${backendUrl}/health`, 90_000);
  await waitFor(webUrl, 60_000);
  console.log(`sidecars-ready backend=${backendUrl} web=${webUrl}`);
} finally {
  stopping = true;
  for (const child of children) stop(child);
  await new Promise((resolveTimer) => setTimeout(resolveTimer, 1000));
  for (const child of children) stop(child, true);
}
