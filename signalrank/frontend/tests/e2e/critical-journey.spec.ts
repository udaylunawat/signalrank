import { expect, test } from "@playwright/test";
import { completeOnboarding } from "./support/flow";

test.beforeEach(({}, testInfo) => {
  test.skip(testInfo.project.name === "desktop-web-chromium", "Desktop has a separate setup journey");
});

test("ONB-01 RUN-01 complete onboarding starts a ranked search", async ({ page }) => {
  await completeOnboarding(page);
  await expect(page.getByText("Search is fresh")).toBeVisible();
  await expect(page.getByText("Source coverage")).toBeVisible();
  await expect(page.getByText("Senior Product Engineer")).toBeVisible();
  await expect(page.getByText("91")).toBeVisible();
});

test("ONB-02 draft state survives a reload before completion", async ({ page }) => {
  await page.goto("/signup");
  await page.getByLabel("Email address").fill(`draft-${Date.now()}@example.test`);
  await page.getByLabel("Password").fill("fixture-password");
  await page.getByRole("button", { name: "Create account" }).click();
  await page.getByLabel("resume").setInputFiles("tests/fixtures/synthetic-resume.txt");
  await page.getByRole("button", { name: "Build my profile" }).click();
  await expect(page.getByRole("heading", { name: "Confirm what you want next." })).toBeVisible();
  await page.getByPlaceholder("Type any role title").fill("Platform Engineer");
  await page.getByRole("button", { name: "Add", exact: true }).click();
  await page.reload();
  await expect(page.getByText("Platform Engineer")).toBeVisible();
});
