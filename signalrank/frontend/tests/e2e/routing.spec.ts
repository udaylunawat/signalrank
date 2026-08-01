import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test.beforeEach(({}, testInfo) => {
  test.skip(testInfo.project.name === "desktop-web-chromium", "SaaS routing is not used by desktop mode");
});

test("AUTH-01 signed-out users are redirected from dashboard to login", async ({
  page,
}) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login\?callbackUrl=/);
  await expect(page.getByRole("heading", { name: "Continue your focused search." })).toBeVisible();
});

test("A11Y-01 login has no critical or serious accessibility violations", async ({
  page,
}) => {
  await page.goto("/login");
  const results = await new AxeBuilder({ page: page as never })
    .disableRules(["color-contrast"])
    .analyze();
  expect(
    results.violations.filter((violation) =>
      ["critical", "serious"].includes(violation.impact ?? ""),
    ),
  ).toEqual([]);
});
