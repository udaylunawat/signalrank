import { execFileSync } from "node:child_process";
import {
  chmodSync,
  copyFileSync,
  existsSync,
  mkdirSync,
  realpathSync,
  rmSync,
} from "node:fs";
import { basename, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const desktopDir = resolve(scriptDir, "..");
const binariesDir = resolve(desktopDir, "src-tauri", "binaries");
const nodeLibsDir = resolve(desktopDir, "src-tauri", "node-libs");
const nodeRuntimeDir = resolve(desktopDir, "src-tauri", "resources", "node");
const isWindows = process.platform === "win32";
const executableSuffix = isWindows ? ".exe" : "";

function fallbackTargetTriple() {
  const architecture = process.arch === "arm64" ? "aarch64" : "x86_64";
  if (process.platform === "darwin") return `${architecture}-apple-darwin`;
  if (process.platform === "win32") return `${architecture}-pc-windows-msvc`;
  if (process.platform === "linux") return `${architecture}-unknown-linux-gnu`;
  throw new Error(`Unsupported platform: ${process.platform}`);
}

function targetTriple() {
  try {
    return execFileSync("rustc", ["--print", "host-tuple"], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return fallbackTargetTriple();
  }
}

function stageBinary(source, name, triple) {
  if (!existsSync(source)) throw new Error(`Missing sidecar source: ${source}`);
  const destination = resolve(
    binariesDir,
    `${name}-${triple}${executableSuffix}`,
  );
  copyFileSync(source, destination);
  if (!isWindows) chmodSync(destination, 0o755);
  console.log(`staged ${name}: ${destination}`);
  return destination;
}

function stageNodeRuntime(source) {
  const destination = resolve(nodeRuntimeDir, `signalrank-web${executableSuffix}`);
  copyFileSync(source, destination);
  if (!isWindows) chmodSync(destination, 0o755);
  console.log(`staged signalrank-web runtime: ${destination}`);
  return destination;
}

function commandOutput(command, args) {
  return execFileSync(command, args, {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
}

function dynamicLibraries(binary) {
  return commandOutput("otool", ["-L", binary])
    .split("\n")
    .slice(1)
    .map((line) => line.trim().split(" ")[0])
    .filter(Boolean)
    .filter(
      (path) =>
        !path.startsWith("/usr/lib/") &&
        !path.startsWith("/System/Library/Frameworks/"),
    );
}

function stageMacNodeLibraries(nodeSidecar) {
  const nodeDirectory = dirname(realpathSync(process.execPath));
  const brewPrefix = (() => {
    try {
      return commandOutput("brew", ["--prefix"]).trim();
    } catch {
      return null;
    }
  })();
  const copied = new Map();
  const queue = [{ binary: nodeSidecar, sourceDirectory: nodeDirectory }];

  for (let index = 0; index < queue.length; index += 1) {
    const current = queue[index];
    for (const dependency of dynamicLibraries(current.binary)) {
      const name = basename(dependency);
      const candidates = dependency.startsWith("/")
        ? [dependency]
        : [
            resolve(current.sourceDirectory, name),
            brewPrefix && resolve(brewPrefix, "lib", name),
            brewPrefix && resolve(brewPrefix, "opt", "node", "lib", name),
          ].filter(Boolean);
      const source = candidates.find((candidate) => existsSync(candidate));
      if (!source) throw new Error(`Unable to resolve Node dependency ${dependency}`);
      if (!copied.has(name)) {
        const destination = resolve(nodeLibsDir, name);
        copyFileSync(source, destination);
        chmodSync(destination, 0o755);
        copied.set(name, destination);
        queue.push({ binary: destination, sourceDirectory: dirname(source) });
      }
    }
  }

  for (const [name, binary] of copied) {
    execFileSync("install_name_tool", ["-id", `@rpath/${name}`, binary]);
    for (const dependency of dynamicLibraries(binary)) {
      execFileSync("install_name_tool", [
        "-change",
        dependency,
        `@loader_path/${basename(dependency)}`,
        binary,
      ]);
    }
    execFileSync("codesign", ["--force", "--sign", "-", binary]);
  }

  for (const dependency of dynamicLibraries(nodeSidecar)) {
    execFileSync("install_name_tool", [
      "-change",
      dependency,
      `@executable_path/../node-libs/${basename(dependency)}`,
      nodeSidecar,
    ]);
  }
  execFileSync("codesign", ["--force", "--sign", "-", nodeSidecar]);
}

mkdirSync(binariesDir, { recursive: true });
rmSync(nodeLibsDir, { force: true, recursive: true });
mkdirSync(nodeLibsDir, { recursive: true });
rmSync(nodeRuntimeDir, { force: true, recursive: true });
mkdirSync(nodeRuntimeDir, { recursive: true });

const triple = targetTriple();
stageBinary(
  resolve(
    desktopDir,
    "dist",
    "backend",
    `signalrank-backend${executableSuffix}`,
  ),
  "signalrank-backend",
  triple,
);
const nodeSidecar = stageNodeRuntime(realpathSync(process.execPath));

if (process.platform === "darwin") stageMacNodeLibraries(nodeSidecar);
