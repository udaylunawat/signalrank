import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.E2E_BASE_URL ?? "http://127.0.0.1:3011";
const e2eMode = process.env.E2E_MODE === "desktop" ? "desktop" : "saas";
const crossBrowser = process.env.E2E_CROSS_BROWSER === "1";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI
    ? [["github"], ["html", { open: "never" }], ["./tests/e2e/support/observation-reporter.mjs"]]
    : [["list"], ["./tests/e2e/support/observation-reporter.mjs"]],
  webServer: {
    command: `${process.execPath} tests/e2e/support/run-services.mjs`,
    url: baseURL,
    timeout: 120_000,
    reuseExistingServer: !process.env.CI,
    env: { E2E_MODE: e2eMode },
  },
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "saas-chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 900 },
      },
    },
    {
      name: "desktop-web-chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "saas-mobile",
      testMatch: /responsive\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 390, height: 844 },
      },
    },
    {
      name: "saas-tablet",
      testMatch: /responsive\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 768, height: 1024 },
      },
    },
    ...(crossBrowser
      ? [
          {
            name: "saas-firefox",
            use: {
              ...devices["Desktop Firefox"],
              viewport: { width: 1440, height: 900 },
            },
          },
          {
            name: "saas-webkit",
            use: {
              ...devices["Desktop Safari"],
              viewport: { width: 1440, height: 900 },
            },
          },
        ]
      : []),
  ],
  outputDir: "test-results",
});
