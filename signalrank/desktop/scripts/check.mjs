import { spawnSync } from "node:child_process";
import { mkdirSync, readdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const desktopDir = resolve(scriptDir, "..");
mkdirSync(resolve(desktopDir, "src-tauri", "node-libs"), { recursive: true });
mkdirSync(resolve(desktopDir, "dist", "web"), { recursive: true });

for (const file of readdirSync(scriptDir).filter((name) => name.endsWith(".mjs"))) {
  const result = spawnSync(process.execPath, ["--check", resolve(scriptDir, file)], {
    stdio: "inherit",
  });
  if (result.status) process.exit(result.status);
}

const cargo = spawnSync(
  "cargo",
  ["check", "--manifest-path", resolve(desktopDir, "src-tauri", "Cargo.toml")],
  {
    env: {
      ...process.env,
      TAURI_CONFIG: JSON.stringify({ bundle: { externalBin: [], resources: {} } }),
    },
    stdio: "inherit",
  },
);
if (cargo.error) {
  console.error(`Unable to start cargo: ${cargo.error.message}`);
  process.exit(1);
}
process.exit(cargo.status ?? 1);
