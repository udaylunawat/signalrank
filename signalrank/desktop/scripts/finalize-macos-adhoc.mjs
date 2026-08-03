import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, rmSync } from "node:fs";
import { resolve } from "node:path";

if (process.platform !== "darwin") process.exit(0);

const identity = process.env.APPLE_SIGNING_IDENTITY?.trim();
if (identity && identity !== "-") process.exit(0);

const bundleRoot = resolve("src-tauri", "target", "release", "bundle");
const appDir = resolve(bundleRoot, "macos");
const app = resolve(appDir, "SignalRank.app");
const dmgDir = resolve(bundleRoot, "dmg");
const dmgScript = resolve(dmgDir, "bundle_dmg.sh");

if (!existsSync(app)) throw new Error(`Missing macOS application bundle: ${app}`);
if (!existsSync(dmgScript)) throw new Error(`Missing DMG builder: ${dmgScript}`);

execFileSync("codesign", ["--force", "--deep", "--sign", "-", app], {
  stdio: "inherit",
});
execFileSync("codesign", ["--verify", "--deep", "--strict", "--verbose=2", app], {
  stdio: "inherit",
});

const tauriConfig = JSON.parse(
  readFileSync(resolve("src-tauri", "tauri.conf.json"), "utf8"),
);
const architecture = process.arch === "arm64" ? "aarch64" : "x64";
const dmg = resolve(
  dmgDir,
  `SignalRank_${tauriConfig.version}_${architecture}.dmg`,
);
rmSync(dmg, { force: true });

execFileSync(
  "bash",
  [
    dmgScript,
    "--volname",
    "SignalRank",
    "--volicon",
    resolve("src-tauri", "icons", "icon.icns"),
    "--window-size",
    "600",
    "400",
    "--icon-size",
    "128",
    "--icon",
    "SignalRank.app",
    "160",
    "190",
    "--hide-extension",
    "SignalRank.app",
    "--app-drop-link",
    "440",
    "190",
    dmg,
    appDir,
  ],
  { stdio: "inherit" },
);

console.log(`ad-hoc macOS bundle finalized: ${dmg}`);
