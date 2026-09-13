import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "tests/browser",
  workers: 1,
  timeout: 90_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: process.env.PLAYGROUND_URL || "http://127.0.0.1:8765",
    viewport: { width: 1440, height: 1000 },
    trace: "retain-on-failure",
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_PATH
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH }
      : {},
  },
  webServer: process.env.PLAYGROUND_URL
    ? undefined
    : {
        command: "python3 scripts/serve_site.py",
        url: "http://127.0.0.1:8765",
        reuseExistingServer: !process.env.CI,
      },
});
