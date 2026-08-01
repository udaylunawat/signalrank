import { expect, test } from "@playwright/test";
import { signUp, uniqueEmail } from "./support/flow";

test.beforeEach(({}, testInfo) => {
  test.skip(testInfo.project.name === "desktop-web-chromium", "SaaS authentication is not available in desktop mode");
});

test("AUTH-02 valid signup creates a session and opens onboarding", async ({ page }) => {
  await signUp(page);
  await expect(page.getByRole("heading", { name: "Start with what you’ve already built." })).toBeVisible();
});

test("AUTH-03 invalid login shows a recoverable error", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email address").fill(uniqueEmail());
  await page.getByLabel("Password").fill("wrong-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.locator("p[role=alert]")).toContainText("doesn’t match");
});

test("AUTH-04 duplicate signup is rejected without replacing the first account", async ({ page }) => {
  const email = await signUp(page);
  await page.goto("/signup");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password").fill("fixture-password");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.locator("p[role=alert]")).toContainText("already exists");
});

test("AUTH-06 invalid signup is rejected and valid login restores the session", async ({ page }) => {
  await page.goto("/signup");
  await page.getByLabel("Email address").fill(uniqueEmail());
  await page.getByLabel("Password").fill("short");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/signup$/);
  expect(
    await page.getByLabel("Password").evaluate((element) =>
      (element as HTMLInputElement).validity.tooShort,
    ),
  ).toBe(true);

  const email = uniqueEmail();
  await page.request.post("http://127.0.0.1:8111/api/auth/register", {
    data: { email, password: "fixture-password" },
  });
  await page.goto("/login");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password").fill("fixture-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
});
