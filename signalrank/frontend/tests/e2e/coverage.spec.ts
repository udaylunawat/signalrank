import { expect, test } from "@playwright/test";
import {
  completeOnboarding,
  openMatches,
  signUp,
  syntheticResumeFiles,
  uniqueEmail,
} from "./support/flow";

test.beforeEach(({}, testInfo) => {
  test.skip(testInfo.project.name === "desktop-web-chromium", "SaaS coverage runs in SaaS projects");
});

test.afterEach(async ({ page }, testInfo) => {
  if (testInfo.project.name === "saas-chromium") {
    await page.request.post("http://127.0.0.1:8111/__fixture__/reset");
  }
});

test("AUTH-05 session survives reload and sign-out returns to login", async ({ page }) => {
  test.skip(test.info().project.name !== "saas-chromium", "Sign-out control is covered in the desktop SaaS layout");
  await completeOnboarding(page);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Focus on the roles that fit." })).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login/);
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login\?callbackUrl=/);
});

test("SEC-01 accounts cannot see another account's matches", async ({ page }) => {
  test.skip(test.info().project.name !== "saas-chromium", "Account isolation uses the authenticated desktop layout");
  await completeOnboarding(page);
  await expect(page.getByText("Senior Product Engineer")).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login/);
  await signUp(page, uniqueEmail());
  await page.goto("/jobs");
  await expect(page.getByRole("heading", { name: "Your matches" })).toBeVisible();
  await expect(page.getByText("Senior Product Engineer")).not.toBeVisible();
  await expect(page.getByText("No matches in this view")).toBeVisible();
});

test("ONB-03 TXT, PDF, and DOCX synthetic resumes reach extraction", async ({ page }) => {
  for (const file of Object.values(syntheticResumeFiles)) {
    await signUp(page, uniqueEmail());
    await page.getByLabel("resume").setInputFiles(file);
    await page.getByRole("button", { name: "Build my profile" }).click();
    await expect(page.getByRole("heading", { name: "Confirm what you want next." })).toBeVisible();
  }
});

test("ONB-04 unsupported resume type is rejected", async ({ page }) => {
  await signUp(page);
  await page.getByLabel("resume").setInputFiles({
    name: "resume.exe",
    mimeType: "application/octet-stream",
    buffer: Buffer.from("not a resume"),
  });
  await page.getByRole("button", { name: "Build my profile" }).click();
  await expect(page.locator("p[role=alert]")).toContainText("Supported formats");
});

test("ONB-05 over-10-MB resume is blocked before upload", async ({ page }) => {
  await signUp(page);
  await page.getByLabel("resume").setInputFiles({
    name: "large-resume.txt",
    mimeType: "text/plain",
    buffer: Buffer.alloc(10 * 1024 * 1024 + 1, "x"),
  });
  await expect(page.locator("p[role=alert]")).toContainText("larger than 10 MB");
  await expect(page.getByRole("button", { name: "Build my profile" })).toBeDisabled();
});

test("ONB-06 degraded parsing exposes retry and recovers", async ({ page }) => {
  await signUp(page);
  await page.getByLabel("resume").setInputFiles({
    name: "degraded.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("Synthetic resume fixture without extracted signals."),
  });
  await page.getByRole("button", { name: "Build my profile" }).click();
  await expect(page.getByRole("button", { name: "Retry with OpenRouter" })).toBeVisible();
  await page.getByRole("button", { name: "Retry with OpenRouter" }).click();
  await expect(page.getByText("Extracted profile")).toBeVisible();
});

test("ONB-07 empty extraction is rejected without entering onboarding", async ({ page }) => {
  await signUp(page);
  await page.getByLabel("resume").setInputFiles({
    name: "empty.txt",
    mimeType: "text/plain",
    buffer: Buffer.from(""),
  });
  await page.getByRole("button", { name: "Build my profile" }).click();
  await expect(page.locator("p[role=alert]")).toContainText("Could not extract text");
  await expect(page).toHaveURL(/\/onboarding$/);
  await expect(page.getByRole("heading", { name: /Your resume becomes the signal/ })).toBeVisible();
});

