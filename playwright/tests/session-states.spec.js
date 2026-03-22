// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Session lifecycle state tests -- verify post-session UI behavior.
 *
 * The 2026 WA legislative session ended March 12, 2026. After session end
 * the app switches stat card labels and adds post-session filter tags
 * for governor-related statuses.
 *
 * The app loads data remotely from raw.githubusercontent.com so generous
 * timeouts are used to account for network latency.
 */

/** Helper: wait for bills to finish loading */
async function waitForBills(page) {
  await page.locator('.bill-card').first().waitFor({ state: 'visible', timeout: 30_000 });
}

test.describe('Session lifecycle states', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForBills(page);
  });

  test('post-session stat label shows "Awaiting Governor" text', async ({ page }) => {
    const hearingsLabel = page.locator('#hearingsLabel');
    await expect(hearingsLabel).toHaveText('Awaiting Governor', { timeout: 15_000 });
  });

  test('post-session stat label shows "Signed Into Law" text', async ({ page }) => {
    const daysLeftLabel = page.locator('#daysLeftLabel');
    await expect(daysLeftLabel).toHaveText('Signed Into Law', { timeout: 15_000 });
  });

  test('"Passed Legislature" filter tag exists', async ({ page }) => {
    // Open the filters panel to reveal filter tags
    await page.locator('#filterToggle').click();
    await expect(page.locator('#filtersPanel')).toBeVisible();

    const passedLegTag = page.locator('span.filter-tag[data-value="passed_legislature"]');
    await expect(passedLegTag).toBeVisible({ timeout: 10_000 });
  });

  test('"At Governor" filter tag exists', async ({ page }) => {
    await page.locator('#filterToggle').click();
    await expect(page.locator('#filtersPanel')).toBeVisible();

    const governorTag = page.locator('span.filter-tag[data-value="governor"]');
    await expect(governorTag).toBeVisible({ timeout: 10_000 });
  });

  test('"Signed Into Law" filter tag exists', async ({ page }) => {
    await page.locator('#filterToggle').click();
    await expect(page.locator('#filtersPanel')).toBeVisible();

    const enactedTag = page.locator('span.filter-tag[data-value="enacted"]');
    await expect(enactedTag).toBeVisible({ timeout: 10_000 });
  });

  test('clicking "Signed Into Law" filter shows enacted bills', async ({ page }) => {
    // Open filters panel
    await page.locator('#filterToggle').click();
    await expect(page.locator('#filtersPanel')).toBeVisible();

    // Click the enacted filter tag
    const enactedTag = page.locator('.filter-tag[data-value="enacted"]');
    await enactedTag.click();

    // Wait for bills to re-render with enacted filter applied
    await expect(async () => {
      const count = await page.locator('.bill-card').count();
      expect(count).toBeGreaterThan(0);
    }).toPass({ timeout: 15_000 });
  });
});
