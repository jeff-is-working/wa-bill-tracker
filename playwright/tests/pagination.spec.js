// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Pagination tests -- verify the app paginates bill cards and shows count info.
 *
 * The app loads data remotely from raw.githubusercontent.com so generous
 * timeouts are used to account for network latency.
 */

/** Helper: wait for bills to finish loading */
async function waitForBills(page) {
  await page.locator('.bill-card').first().waitFor({ state: 'visible', timeout: 30_000 });
}

test.describe('Pagination', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForBills(page);
  });

  test('default view shows 25 or fewer bill cards', async ({ page }) => {
    const count = await page.locator('.bill-card').count();
    expect(count).toBeGreaterThan(0);
    expect(count).toBeLessThanOrEqual(25);
  });

  test('total bills stat card shows a number greater than visible card count', async ({ page }) => {
    // Wait for totalBills stat to populate
    const totalBills = page.locator('#totalBills');
    await expect(totalBills).not.toHaveText('0', { timeout: 30_000 });

    const totalText = await totalBills.textContent();
    const totalCount = Number(totalText);

    const visibleCount = await page.locator('.bill-card').count();

    // Total bills should exceed the visible page of cards, proving pagination is active
    expect(totalCount).toBeGreaterThan(visibleCount);
  });

  test('page info area shows count text', async ({ page }) => {
    // The pagination controls area should contain a .page-info span with "Showing" text
    const pageInfo = page.locator('#paginationControls .page-info');
    await expect(pageInfo).toBeVisible({ timeout: 30_000 });

    const infoText = await pageInfo.textContent();
    expect(infoText).toContain('Showing');
  });
});
