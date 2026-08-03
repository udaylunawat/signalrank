import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { completeOnboarding, openMatches } from "./support/flow";

test.beforeEach(({}, testInfo) => {
  test.skip(testInfo.project.name === "desktop-web-chromium", "Desktop has a separate journey");
});

test("MATCH-01 filters, sorting, and URL state control ranked results", async ({ page }) => {
  await completeOnboarding(page);
  await openMatches(page);
  await expect(page.getByText("Senior Product Engineer")).toBeVisible();

  await page.getByLabel("Search all matches").fill("Northstar");
  await expect(page).toHaveURL(/q=Northstar/);
  await expect(page.getByText("Senior Product Engineer")).toBeVisible();
  await expect(page.getByText("Backend Engineer")).not.toBeVisible();

  await page.getByLabel("Search all matches").fill("");
  await page.getByRole("button", { name: "80%+" }).click();
  await expect(page.getByText("Senior Product Engineer")).toBeVisible();
  await expect(page.getByText("Data Platform Contractor")).not.toBeVisible();
  await page.getByRole("button", { name: "Compact" }).click();
  await expect(page.getByRole("button", { name: "Compact" })).toHaveAttribute("aria-pressed", "true");
});

test("MATCH-02 explanation, tracking, feedback undo, and CSV export work", async ({ page }) => {
  await completeOnboarding(page);
  await openMatches(page);
  const card = page.locator("article").filter({ hasText: "Senior Product Engineer" }).first();

  await card.getByRole("button", { name: "Why it fits" }).click();
  await expect(card.getByText("Why this role fits")).toBeVisible();
  await expect(card.getByText("Role relevance")).toBeVisible();
  await expect(card.getByText("Possible gaps")).toBeVisible();
  await card.getByRole("button", { name: "Track" }).click();
  await expect(card.getByRole("button", { name: "Saved" })).toBeVisible();
  await card.getByRole("button", { name: "Good match" }).click();
  await expect(card.getByRole("button", { name: "Good match" })).toHaveClass(/bg-primary/);
  await card.getByRole("button", { name: "Not a fit" }).click();
  await card.getByRole("button", { name: "Wrong role" }).click();
  await expect(page.getByText("Feedback saved.")).toBeVisible();
  await page.getByRole("button", { name: "Undo" }).click();
  await expect(page.getByText("Feedback saved.")).not.toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export CSV" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^signalrank-jobs-2026-08-01\.csv$/);
  const csv = await readFile((await download.path())!, "utf8");
  expect(csv).toContain("\ufeffrun_id,run_completed_at,job_id");
  expect(csv).toContain("Senior Product Engineer");
});
