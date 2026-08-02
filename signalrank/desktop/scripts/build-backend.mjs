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

function runUvPython(args) {
  const result = spawnSync("uv", ["run", "python", ...args], {
    cwd: backendDir,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "inherit"],
  });
  if (result.error) {
    console.error(`Unable to run Python probe: ${result.error.message}`);
    process.exit(1);
  }
  if (result.status !== 0) {
    console.error(`Python probe exited with status ${result.status}`);
    process.exit(result.status ?? 1);
  }
  return result.stdout.trim();
}

const tlsClientLibraryName = runUvPython([
  "-c",
  [
    "import ctypes",
    "from platform import machine",
    "from sys import platform",
    "machine_name = machine()",
    "name = ('-arm64.dylib' if platform == 'darwin' and machine_name == 'arm64' else '-x86.dylib' if platform == 'darwin' else '-64.dll' if platform in ('win32', 'cygwin') and ctypes.sizeof(ctypes.c_voidp) == 8 else '-32.dll' if platform in ('win32', 'cygwin') else '-arm64.so' if machine_name == 'aarch64' else '-x86.so' if 'x86' in machine_name else '-amd64.so')",
    "print('tls-client' + name)",
  ].join("; "),
]);

if (!tlsClientLibraryName) {
  console.error("Unable to determine the platform TLS client library");
  process.exit(1);
}

const tlsClientLibrary = runUvPython([
  "-c",
  "import pathlib, tls_client; import sys; print(pathlib.Path(tls_client.__file__).parent / 'dependencies' / sys.argv[1])",
  tlsClientLibraryName,
]);

if (!existsSync(tlsClientLibrary)) {
  console.error(`Missing platform TLS client library: ${tlsClientLibrary}`);
  process.exit(1);
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
  "api.main",
  "--hidden-import",
  "aiosqlite",
  "--hidden-import",
  "keyring",
  "--hidden-import",
  "keyring.backends.macOS",
  "--hidden-import",
  "passlib.handlers.bcrypt",
  "--hidden-import",
  "tls_client",
  "--hidden-import",
  "uvicorn.logging",
  "--hidden-import",
  "uvicorn.loops.auto",
  "--hidden-import",
  "uvicorn.protocols.http.auto",
  "--hidden-import",
  "uvicorn.protocols.websockets.auto",
  "--hidden-import",
  "uvicorn.lifespan.on",
  "--collect-submodules",
  "keyring.backends",
  "--add-binary",
  `${tlsClientLibrary}${delimiter}tls_client/dependencies`,
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
