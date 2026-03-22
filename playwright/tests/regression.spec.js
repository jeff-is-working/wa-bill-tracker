// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Regression tests -- verify post-session behavior and governor-related display.
 *
 * The 2026 WA legislative session ended March 12, 2026.  After session end
 * the app switches the stat cards to show "Awaiting Governor" and
 * "Signed Into Law" instead of "Hearings This Week" and "Days Remaining".
 *
 * These tests confirm that:
 *   - Governor-related stat cards are visible post-session
 *   - Enacted bills appear in the default view (not hidden by cutoff filters)
 *   - Governor-status bills appear in the default view
 */

/** Helper: wait for bills to finish loading */
async function waitForBills(page) {
  await page.locator('.bill-card').first().waitFor({ state: 'visible', timeout: 30_000 });
}

test.describe('Post-session regression tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForBills(page);
  });

  test('post-session governor stats are visible in header stat cards', async ({ page }) => {
    // After session end, the app relabels the stat cards:
    //   "Hearings This Week" -> "Awaiting Governor"
    //   "Days Remaining" -> "Signed Into Law"
    const hearingsLabel = page.locator('#hearingsLabel');
    const daysLeftLabel = page.locator('#daysLeftLabel');

    await expect(hearingsLabel).toHaveText('Awaiting Governor', { timeout: 15_000 });
    await expect(daysLeftLabel).toHaveText('Signed Into Law', { timeout: 15_000 });
  });

  test('awaiting governor stat shows a number >= 0', async ({ page }) => {
    const hearingsValue = page.locator('#hearingsWeek');
    await expect(hearingsValue).not.toHaveText('0', { timeout: 30_000 });

    const value = await hearingsValue.textContent();
    expect(Number(value)).toBeGreaterThanOrEqual(0);
  });

  test('signed into law stat shows a number > 0', async ({ page }) => {
    const daysLeftValue = page.locator('#daysLeft');

    // Wait for the value to update from default "60"
    await expect(daysLeftValue).not.toHaveText('60', { timeout: 30_000 });

    const value = await daysLeftValue.textContent();
    expect(Number(value)).toBeGreaterThan(0);
  });

  test('enacted bills are visible in default view', async ({ page }) => {
    // Open the filters panel and select "Signed Into Law"
    await page.locator('#filterToggle').click();
    await expect(page.locator('#filtersPanel')).toBeVisible();

    const enactedTag = page.locator('.filter-tag[data-value="enacted"]');
    await enactedTag.click();

    // Enacted bills should be visible (not hidden by cutoff logic)
    await expect(async () => {
      const count = await page.locator('.bill-card').count();
      expect(count).toBeGreaterThan(0);
    }).toPass({ timeout: 15_000 });
  });

  test('governor status bills are visible in default view', async ({ page }) => {
    // Open the filters panel and select "At Governor"
    await page.locator('#filterToggle').click();
    await expect(page.locator('#filtersPanel')).toBeVisible();

    const governorTag = page.locator('.filter-tag[data-value="governor"]');
    await governorTag.click();

    // Governor-status bills should be visible
    await expect(async () => {
      const count = await page.locator('.bill-card').count();
      expect(count).toBeGreaterThan(0);
    }).toPass({ timeout: 15_000 });
  });

  test('enacted bills are not hidden by inactive bill toggle being off', async ({ page }) => {
    // By default, "Show inactive bills" is unchecked.
    // Enacted bills should still be visible because they passed all cutoffs.
    const inactiveToggle = page.locator('#showInactiveBills');
    await expect(inactiveToggle).not.toBeChecked();

    // Filter to enacted bills
    await page.locator('#filterToggle').click();
    const enactedTag = page.locator('.filter-tag[data-value="enacted"]');
    await enactedTag.click();

    await expect(async () => {
      const count = await page.locator('.bill-card').count();
      expect(count).toBeGreaterThan(0);
    }).toPass({ timeout: 15_000 });
  });
});
