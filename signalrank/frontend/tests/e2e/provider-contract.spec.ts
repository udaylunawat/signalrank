import { expect, test } from "@playwright/test";

test.beforeEach(({}, testInfo) => {
  test.skip(testInfo.project.name === "desktop-web-chromium", "SaaS provider fixtures run in the SaaS project");
});

test("DISC-02 recorded provider fixtures cover success, auth, rate limit, malformed, and timeout", async ({ page }) => {
  const expectedStatuses = {
    success: 200,
    auth: 401,
    rate_limit: 429,
    malformed: 200,
    timeout: 504,
  } as const;

  for (const [scenario, expectedStatus] of Object.entries(expectedStatuses)) {
    await page.request.post("http://127.0.0.1:8111/__fixture__/provider-scenario", {
      data: { name: scenario },
    });
    const openRouter = await page.request.post("http://127.0.0.1:8111/v1/chat/completions", {
      data: { model: "fixture/model", messages: [{ role: "user", content: "synthetic" }] },
    });
    expect(openRouter.status(), scenario).toBe(expectedStatus);
    if (scenario === "malformed") {
      await expect(openRouter.text()).resolves.toBe('{"choices":');
    }
    if (scenario === "rate_limit") {
      expect(openRouter.headers()["retry-after"]).toBe("1");
    }

    for (const sourceName of ["indeed", "linkedin", "remotive", "himalayas", "jobicy"]) {
      const source = await page.request.get(
        `http://127.0.0.1:8111/__fixture__/providers/${sourceName}`,
      );
      expect(source.status(), `${scenario} ${sourceName} response`).toBe(expectedStatus);
    }
  }
});
