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

const tlsBinaryName =
  process.platform === "darwin"
    ? process.arch === "arm64"
      ? "tls-client-arm64.dylib"
      : "tls-client-x86.dylib"
    : process.platform === "win32"
      ? "tls-client-64.dll"
      : process.arch === "arm64"
        ? "tls-client-arm64.so"
        : "tls-client-amd64.so";
const locateTlsBinary = spawnSync(
  "uv",
  [
    "run",
    "python",
    "-c",
    "import pathlib, sys, tls_client; print(pathlib.Path(tls_client.__file__).parent / 'dependencies' / sys.argv[1])",
    tlsBinaryName,
  ],
  { cwd: backendDir, encoding: "utf8" },
);
const tlsBinary = locateTlsBinary.stdout?.trim();
if (locateTlsBinary.status || !tlsBinary || !existsSync(tlsBinary)) {
  console.error(`Unable to locate the native tls-client library: ${tlsBinaryName}`);
  process.exit(locateTlsBinary.status ?? 1);
}

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
  "--hidden-import",
  "aiosqlite",
  "--hidden-import",
  "api.main",
  "--hidden-import",
  "keyring",
  "--hidden-import",
  "passlib.handlers.bcrypt",
  "--add-binary",
  `${tlsBinary}${delimiter}tls_client/dependencies`,
  "--exclude-module",
  "PIL",
  "--exclude-module",
  "pytest",
  "--exclude-module",
  "_pytest",
  "--add-data",
  `${resolve(backendDir, "config")}${delimiter}config`,
];

if (process.platform === "darwin") {
  args.push("--hidden-import", "keyring.backends.macOS");
  args.push(
    "--exclude-module",
    "keyring.backends.Windows",
    "--exclude-module",
    "keyring.backends.SecretService",
  );
} else if (process.platform === "win32") {
  args.push("--hidden-import", "keyring.backends.Windows");
  args.push(
    "--exclude-module",
    "keyring.backends.macOS",
    "--exclude-module",
    "keyring.backends.SecretService",
  );
} else {
  args.push("--hidden-import", "keyring.backends.SecretService");
  args.push(
    "--exclude-module",
    "keyring.backends.macOS",
    "--exclude-module",
    "keyring.backends.Windows",
  );
}

const signingIdentity = process.env.APPLE_SIGNING_IDENTITY?.trim();
if (
  process.platform === "darwin" &&
  signingIdentity &&
  signingIdentity !== "-"
) {
  args.push("--codesign-identity", signingIdentity);
}

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
