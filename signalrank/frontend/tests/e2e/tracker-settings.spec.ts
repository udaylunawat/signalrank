import { expect, test } from "@playwright/test";
import { completeOnboarding, openMatches, signUp } from "./support/flow";

test.beforeEach(({}, testInfo) => {
  test.skip(testInfo.project.name === "desktop-web-chromium", "Desktop has a separate setup journey");
});

test("TRACK-01 saved roles move through the application pipeline and persist", async ({ page }) => {
  await completeOnboarding(page);
  await openMatches(page);
  const card = page.locator("article").filter({ hasText: "Senior Product Engineer" }).first();
  await card.getByRole("button", { name: "Track" }).click();
  await page.getByRole("link", { name: "Tracker" }).click();
  await expect(page.getByRole("heading", { name: "Keep every opportunity moving." })).toBeVisible();
  const status = page.getByLabel("Status for Senior Product Engineer");
  await status.selectOption("applied");
  await page.reload();
  await expect(page.getByLabel("Status for Senior Product Engineer")).toHaveValue("applied");
  await page.getByRole("button", { name: "Remove Senior Product Engineer" }).click();
  await expect(page.getByText("Build your shortlist as you browse")).toBeVisible();
});

test("TRACK-03 tracker has a useful empty state before a role is saved", async ({ page }) => {
  await signUp(page);
  await page.goto("/tracker");
  await expect(page.getByText("Build your shortlist as you browse")).toBeVisible();
});

test("SET-01 preference changes save and reload", async ({ page }) => {
  await completeOnboarding(page);
  await page.getByRole("link", { name: "Settings" }).click();
  await page.getByLabel("Target roles").fill("Platform Engineer, Backend Engineer");
  await page.getByLabel("Preferred locations").fill("Remote, Bengaluru");
  await page.getByLabel("Preferred companies").fill("Northstar Labs");
  await page.getByLabel("Excluded companies").fill("Staffing Agency");
  await page.getByLabel("Excluded job titles").fill("Support Engineer");
  await page.getByRole("button", { name: "Top reputed (AI)" }).click();
  await page.getByRole("button", { name: "Save preferences" }).click();
  await expect(page.getByText("Saved")).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Target roles")).toHaveValue("Platform Engineer, Backend Engineer");
  await expect(page.getByLabel("Preferred locations")).toHaveValue("Remote, Bengaluru");
});
