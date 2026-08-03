import { spawn, spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createServer } from "node:net";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const root = resolve(scriptDir, "..", "..");
const backendDir = resolve(root, "backend");
const frontendDir = resolve(root, "frontend");
const appDataDir = resolve(root, ".desktop-data");
const bootstrapToken = randomBytes(32).toString("base64url");

mkdirSync(appDataDir, { recursive: true, mode: 0o700 });

function loadInstallSecret() {
  const path = resolve(appDataDir, "install-secret");
  try {
    const existing = readFileSync(path, "utf8").trim();
    if (existing.length >= 32) return existing;
  } catch (error) {
    if (error?.code !== "ENOENT") throw error;
  }
  const secret = randomBytes(48).toString("base64url");
  writeFileSync(path, secret, { encoding: "utf8", flag: "w", mode: 0o600 });
  return secret;
}

const authSecret = loadInstallSecret();

function freePort() {
  return new Promise((resolvePort, reject) => {
    const server = createServer();
    server.unref();
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      const port = typeof address === "object" && address ? address.port : 0;
      server.close(() => resolvePort(port));
    });
  });
}

const backendPort = await freePort();
const webPort = 3000;
const backendUrl = `http://127.0.0.1:${backendPort}`;
const webUrl = `http://127.0.0.1:${webPort}`;
const shared = {
  ...process.env,
  SIGNALRANK_MODE: "desktop",
  SIGNALRANK_APP_DATA_DIR: appDataDir,
  SIGNALRANK_DESKTOP_BOOTSTRAP_TOKEN: bootstrapToken,
};

const children = [];
let shuttingDown = false;

function start(name, command, args, cwd, env) {
  const child = spawn(command, args, {
    cwd,
    detached: process.platform !== "win32",
    env,
    stdio: ["ignore", "inherit", "inherit"],
  });
  child.on("error", (error) => {
    if (!shuttingDown) {
      console.error(`${name} failed to start: ${error.message}`);
      shutdown(1);
    }
  });
  child.on("exit", (code) => {
    if (!shuttingDown) {
      console.error(`${name} exited unexpectedly with code ${code ?? "unknown"}`);
      shutdown(code || 1);
    }
  });
  children.push(child);
}

function stopTree(child, force = false) {
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
    // The process may already have exited.
  }
}

function shutdown(code = 0) {
  if (shuttingDown) return;
  shuttingDown = true;
  for (const child of children) stopTree(child);
  setTimeout(() => {
    for (const child of children) stopTree(child, true);
    process.exit(code);
  }, 1500).unref();
}

process.once("SIGINT", () => shutdown(0));
process.once("SIGTERM", () => shutdown(0));

start(
  "backend",
  "uv",
  ["run", "python", "-m", "api.desktop_main"],
  backendDir,
  {
    ...shared,
    HOST: "127.0.0.1",
    PORT: String(backendPort),
  },
);

start("web", "npm", ["run", "dev", "--", "--hostname", "127.0.0.1"], frontendDir, {
  ...shared,
  AUTH_SECRET: authSecret,
  AUTH_URL: webUrl,
  BACKEND_URL: backendUrl,
  HOSTNAME: "127.0.0.1",
  NEXTAUTH_SECRET: authSecret,
  NEXTAUTH_URL: webUrl,
  NEXT_PUBLIC_SIGNALRANK_MODE: "desktop",
  PORT: String(webPort),
});
