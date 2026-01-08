import { test, expect } from '@playwright/test';

/**
 * E2E Tests for Our Journey Page
 * Covers: Page load, empty state, back button
 */

test.describe('Our Journey Page', () => {
  test.setTimeout(60000);

  test.beforeEach(async ({ page }) => {
    const mockUser = { id: '1', email: 'zero@balizero.com', name: 'Zero User', role: 'user' };
    
    // Mock login API
    await page.route('**/api/auth/login', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          message: 'Login successful',
          data: {
            token: 'mock-jwt-token',
            token_type: 'Bearer',
            expiresIn: 3600,
            user: mockUser,
          },
        }),
      });
    });

    // Mock profile API (called after login to verify token)
    await page.route('**/api/auth/profile', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockUser),
      });
    });

    // Mock clock status API (called by workspace layout)
    await page.route('**/api/team/my-status**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          is_online: false,
          today_hours: 0,
          week_hours: 0,
        }),
      });
    });

    // Mock knowledge search API
    await page.route('**/api/search/', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          results: [],
          total: 0,
          query: '',
        }),
      });
    });

    // Login first
    await page.goto('/login');
    await page.fill('input[name="email"]', 'zero@balizero.com');
    await page.fill('input[name="pin"]', '010719');
    await page.click('button[type="submit"]');
    
    // Wait for navigation - could be /chat or /dashboard
    await page.waitForURL(/\/(chat|dashboard)/, { timeout: 10000 });
    
    // Navigate to our-journey page
    await page.goto('/knowledge/our-journey');
    try {
      await page.waitForLoadState('networkidle', { timeout: 10000 });
    } catch (e) {
      // ignore timeout
    }
  });

  test('should load our-journey page correctly', async ({ page }) => {
    // Wait for page to be fully loaded
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
    
    // Check page title
    await expect(page.locator('h1:has-text("Our Journey")')).toBeVisible({ timeout: 10000 });
    
    // Check description
    await expect(page.locator('text=This section will showcase our journey and milestones')).toBeVisible();
    
    // Check back button
    const backButton = page.locator('button:has-text("Back to Knowledge Base")');
    await expect(backButton).toBeVisible();
  });

  test('should display empty state with coming soon message', async ({ page }) => {
    // Wait for page to be fully loaded
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
    
    // Check for "Coming Soon" heading
    await expect(page.locator('h3:has-text("Coming Soon")')).toBeVisible({ timeout: 10000 });
    
    // Check for empty state message
    await expect(page.locator('text=This section is being prepared')).toBeVisible();
    await expect(page.locator('text=Check back soon for updates')).toBeVisible();
  });

  test('should navigate back to knowledge base', async ({ page }) => {
    // Wait for page to be fully loaded
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
    
    const backButton = page.locator('button:has-text("Back to Knowledge Base")');
    await expect(backButton).toBeVisible();
    await backButton.click();
    
    // Should navigate back to main knowledge page
    await page.waitForURL(/.*\/knowledge$/, { timeout: 10000 });
    await expect(page).toHaveURL(/.*\/knowledge$/);
  });

  test('should have correct page structure', async ({ page }) => {
    // Wait for page to be fully loaded
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
    
    // Check header section exists
    const header = page.locator('h1:has-text("Our Journey")').locator('..');
    await expect(header).toBeVisible({ timeout: 10000 });
    
    // Check empty state section exists
    const emptyState = page.locator('h3:has-text("Coming Soon")').locator('..');
    await expect(emptyState).toBeVisible();
  });
});

