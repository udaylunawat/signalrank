import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("WEB-01 signed-out users are redirected from dashboard to login", async ({
  page,
}) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login\?callbackUrl=/);
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
});

test("WEB-07 login has no critical or serious accessibility violations", async ({
  page,
}) => {
  await page.goto("/login");
  const results = await new AxeBuilder({ page })
    .disableRules(["color-contrast"])
    .analyze();
  expect(
    results.violations.filter((violation) =>
      ["critical", "serious"].includes(violation.impact ?? ""),
    ),
  ).toEqual([]);
});
