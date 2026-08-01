import { appendFile, mkdir, writeFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import os from "node:os";
import { resolve } from "node:path";
import { CASE_IDS } from "./case-catalog.mjs";

function commitName() {
  try {
    return execFileSync("git", ["rev-parse", "--short", "HEAD"], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return process.env.GITHUB_SHA?.slice(0, 8) ?? "unknown-commit";
  }
}

function artifactDirectory() {
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  return resolve(process.cwd(), "../artifacts/e2e", `${stamp}-${commitName()}`);
}

function caseIds(title) {
  return [...title.matchAll(/\b(?:AUTH|ONB|RUN|DISC|RANK|MATCH|TRACK|SET|TAILOR|DESK|NATIVE|REL|A11Y|SEC)-\d{2}\b/g)].map(
    (match) => match[0],
  );
}

function observedStatus(result) {
  if (result.status === "passed") return "Pass";
  if (result.status === "skipped" || result.status === "interrupted") return "Blocked";
  return "Fail";
}

function statusPriority(status) {
  return { Blocked: 1, Pass: 2, Fail: 3 }[status] ?? 0;
}

function attachmentPaths(test) {
  return test.attachments
    .map((attachment) => attachment.path)
    .filter((path) => typeof path === "string");
}

function browserLabel(project) {
  if (project.includes("firefox")) return "Firefox";
  if (project.includes("webkit")) return "WebKit";
  if (project.includes("mobile")) return "Chromium / 390x844";
  if (project.includes("tablet")) return "Chromium / 768x1024";
  return "Chromium";
}

export default class ObservationReporter {
  async onBegin(config) {
    this.directory = artifactDirectory();
    this.observationsPath = resolve(this.directory, "observations.jsonl");
    this.logPath = resolve(this.directory, "observation-log.md");
    this.caseStatuses = new Map(
      CASE_IDS.map((caseId) => [caseId, { status: "Blocked", evidence: [] }]),
    );
    await mkdir(this.directory, { recursive: true });
    await writeFile(
      resolve(this.directory, "metadata.json"),
      `${JSON.stringify(
        {
          commit: commitName(),
          started_at: new Date().toISOString(),
          projects: config.projects.map((project) => project.name),
          artifact_policy: "synthetic fixtures only; scan before publishing",
        },
        null,
        2,
      )}\n`,
    );
    await writeFile(
      resolve(this.directory, "environment.json"),
      `${JSON.stringify(
        {
          platform: process.platform,
          architecture: process.arch,
          node: process.version,
          os_release: os.release(),
          ci: Boolean(process.env.CI),
        },
        null,
        2,
      )}\n`,
    );
    await writeFile(
      this.logPath,
      "# SignalRank E2E observation log\n\n| Case ID | Surface | Browser/WebView | Status | Evidence |\n| --- | --- | --- | --- | --- |\n",
    );
  }

  async onTestEnd(test, result) {
    const ids = caseIds(test.titlePath().join(" "));
    if (!ids.length) return;
    const evidence = attachmentPaths(result);
    const status = observedStatus(result);
    for (const id of ids) {
      const current = this.caseStatuses.get(id);
      if (!current || statusPriority(status) > statusPriority(current.status)) {
        this.caseStatuses.set(id, {
          status,
          evidence: [...(current?.evidence ?? []), ...evidence],
        });
      }
    }
    const project = test.parent.project()?.name ?? "unknown";
    const record = {
      case_id: ids,
      surface: project.startsWith("desktop") ? "desktop-configured-web" : "saas-web",
      browser_or_webview: browserLabel(project),
      viewport: test.parent.project()?.use?.viewport ?? null,
      os: process.platform,
      architecture: process.arch,
      commit: commitName(),
      fixture: "synthetic-resume.txt + local fixture backend",
      expected_result: "The assertions in the case pass without external provider access.",
      observed_result: observedStatus(result),
      evidence,
      severity: result.status === "failed" ? "P1" : "none",
      reproduction: result.status === "failed" ? test.titlePath().join(" > ") : null,
      owner: "SignalRank QA",
      retest_status: result.status === "failed" ? "required" : "not-required",
      duration_ms: result.duration,
    };
    await appendFile(this.observationsPath, `${JSON.stringify(record)}\n`);
    const evidenceText = evidence.length ? evidence.join("; ") : "none";
    for (const id of ids) {
      await appendFile(
        this.logPath,
        `| ${id} | ${record.surface} | ${record.browser_or_webview} | ${record.observed_result} | ${evidenceText} |\n`,
      );
    }
  }

  async onEnd() {
    const summary = CASE_IDS.map((caseId) => {
      const current = this.caseStatuses.get(caseId);
      return {
        case_id: caseId,
        status: current?.status ?? "Blocked",
        evidence: [...new Set(current?.evidence ?? [])],
        note:
          current?.status === "Blocked"
            ? "No automated case registered in the executed lane."
            : null,
      };
    });
    await writeFile(
      resolve(this.directory, "case-summary.json"),
      `${JSON.stringify(summary, null, 2)}\n`,
    );
    await appendFile(
      this.logPath,
      `\n## Stable case summary\n\n| Case ID | Status | Evidence | Note |\n| --- | --- | --- | --- |\n${summary
        .map(
          (item) =>
            `| ${item.case_id} | ${item.status} | ${item.evidence.join("; ") || "none"} | ${item.note ?? ""} |`,
        )
        .join("\n")}\n`,
    );
  }

  printsToStdio() {
    return false;
  }
}
