import { spawn } from "node:child_process";
import { existsSync, mkdtempSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";

function packagedBinary() {
  const release = resolve("src-tauri", "target", "release");
  if (process.platform === "darwin") {
    return resolve(
      release,
      "bundle",
      "macos",
      "SignalRank.app",
      "Contents",
      "MacOS",
      "signalrank-desktop",
    );
  }
  if (process.platform === "win32") {
    return resolve(release, "signalrank-desktop.exe");
  }
  return resolve(release, "signalrank-desktop");
}

const binary = packagedBinary();
if (!existsSync(binary)) throw new Error(`Missing packaged app binary: ${binary}`);

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

async function waitForUrl(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url, {
        signal: AbortSignal.timeout(2000),
      });
      if (response.ok) return response;
    } catch {
    }
    await new Promise((resolveTimer) => setTimeout(resolveTimer, 300));
  }
  throw new Error(`Timed out waiting for ${url}`);
}

async function smokeSignedBackend() {
  const backend = resolve(
    dirname(binary),
    `signalrank-backend${process.platform === "win32" ? ".exe" : ""}`,
  );
  if (!existsSync(backend)) throw new Error(`Missing packaged backend: ${backend}`);
  const port = await freePort();
  const dataDir = mkdtempSync(resolve(tmpdir(), "signalrank-backend-signing-smoke-"));
  const child = spawn(backend, {
    env: {
      ...process.env,
      HOST: "127.0.0.1",
      PORT: String(port),
      SIGNALRANK_MODE: "desktop",
      SIGNALRANK_APP_DATA_DIR: dataDir,
      SIGNALRANK_DESKTOP_BOOTSTRAP_TOKEN:
        "signalrank-packaged-signing-smoke-token-0001",
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  let output = "";
  child.stdout.on("data", (chunk) => {
    output += chunk.toString();
  });
  child.stderr.on("data", (chunk) => {
    output += chunk.toString();
  });
  const exited = new Promise((_, reject) => {
    child.once("exit", (code) => {
      reject(
        new Error(
          `Packaged backend exited before health check with code ${code}\n${output.slice(-5000)}`,
        ),
      );
    });
  });
  try {
    await Promise.race([
      waitForUrl(`http://127.0.0.1:${port}/health`, 120_000),
      exited,
    ]);
    console.log("packaged-backend-signing-ready");
  } finally {
    if (child.exitCode === null) child.kill("SIGTERM");
  }
}

await smokeSignedBackend();

const appDataDir = mkdtempSync(resolve(tmpdir(), "signalrank-packaged-smoke-"));
const child = spawn(binary, {
  env: {
    ...process.env,
    SIGNALRANK_APP_DATA_DIR: appDataDir,
    SIGNALRANK_SMOKE_EXIT_AFTER_READY:
      process.env.SIGNALRANK_SMOKE_EXIT_AFTER_READY ?? "10",
  },
  stdio: ["ignore", "pipe", "pipe"],
});

const childExit = new Promise((resolveExit, reject) => {
  child.once("exit", (code) => {
    if (code === 0) resolveExit();
    else reject(new Error(`Packaged app exited with code ${code}`));
  });
});

let output = "";
let backendUrl = "";
let webUrl = "";

function collect(chunk) {
  const text = chunk.toString();
  output += text;
  process.stdout.write(text);
  const match = text.match(
    /services ready backend=(http:\/\/127\.0\.0\.1:\d+) web=(http:\/\/127\.0\.0\.1:\d+)/,
  );
  if (match) {
    backendUrl = match[1];
    webUrl = match[2];
  }
}

child.stdout.on("data", collect);
child.stderr.on("data", collect);

async function waitForServices() {
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    if (backendUrl && webUrl) {
      try {
        const [backend, web] = await Promise.all([
          fetch(`${backendUrl}/health`, { signal: AbortSignal.timeout(2000) }),
          fetch(`${webUrl}/desktop-setup`, { signal: AbortSignal.timeout(2000) }),
        ]);
        if (backend.ok && web.ok) return;
      } catch {
      }
    }
    await new Promise((resolveTimer) => setTimeout(resolveTimer, 300));
  }
  throw new Error("Packaged services did not become healthy");
}

function waitForExit(timeoutMs) {
  return Promise.race([
    childExit,
    new Promise((_, reject) => {
      setTimeout(() => reject(new Error("Packaged app did not exit")), timeoutMs);
    }),
  ]);
}

async function assertStopped(url) {
  const deadline = Date.now() + 5000;
  while (Date.now() < deadline) {
    try {
      await fetch(url);
    } catch {
      return;
    }
    await new Promise((resolveTimer) => setTimeout(resolveTimer, 200));
  }
  throw new Error(`Local service remained reachable after app exit: ${url}`);
}

try {
  await Promise.race([
    waitForServices(),
    childExit.then(() => {
      throw new Error("Packaged app exited before its services became ready");
    }),
  ]);
  console.log(`packaged-services-ready backend=${backendUrl} web=${webUrl}`);
  await waitForExit(20_000);
  if (output.includes("[auth][error]")) {
    throw new Error("Packaged app emitted an Auth.js session error");
  }
  await Promise.all([assertStopped(backendUrl), assertStopped(webUrl)]);
  console.log("packaged-shutdown-clean");
} catch (error) {
  if (child.exitCode === null) child.kill();
  console.error(output.slice(-5000));
  throw error;
}
