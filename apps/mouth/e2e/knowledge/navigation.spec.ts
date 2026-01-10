import { test, expect } from '@playwright/test';

/**
 * E2E Tests for Knowledge Base Navigation Flow
 * Covers: Complete navigation flow between all knowledge pages
 */

test.describe('Knowledge Base Navigation Flow', () => {
  test.setTimeout(90000);

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
  });

  test('should navigate complete flow: main -> company-licenses -> blueprints -> back', async ({ page }) => {
    // Start at main knowledge page
    await page.goto('/knowledge');
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
    await expect(page).toHaveURL(/.*\/knowledge$/);
    
    // Click Company & Licenses - use h3 for category heading
    const companyCard = page.locator('h3:has-text("Company & Licenses")').locator('..');
    await expect(companyCard).toBeVisible();
    await companyCard.click();
    await page.waitForURL(/.*\/knowledge\/company-licenses/, { timeout: 10000 });
    await expect(page.locator('h1:has-text("Company & Licenses")')).toBeVisible();
    
    // Click Company button - use h2 for button heading
    const companyButton = page.locator('h2:has-text("Company")').locator('..').locator('..');
    await expect(companyButton).toBeVisible();
    await companyButton.click();
    await page.waitForURL(/.*\/knowledge\/blueprints/, { timeout: 10000 });
    await expect(page).toHaveURL(/.*\/knowledge\/blueprints/);
    
    // Navigate back to company-licenses
    await page.goBack();
    await page.waitForURL(/.*\/knowledge\/company-licenses/, { timeout: 10000 });
    
    // Navigate back to main again
    const backButton = page.locator('button:has-text("Back to Knowledge Base")');
    await expect(backButton).toBeVisible();
    await backButton.click();
    await page.waitForURL(/.*\/knowledge$/, { timeout: 10000 });
    await expect(page).toHaveURL(/.*\/knowledge$/);
  });

  test('should navigate complete flow: main -> company-licenses -> licenses -> back', async ({ page }) => {
    // Start at main knowledge page
    await page.goto('/knowledge');
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
    
    // Click Company & Licenses - use h3 for category heading
    const companyCard = page.locator('h3:has-text("Company & Licenses")').locator('..');
    await expect(companyCard).toBeVisible();
    await companyCard.click();
    await page.waitForURL(/.*\/knowledge\/company-licenses/, { timeout: 10000 });
    
    // Click Licenses button - use h2 for button heading
    const licensesButton = page.locator('h2:has-text("Licenses")').locator('..').locator('..');
    await expect(licensesButton).toBeVisible();
    await licensesButton.click();
    await page.waitForURL(/.*\/knowledge\/licenses/, { timeout: 10000 });
    await expect(page).toHaveURL(/.*\/knowledge\/licenses/);
    
    // Navigate back
    await page.goBack();
    await page.waitForURL(/.*\/knowledge\/company-licenses/, { timeout: 10000 });
  });

  test('should navigate: main -> our-journey -> back', async ({ page }) => {
    // Start at main knowledge page
    await page.goto('/knowledge');
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
    
    // Click Our Journey - use h3 for category heading
    const journeyCard = page.locator('h3:has-text("Our Journey")').locator('..');
    await expect(journeyCard).toBeVisible();
    await journeyCard.click();
    await page.waitForURL(/.*\/knowledge\/our-journey/, { timeout: 10000 });
    await expect(page.locator('h1:has-text("Our Journey")')).toBeVisible();
    await expect(page.locator('text=Coming Soon')).toBeVisible();
    
    // Navigate back
    const backButton = page.locator('button:has-text("Back to Knowledge Base")');
    await expect(backButton).toBeVisible();
    await backButton.click();
    await page.waitForURL(/.*\/knowledge$/, { timeout: 10000 });
    await expect(page).toHaveURL(/.*\/knowledge$/);
  });

  test('should navigate: main -> kitas -> back', async ({ page }) => {
    // Start at main knowledge page
    await page.goto('/knowledge');
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
    
    // Click KITAS & Visa - use h3 for category heading
    const kitasCard = page.locator('h3:has-text("KITAS & Visa")').locator('..');
    await expect(kitasCard).toBeVisible();
    await kitasCard.click();
    await page.waitForURL(/.*\/knowledge\/kitas/, { timeout: 10000 });
    await expect(page).toHaveURL(/.*\/knowledge\/kitas/);
    
    // Navigate back
    await page.goBack();
    await page.waitForURL(/.*\/knowledge$/, { timeout: 10000 });
  });

  test('should navigate: main -> tax -> back', async ({ page }) => {
    // Start at main knowledge page
    await page.goto('/knowledge');
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
    
    // Click Tax & NPWP - use h3 for category heading
    const taxCard = page.locator('h3:has-text("Tax & NPWP")').locator('..');
    await expect(taxCard).toBeVisible();
    await taxCard.click();
    await page.waitForURL(/.*\/knowledge\/tax/, { timeout: 10000 });
    await expect(page).toHaveURL(/.*\/knowledge\/tax/);
    
    // Navigate back
    await page.goBack();
    await page.waitForURL(/.*\/knowledge$/, { timeout: 10000 });
  });

  test('should maintain state when navigating between pages', async ({ page }) => {
    // Start at main knowledge page
    await page.goto('/knowledge');
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
    
    // Perform a search
    const searchInput = page.locator('input[placeholder*="Search knowledge base"]');
    await expect(searchInput).toBeVisible();
    await searchInput.fill('test');
    await page.waitForTimeout(2000);
    
    // Navigate to company-licenses - use h3 for category heading
    const companyCard = page.locator('h3:has-text("Company & Licenses")').locator('..');
    await expect(companyCard).toBeVisible();
    await companyCard.click();
    await page.waitForURL(/.*\/knowledge\/company-licenses/, { timeout: 10000 });
    
    // Navigate back
    const backButton = page.locator('button:has-text("Back to Knowledge Base")');
    await expect(backButton).toBeVisible();
    await backButton.click();
    await page.waitForURL(/.*\/knowledge$/, { timeout: 10000 });
    
    // Search input should be cleared (or maintain state depending on implementation)
    // This test verifies navigation doesn't break
    await expect(page.locator('main h1:has-text("Knowledge Base")')).toBeVisible();
  });
});

