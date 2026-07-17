import { spawn } from "node:child_process";
import { existsSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";

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
          fetch(`${backendUrl}/health`),
          fetch(`${webUrl}/desktop-setup`),
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
  await waitForServices();
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
