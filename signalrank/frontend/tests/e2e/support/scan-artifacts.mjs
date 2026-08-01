import { existsSync, readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";

const roots = (process.argv.length > 2
  ? process.argv.slice(2)
  : ["test-results", "../artifacts/e2e"]
).map((path) => resolve(process.cwd(), path));
const forbidden = [
  /sk-or(?:-v1)?[-_]/i,
  /authorization\s*:\s*bearer/i,
  /fixture-password/i,
  /resume_sha256/i,
  /@example\.test/i,
];

function files(directory) {
  if (!existsSync(directory)) return [];
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = resolve(directory, entry.name);
    return entry.isDirectory() ? files(path) : [path];
  });
}

const allFiles = roots.flatMap((root) => files(root));
const violations = [];
for (const path of allFiles) {
  const text = readFileSync(path, "utf8");
  for (const pattern of forbidden) {
    if (pattern.test(text)) violations.push(`${path}: ${pattern}`);
  }
}

if (violations.length) {
  process.stderr.write(`Sensitive content found in E2E artifacts:\n${violations.join("\n")}\n`);
  process.exit(1);
}
process.stdout.write(`E2E artifact scan passed: ${allFiles.length} files checked.\n`);
