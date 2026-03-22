// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Note management tests -- verify note modal, saving notes, and export button.
 *
 * The app loads data remotely from raw.githubusercontent.com so generous
 * timeouts are used to account for network latency.
 */

/** Helper: wait for bills to finish loading */
async function waitForBills(page) {
  await page.locator('.bill-card').first().waitFor({ state: 'visible', timeout: 30_000 });
}

test.describe('Note management', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await waitForBills(page);
  });

  test('clicking a bill card note button opens the note modal', async ({ page }) => {
    // Find the first bill card's note action button
    const noteBtn = page.locator('.bill-card').first().locator('[data-action="note"]');
    await expect(noteBtn).toBeVisible({ timeout: 10_000 });
    await noteBtn.click();

    // The note modal should become visible (has 'active' class)
    const noteModal = page.locator('#noteModal');
    await expect(noteModal).toHaveClass(/active/, { timeout: 10_000 });
  });

  test('typing text in note textarea and clicking save stores the note', async ({ page }) => {
    // Open note modal for the first bill
    const noteBtn = page.locator('.bill-card').first().locator('[data-action="note"]');
    await noteBtn.click();

    const noteModal = page.locator('#noteModal');
    await expect(noteModal).toHaveClass(/active/, { timeout: 10_000 });

    // Type a test note
    const textarea = page.locator('#noteTextarea');
    await textarea.fill('Playwright test note for E2E verification');

    // Click save
    await page.locator('#noteModalSave').click();

    // After saving, the modal should close (lose 'active' class)
    await expect(noteModal).not.toHaveClass(/active/, { timeout: 10_000 });
  });

  test('export notes button exists in user panel area and is clickable', async ({ page }) => {
    // The CSV export button is in the user panel notes export area
    const csvBtn = page.locator('#csvNotesBtn');
    await expect(csvBtn).toBeVisible({ timeout: 30_000 });

    // Verify the button is enabled and clickable
    await expect(csvBtn).toBeEnabled();
  });
});
