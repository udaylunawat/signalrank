import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import { delimiter, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const desktopDir = resolve(scriptDir, "..");
const backendDir = resolve(scriptDir, "..", "..", "backend");
const entrypoint = resolve(backendDir, "api", "desktop_main.py");
const modelDir = resolve(
  desktopDir,
  "dist",
  "models",
  "all-MiniLM-L6-v2",
);
mkdirSync(resolve(desktopDir, "dist", "pyinstaller"), { recursive: true });

if (!existsSync(resolve(modelDir, "config.json"))) {
  mkdirSync(modelDir, { recursive: true });
  const prepareModel = spawnSync(
    "uv",
    [
      "run",
      "python",
      "-c",
      [
        "import sys",
        "from sentence_transformers import SentenceTransformer",
        "model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')",
        "model.save_pretrained(sys.argv[1])",
      ].join("; "),
      modelDir,
    ],
    {
      cwd: backendDir,
      env: { ...process.env, HF_HUB_DISABLE_TELEMETRY: "1" },
      stdio: "inherit",
    },
  );
  if (prepareModel.error) {
    console.error(`Unable to prepare embedding model: ${prepareModel.error.message}`);
    process.exit(1);
  }
  if (prepareModel.status) process.exit(prepareModel.status);
}

const args = [
  "run",
  "--with",
  "pyinstaller>=6.11",
  "pyinstaller",
  "--clean",
  "--noconfirm",
  "--onefile",
  "--name",
  "signalrank-backend",
  "--specpath",
  resolve(desktopDir, "dist", "pyinstaller"),
  "--workpath",
  resolve(desktopDir, "dist", "pyinstaller", "build"),
  "--distpath",
  resolve(desktopDir, "dist", "backend"),
  "--collect-submodules",
  "api",
  "--collect-submodules",
  "batch",
  "--collect-submodules",
  "domain",
  "--collect-submodules",
  "llm",
  "--hidden-import",
  "aiosqlite",
  "--hidden-import",
  "keyring",
  "--collect-submodules",
  "passlib",
  "--collect-submodules",
  "keyring.backends",
  "--collect-data",
  "tls_client",
  "--add-data",
  `${resolve(backendDir, "config")}${delimiter}config`,
  "--add-data",
  `${resolve(backendDir, "templates")}${delimiter}templates`,
  "--add-data",
  `${modelDir}${delimiter}models/all-MiniLM-L6-v2`,
];

if (process.platform !== "win32") args.push("--strip");
args.push(entrypoint);

const result = spawnSync("uv", args, {
  cwd: backendDir,
  env: {
    ...process.env,
    SIGNALRANK_MODE: "desktop",
  },
  stdio: "inherit",
});

if (result.error) {
  console.error(`Unable to start uv: ${result.error.message}`);
  process.exit(1);
}
process.exit(result.status ?? 1);
