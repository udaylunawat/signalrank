import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { completeOnboarding, openMatches } from "./support/flow";

async function expectAccessible(page: Page) {
  const results = await new AxeBuilder({ page: page as never }).disableRules(["color-contrast"]).analyze();
  expect(results.violations.filter((violation) => ["critical", "serious"].includes(violation.impact ?? ""))).toEqual([]);
}

test.beforeEach(({}, testInfo) => {
  test.skip(testInfo.project.name === "desktop-web-chromium", "SaaS accessibility pages run in the SaaS projects");
});

test("A11Y-02 critical authenticated pages have no critical or serious violations", async ({ page }) => {
  await completeOnboarding(page);
  await expectAccessible(page);
  await openMatches(page);
  await expectAccessible(page);
  await page.getByRole("link", { name: "Tracker" }).click();
  await expectAccessible(page);
  await page.getByRole("link", { name: "Settings" }).click();
  await expectAccessible(page);
});
