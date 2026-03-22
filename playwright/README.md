# Playwright E2E Tests

End-to-end test suite for the WA Bill Tracker static site.

## Structure

```
playwright/
  playwright.config.js   - Playwright configuration (browsers, webServer, timeouts)
  tests/
    smoke.spec.js        - Page load, bill rendering, stat cards, console errors
    filters.spec.js      - Search, status filters, bill type nav, clear/reset
    regression.spec.js   - Post-session governor stats, enacted/governor bill visibility
```

## Prerequisites

```bash
npm install
npx playwright install
```

## Running Tests

```bash
# All browsers
npm test

# Chromium only (fastest)
npm run test:chromium

# With UI mode
npx playwright test --ui

# Specific test file
npx playwright test playwright/tests/smoke.spec.js
```

## Architecture Notes

- The app is a static vanilla HTML/CSS/JS site served locally via `npx serve`.
- Bill data is fetched at runtime from `raw.githubusercontent.com` -- tests use
  generous timeouts (30s) to account for network latency.
- The `webServer` config in `playwright.config.js` starts `serve` automatically
  before tests run and points to the repo root (one directory up from `playwright/`).
- No mocking or intercepting of network requests -- tests run against live data.
