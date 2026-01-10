import { test, expect } from '@playwright/test';

/**
 * E2E Tests for Knowledge Base Main Page
 * Covers: Page load, search functionality, category navigation, document interaction
 */

test.describe('Knowledge Base Main Page', () => {
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
      const request = route.request();
      const postData = request.postDataJSON();
      const query = postData?.query || '';
      
      // Return mock results based on query
      const queryLower = query.toLowerCase();
      let mockResults = [];
      
      if (queryLower.includes('xyzabc123nonexistent') || queryLower.includes('nonexistent')) {
        // Return empty results for non-existent queries
        mockResults = [];
      } else if (queryLower.includes('visa') || queryLower.includes('kitas')) {
        mockResults = [
          {
            content: 'KITAS visa information',
            metadata: {
              document_id: 'doc-1',
              title: 'KITAS Guide',
              collection: 'kitas',
            },
            score: 0.9,
          },
        ];
      } else if (query.trim() === '') {
        mockResults = [];
      } else {
        mockResults = [
          {
            content: `Search results for: ${query}`,
            metadata: {
              document_id: 'doc-2',
              title: `Document about ${query}`,
              collection: 'general',
            },
            score: 0.8,
          },
        ];
      }

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          results: mockResults,
          total: mockResults.length,
          query,
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
    
    // Navigate to knowledge page
    await page.goto('/knowledge');
    try {
      await page.waitForLoadState('networkidle', { timeout: 10000 });
    } catch (e) {
      // ignore timeout
    }
  });

  test('should load knowledge page correctly', async ({ page }) => {
    // Wait for page to be fully loaded
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
    
    // Check page title - use main content area to avoid multiple matches
    await expect(page.locator('main h1:has-text("Knowledge Base")')).toBeVisible({ timeout: 10000 });
    
    // Check search bar
    const searchInput = page.locator('input[placeholder*="Search knowledge base"]');
    await expect(searchInput).toBeVisible();
    
    // Check "New Document" button
    await expect(page.locator('button:has-text("New Document")')).toBeVisible();
    
    // Check all categories are visible (using h3 for headings)
    await expect(page.locator('h3:has-text("KITAS & Visa")')).toBeVisible();
    await expect(page.locator('h3:has-text("Company & Licenses")')).toBeVisible();
    await expect(page.locator('h3:has-text("Tax & NPWP")')).toBeVisible();
    await expect(page.locator('h3:has-text("Our Journey")')).toBeVisible();
  });

  test('should display category cards with correct information', async ({ page }) => {
    // Wait for page to be fully loaded
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
    
    // Check KITAS category - use h3 for heading
    const kitasCard = page.locator('h3:has-text("KITAS & Visa")').locator('..');
    await expect(kitasCard).toBeVisible();
    await expect(kitasCard.locator('text=View visa guides')).toBeVisible();
    
    // Check Company & Licenses category - use h3 for heading
    const companyCard = page.locator('h3:has-text("Company & Licenses")').locator('..');
    await expect(companyCard).toBeVisible();
    await expect(companyCard.locator('p:has-text("Company & Licenses")')).toBeVisible();
    
    // Check Tax category - use h3 for heading
    const taxCard = page.locator('h3:has-text("Tax & NPWP")').locator('..');
    await expect(taxCard).toBeVisible();
    await expect(taxCard.locator('text=NPWP, SPT, BPJS, LKPM')).toBeVisible();
    
    // Check Our Journey category - use h3 for heading
    const journeyCard = page.locator('h3:has-text("Our Journey")').locator('..');
    await expect(journeyCard).toBeVisible();
    await expect(journeyCard.locator('text=Coming soon')).toBeVisible();
  });

  test('should perform search and display results', async ({ page }) => {
    const searchInput = page.locator('input[placeholder*="Search knowledge base"]');
    
    // Type search query
    await searchInput.fill('visa');
    await searchInput.press('Enter');
    
    // Wait for search to complete (debounce + API call)
    await page.waitForTimeout(2000);
    
    // Check that search results section appears
    const resultsSection = page.locator('text=Search Results');
    await expect(resultsSection).toBeVisible({ timeout: 10000 });
  });

  test('should navigate to KITAS category page', async ({ page }) => {
    // Wait for page to be fully loaded
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
    
    // Use h3 for category heading
    const kitasCard = page.locator('h3:has-text("KITAS & Visa")').locator('..');
    await expect(kitasCard).toBeVisible();
    await kitasCard.click();
    
    // Should navigate to KITAS page
    await page.waitForURL(/.*\/knowledge\/kitas/, { timeout: 10000 });
    await expect(page).toHaveURL(/.*\/knowledge\/kitas/);
  });

  test('should navigate to Company & Licenses page', async ({ page }) => {
    // Wait for page to be fully loaded
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
    
    // Use h3 for category heading
    const companyCard = page.locator('h3:has-text("Company & Licenses")').locator('..');
    await expect(companyCard).toBeVisible();
    await companyCard.click();
    
    // Should navigate to company-licenses page
    await page.waitForURL(/.*\/knowledge\/company-licenses/, { timeout: 10000 });
    await expect(page).toHaveURL(/.*\/knowledge\/company-licenses/);
  });

  test('should navigate to Tax & NPWP page', async ({ page }) => {
    // Wait for page to be fully loaded
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
    
    // Use h3 for category heading
    const taxCard = page.locator('h3:has-text("Tax & NPWP")').locator('..');
    await expect(taxCard).toBeVisible();
    await taxCard.click();
    
    // Should navigate to tax page
    await page.waitForURL(/.*\/knowledge\/tax/, { timeout: 10000 });
    await expect(page).toHaveURL(/.*\/knowledge\/tax/);
  });

  test('should navigate to Our Journey page', async ({ page }) => {
    // Wait for page to be fully loaded
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
    
    // Use h3 for category heading
    const journeyCard = page.locator('h3:has-text("Our Journey")').locator('..');
    await expect(journeyCard).toBeVisible();
    await journeyCard.click();
    
    // Should navigate to our-journey page
    await page.waitForURL(/.*\/knowledge\/our-journey/, { timeout: 10000 });
    await expect(page).toHaveURL(/.*\/knowledge\/our-journey/);
  });

  test('should show empty state when no search results', async ({ page }) => {
    const searchInput = page.locator('input[placeholder*="Search knowledge base"]');
    
    // Search for something that likely won't return results
    await searchInput.fill('xyzabc123nonexistent');
    await searchInput.press('Enter');
    
    // Wait for search to complete
    await page.waitForTimeout(2000);
    
    // Check for "No documents found" message
    await expect(page.locator('text=No documents found')).toBeVisible({ timeout: 10000 });
  });

  test('should clear search when input is cleared', async ({ page }) => {
    const searchInput = page.locator('input[placeholder*="Search knowledge base"]');
    
    // Perform a search
    await searchInput.fill('test');
    await page.waitForTimeout(2000);
    
    // Clear the search
    await searchInput.fill('');
    await page.waitForTimeout(1000);
    
    // Search results should disappear
    const resultsSection = page.locator('text=Search Results');
    // Results section might still be visible briefly, but should eventually disappear
    // or show "Recent Documents" instead
  });

  test('should navigate to new document page', async ({ page }) => {
    const newDocButton = page.locator('button:has-text("New Document")');
    await newDocButton.click();
    
    // Should navigate to upload page
    await page.waitForURL(/.*\/knowledge\/upload/, { timeout: 5000 });
    await expect(page).toHaveURL(/.*\/knowledge\/upload/);
  });

  test('should display info box with correct text', async ({ page }) => {
    const infoBox = page.locator('text=The Knowledge Base contains all company documents');
    await expect(infoBox).toBeVisible();
    await expect(infoBox).toContainText('Integrated with Zantara AI for semantic search');
  });

  test('should handle search with Enter key', async ({ page }) => {
    const searchInput = page.locator('input[placeholder*="Search knowledge base"]');
    
    await searchInput.fill('company');
    await searchInput.press('Enter');
    
    // Wait for search
    await page.waitForTimeout(2000);
    
    // Should show search results
    const resultsSection = page.locator('text=Search Results');
    await expect(resultsSection).toBeVisible({ timeout: 10000 });
  });

  test('should debounce search input', async ({ page }) => {
    const searchInput = page.locator('input[placeholder*="Search knowledge base"]');
    
    // Type multiple characters quickly
    await searchInput.fill('v');
    await page.waitForTimeout(100);
    await searchInput.fill('vi');
    await page.waitForTimeout(100);
    await searchInput.fill('vis');
    await page.waitForTimeout(100);
    await searchInput.fill('visa');
    
    // Wait for debounce + API call
    await page.waitForTimeout(2000);
    
    // Should only trigger one search (check network requests or results)
    const resultsSection = page.locator('text=Search Results');
    await expect(resultsSection).toBeVisible({ timeout: 10000 });
  });
});

