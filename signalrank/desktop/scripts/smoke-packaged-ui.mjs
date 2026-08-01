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

const appDataDir = mkdtempSync(resolve(tmpdir(), "signalrank-packaged-ui-smoke-"));
const {
  SIGNALRANK_SMOKE_EXIT_AFTER_READY: _ignoredExit,
  ...environment
} = process.env;
const child = spawn(binary, {
  env: {
    ...environment,
    SIGNALRANK_APP_DATA_DIR: appDataDir,
    SIGNALRANK_NATIVE_UI_SMOKE: "1",
    SIGNALRANK_SMOKE_EXIT_AFTER_READY: "120",
  },
  stdio: ["ignore", "pipe", "pipe"],
});

let output = "";
function collect(chunk) {
  const text = chunk.toString();
  output += text;
  process.stdout.write(text);
}
child.stdout.on("data", collect);
child.stderr.on("data", collect);

const exit = new Promise((resolveExit, reject) => {
  child.once("error", reject);
  child.once("exit", (code, signal) => resolveExit({ code, signal }));
});

try {
  const result = await Promise.race([
    exit,
    new Promise((_, reject) =>
      setTimeout(() => reject(new Error("Native packaged UI smoke timed out")), 120_000),
    ),
  ]);
  if (result.code !== 0) {
    throw new Error(`Native packaged UI smoke exited with ${result.code ?? result.signal}`);
  }
  if (!output.includes("[native-ui] smoke-result pass=true")) {
    throw new Error("Native packaged UI smoke did not report a passing WebView assertion");
  }
  if (!output.includes("services ready backend=http://127.0.0.1:")) {
    throw new Error("Native packaged UI smoke did not start both sidecars");
  }
  console.log("packaged-webview-ui-smoke-pass");
} catch (error) {
  if (child.exitCode === null) child.kill();
  console.error(output.slice(-5000));
  throw error;
}
