import { test, expect } from '@playwright/test';

test.describe('page Page', () => {
  test('should load page', async ({ page }) => {
    await page.goto('/chat');
    // TODO: Add assertions
    await expect(page).toHaveTitle(/.*/);
  });

  // TODO: Add more test cases
});
