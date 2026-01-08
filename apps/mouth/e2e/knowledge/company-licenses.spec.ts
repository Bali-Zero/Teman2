import { test, expect } from '@playwright/test';

/**
 * E2E Tests for Company & Licenses Page
 * Covers: Page load, navigation buttons, back button
 */

test.describe('Company & Licenses Page', () => {
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
    
    // Navigate to company-licenses page
    await page.goto('/knowledge/company-licenses');
    try {
      await page.waitForLoadState('networkidle', { timeout: 10000 });
    } catch (e) {
      // ignore timeout
    }
  });

  test('should load company-licenses page correctly', async ({ page }) => {
    // Wait for page to be fully loaded
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
    
    // Check page title
    await expect(page.locator('h1:has-text("Company & Licenses")')).toBeVisible({ timeout: 10000 });
    
    // Check description
    await expect(page.locator('text=Choose between Company setup guides')).toBeVisible();
    
    // Check back button
    const backButton = page.locator('button:has-text("Back to Knowledge Base")');
    await expect(backButton).toBeVisible();
    
    // Check both main buttons - use h2 for headings
    await expect(page.locator('h2:has-text("Company")')).toBeVisible();
    await expect(page.locator('h2:has-text("Licenses")')).toBeVisible();
    
    // Check subtitles - use more specific locators
    const companyButton = page.locator('h2:has-text("Company")').locator('..').locator('..');
    await expect(companyButton.locator('p:has-text("KBLI Blueprints")')).toBeVisible();
    
    const licensesButton = page.locator('h2:has-text("Licenses")').locator('..').locator('..');
    await expect(licensesButton.locator('p:has-text("Business Licenses")')).toBeVisible();
  });

  test('should navigate back to knowledge base', async ({ page }) => {
    const backButton = page.locator('button:has-text("Back to Knowledge Base")');
    await backButton.click();
    
    // Should navigate back to main knowledge page
    await page.waitForURL('/knowledge', { timeout: 5000 });
    await expect(page).toHaveURL(/.*\/knowledge$/);
  });

  test('should navigate to Company (KBLI Blueprints) page', async ({ page }) => {
    // Wait for page to be fully loaded
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
    
    // Find the Company button by its heading
    const companyButton = page.locator('h2:has-text("Company")').locator('..').locator('..');
    await expect(companyButton).toBeVisible();
    await companyButton.click();
    
    // Should navigate to blueprints page
    await page.waitForURL(/.*\/knowledge\/blueprints/, { timeout: 10000 });
    await expect(page).toHaveURL(/.*\/knowledge\/blueprints/);
  });

  test('should navigate to Licenses page', async ({ page }) => {
    // Wait for page to be fully loaded
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
    
    // Find the Licenses button by its heading
    const licensesButton = page.locator('h2:has-text("Licenses")').locator('..').locator('..');
    await expect(licensesButton).toBeVisible();
    await licensesButton.click();
    
    // Should navigate to licenses page
    await page.waitForURL(/.*\/knowledge\/licenses/, { timeout: 10000 });
    await expect(page).toHaveURL(/.*\/knowledge\/licenses/);
  });

  test('should display correct Company button content', async ({ page }) => {
    // Wait for page to be fully loaded
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
    
    // Find the Company button by its heading - the button contains h2
    const companyButton = page.locator('button').filter({ has: page.locator('h2:has-text("Company")') });
    await expect(companyButton).toBeVisible();
    
    // Check all content is visible within the button
    await expect(companyButton.locator('p:has-text("KBLI Blueprints")')).toBeVisible();
    await expect(companyButton.locator('text=Comprehensive')).toBeVisible();
    await expect(companyButton.locator('span:has-text("View KBLI Blueprints")')).toBeVisible();
  });

  test('should display correct Licenses button content', async ({ page }) => {
    // Wait for page to be fully loaded
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
    
    // Find the Licenses button by its heading - the button contains h2
    const licensesButton = page.locator('button').filter({ has: page.locator('h2:has-text("Licenses")') });
    await expect(licensesButton).toBeVisible();
    
    // Check all content is visible within the button
    await expect(licensesButton.locator('p:has-text("Business Licenses")')).toBeVisible();
    await expect(licensesButton.locator('text=Essential')).toBeVisible();
    await expect(licensesButton.locator('span:has-text("View Licenses Guide")')).toBeVisible();
  });

  test('should have hover effects on buttons', async ({ page }) => {
    // Wait for page to be fully loaded
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
    
    // Find the Company button by its heading
    const companyButton = page.locator('h2:has-text("Company")').locator('..').locator('..');
    
    // Hover over button
    await companyButton.hover();
    
    // Button should still be visible and interactive
    await expect(companyButton).toBeVisible();
  });
});

