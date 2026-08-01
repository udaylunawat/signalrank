import { expect, test } from "@playwright/test";
import { finishOnboarding, syntheticResume } from "./support/flow";

test.beforeEach(({}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop-web-chromium", "Desktop-web tests run in the desktop project");
});

test.beforeEach(async ({ page }, testInfo) => {
  if (testInfo.project.name === "desktop-web-chromium") {
    await page.request.post("http://127.0.0.1:8112/__fixture__/reset");
  }
});

test("DESK-01 local setup creates a session without SaaS signup", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Connect your OpenRouter key" })).toBeVisible();
  await page.getByLabel("OpenRouter API key").fill("fixture-provider-key");
  await page.getByRole("button", { name: "Validate and save" }).click();
  await expect(page.getByRole("heading", { name: "Add your resume" })).toBeVisible();
  await page.locator('input[type="file"]').setInputFiles(syntheticResume);
  await page.getByRole("button", { name: "Upload and review" }).click();
  await expect(page).toHaveURL(/\/onboarding$/);
  await finishOnboarding(page);
  await expect(page.getByText("Local workspace")).toBeVisible();
  await expect(page.getByText("Senior Product Engineer")).toBeVisible();
});

test("DESK-02 invalid provider key remains recoverable", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("OpenRouter API key").fill("invalid");
  await page.getByRole("button", { name: "Validate and save" }).click();
  await expect(page.locator('[role="alert"]').filter({ hasText: "OpenRouter" })).toContainText(
    "could not be validated",
  );
  await expect(page.getByRole("heading", { name: "Connect your OpenRouter key" })).toBeVisible();
});

test("DESK-03 provider key replacement, removal, and restore are visible", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("OpenRouter API key").fill("fixture-provider-key");
  await page.getByRole("button", { name: "Validate and save" }).click();
  await page.locator('input[type="file"]').setInputFiles(syntheticResume);
  await page.getByRole("button", { name: "Upload and review" }).click();
  await finishOnboarding(page);
  await page.getByRole("link", { name: "Settings" }).click();
  await expect(page.getByText("Configured", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Remove saved key" }).click();
  await expect(page.getByText("Not configured", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Use saved key" }).click();
  await expect(page.getByText("Configured", { exact: true })).toBeVisible();
});
