import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

test.beforeEach(({}, testInfo) => {
  test.skip(
    !["saas-mobile", "saas-tablet"].includes(testInfo.project.name),
    "Responsive checks run in the explicit Chromium viewport projects",
  );
});

async function expectNoHorizontalOverflow(page: Page) {
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBe(true);
}

test("A11Y-03 responsive auth surface has focusable controls and no overflow", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Continue your focused search." })).toBeVisible();
  await page.getByLabel("Email address").focus();
  await expect(page.getByLabel("Email address")).toBeFocused();
  await expectNoHorizontalOverflow(page);
  const results = await new AxeBuilder({ page: page as never })
    .disableRules(["color-contrast"])
    .analyze();
  expect(results.violations.filter((violation) => ["critical", "serious"].includes(violation.impact ?? ""))).toEqual([]);
});

test("A11Y-04 responsive desktop-configured navigation stays usable", async ({ page }) => {
  await page.goto("/signup");
  await expect(page.getByRole("heading", { name: "Start with better-fit roles." })).toBeVisible();
  await page.getByLabel("Email address").focus();
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Password")).toBeFocused();
  await expectNoHorizontalOverflow(page);
});
