import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const frontendDir = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
const mode = process.argv[2] === "desktop" ? "desktop" : "saas";
const args = [resolve(frontendDir, "node_modules/@playwright/test/cli.js"), "test", ...process.argv.slice(3)];
const child = spawn(process.execPath, args, {
  cwd: frontendDir,
  env: {
    ...process.env,
    E2E_MODE: mode,
    ...(process.argv[2] === "cross-browser" ? { E2E_CROSS_BROWSER: "1" } : {}),
  },
  stdio: "inherit",
});

child.once("exit", (code, signal) => {
  if (signal) process.kill(process.pid, signal);
  else process.exit(code ?? 1);
});
