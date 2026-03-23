// @ts-check
const { defineConfig, devices } = require('@playwright/test');

/**
 * Playwright configuration for WA Bill Tracker E2E tests.
 *
 * The app is a static vanilla HTML/CSS/JS site that fetches bill data from
 * raw.githubusercontent.com at runtime.  We use the `serve` package to host
 * it locally so tests run against a real HTTP server.
 */
module.exports = defineConfig({
  testDir: './tests',

  /* Maximum time one test can run */
  timeout: 60_000,

  /* Expect timeout -- generous because the app fetches remote data */
  expect: {
    timeout: 15_000,
  },

  /* Fail the build on CI if you accidentally left test.only in the source */
  forbidOnly: !!process.env.CI,

  /* Retry once on CI to absorb flaky network fetches */
  retries: process.env.CI ? 1 : 0,

  /* Parallel workers */
  workers: process.env.CI ? 1 : undefined,

  /* Reporter */
  reporter: 'html',

  /* Shared settings for all projects */
  use: {
    baseURL: 'http://localhost:4200',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  /* Browser projects */
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
  ],

  /* Start a local static file server before running tests */
  webServer: {
    command: 'npx serve . -l 4200',
    cwd: '..',
    url: 'http://localhost:4200',
    reuseExistingServer: false,
    timeout: 30_000,
  },
});
