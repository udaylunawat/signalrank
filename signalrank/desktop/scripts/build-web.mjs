import { spawnSync } from "node:child_process";
import {
  cpSync,
  existsSync,
  mkdirSync,
  readdirSync,
  rmSync,
} from "node:fs";
import { dirname, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const desktopDir = resolve(scriptDir, "..");
const frontendDir = resolve(desktopDir, "..", "frontend");
const standaloneDir = resolve(frontendDir, ".next", "standalone");
const outputDir = resolve(desktopDir, "dist", "web");

// Next.js 16 defaults to Turbopack, which does not emit the standalone server
// bundle required by the Tauri sidecar. Keep the desktop bundle on webpack.
const npm = process.platform === "win32" ? "npm.cmd" : "npm";
const result = spawnSync(npm, ["run", "build", "--", "--webpack"], {
  cwd: frontendDir,
  env: {
    ...process.env,
    SIGNALRANK_MODE: "desktop",
    NEXT_PUBLIC_SIGNALRANK_MODE: "desktop",
  },
  shell: process.platform === "win32",
  stdio: "inherit",
});

if (result.error) {
  console.error(`Unable to start ${npm}: ${result.error.message}`);
  process.exit(1);
}
if (result.status) process.exit(result.status);
if (!existsSync(standaloneDir)) {
  throw new Error(
    "Next.js did not produce .next/standalone. Enable output: 'standalone' for desktop builds.",
  );
}

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

rmSync(outputDir, { force: true, recursive: true });
mkdirSync(outputDir, { recursive: true });
cpSync(standaloneDir, outputDir, { recursive: true });

const serverSource = findServer(standaloneDir);
if (!serverSource) throw new Error("Could not find standalone Next.js server.js");
const serverDir = resolve(outputDir, dirname(relative(standaloneDir, serverSource)));

const staticSource = resolve(frontendDir, ".next", "static");
if (existsSync(staticSource)) {
  const staticTarget = resolve(serverDir, ".next", "static");
  mkdirSync(dirname(staticTarget), { recursive: true });
  cpSync(staticSource, staticTarget, { recursive: true });
}

const publicSource = resolve(frontendDir, "public");
if (existsSync(publicSource)) {
  cpSync(publicSource, resolve(serverDir, "public"), { recursive: true });
}

console.log(`standalone web staged at ${outputDir}`);