test("DISC-01 dashboard reports source coverage and strong matches", async ({ page }) => {
  await completeOnboarding(page);
  await expect(page.getByText("Strong matches")).toBeVisible();
  await expect(page.getByText("Source coverage")).toBeVisible();
  for (const source of ["remotive", "indeed", "linkedin", "himalayas", "jobicy"]) {
    await expect(page.getByText(source, { exact: true })).toBeVisible();
  }
});

test("RUN-02 partial source coverage retains available matches", async ({ page }) => {
  await page.request.post("http://127.0.0.1:8111/__fixture__/scenario", {
    data: { name: "partial" },
  });
  await completeOnboarding(page);
  await expect(page.getByText("Partial coverage")).toBeVisible();
  await expect(page.getByText("Some sources could not be refreshed.")).toBeVisible();
  await expect(page.getByText("Senior Product Engineer")).toBeVisible();
  await expect(page.getByText("Degraded", { exact: true })).toBeVisible();
});

test("RUN-03 total source failure renders a recoverable dashboard state", async ({ page }) => {
  await page.request.post("http://127.0.0.1:8111/__fixture__/scenario", {
    data: { name: "failed" },
  });
  await completeOnboarding(page);
  await expect(page.getByText("Search failed")).toBeVisible();
  await expect(page.getByText("Fixture provider unavailable", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Refresh matches" })).toBeEnabled();
});

test("RUN-04 a new account has an explicit empty dashboard state", async ({ page }) => {
  await signUp(page);
  await page.goto("/dashboard");
  await expect(page.getByText("Your first shortlist starts here")).toBeVisible();
  await expect(page.getByRole("button", { name: "Add your resume" })).toBeVisible();
  await expect(page.getByText("Not started")).toBeVisible();
});

test("MATCH-03 source, score, newest, and empty-state filters are URL-backed", async ({ page }) => {
  await completeOnboarding(page);
  await openMatches(page);
  await page.getByRole("button", { name: "65%+" }).click();
  await expect(page).toHaveURL(/min_score=65/);
  await page.getByLabel("Source").selectOption("indeed");
  await expect(page).toHaveURL(/source=indeed/);
  await expect(page.getByText("Backend Engineer")).toBeVisible();
  await expect(page.getByText("Senior Product Engineer")).not.toBeVisible();
  await page.getByLabel("Search all matches").fill("does-not-exist");
  await expect(page.getByText("No matches in this view")).toBeVisible();
  await page.getByRole("button", { name: "Clear filters" }).click();
  await expect(page.getByText("Senior Product Engineer")).toBeVisible();
});

test("MATCH-04 secure external links open the backed job URL", async ({ page }) => {
  await page.addInitScript(() => {
    window.open = (url) => {
      (window as Window & { __openedUrl?: string }).__openedUrl = String(url);
      return null;
    };
  });
  await completeOnboarding(page);
  await openMatches(page);
  const card = page.locator("article").filter({ hasText: "Senior Product Engineer" }).first();
  await card.getByRole("button", { name: "View role" }).click();
  await expect.poll(() => page.evaluate(() => (window as Window & { __openedUrl?: string }).__openedUrl)).toBe(
    "https://jobs.example.test/northstar-product-engineer",
  );
});

test("TRACK-02 tracker supports every application status and persistence", async ({ page }) => {
  await completeOnboarding(page);
  await openMatches(page);
  for (const title of ["Senior Product Engineer", "Backend Engineer", "Data Platform Contractor"]) {
    await page.locator("article").filter({ hasText: title }).getByRole("button", { name: "Track" }).click();
  }
  await page.getByRole("link", { name: "Tracker" }).click();
  const status = page.getByLabel("Status for Senior Product Engineer");
  for (const value of ["applied", "phone_screen", "interview", "offer", "interested"]) {
    await status.selectOption(value);
    await expect(status).toHaveValue(value);
  }
  await page.getByLabel("Status for Backend Engineer").selectOption("rejected");
  await page.getByLabel("Status for Data Platform Contractor").selectOption("archived");
  await expect(page.locator("span").filter({ hasText: /^Rejected$/ })).toBeVisible();
  await expect(page.locator("span").filter({ hasText: /^Archived$/ })).toBeVisible();
  await page.reload();
  await expect(status).toHaveValue("interested");
  await expect(page.locator("span").filter({ hasText: /^Rejected$/ })).toBeVisible();
  await expect(page.locator("span").filter({ hasText: /^Archived$/ })).toBeVisible();
});
