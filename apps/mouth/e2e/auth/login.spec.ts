import { test, expect } from '@playwright/test';

/**
 * E2E Tests for Authentication Flow (Scientific Phase 4)
 * Covers: Login, Error Handling, Session Persistence, Logout
 * API Point: 1 (Auth)
 */

test.describe('Authentication Flow', () => {
  // Increase timeout for this suite to handle Next.js rebuilds
  test.setTimeout(60000);

  test.beforeEach(async ({ page }) => {
    // Log all requests to debug
    page.on('request', (request) => console.log('>>', request.method(), request.url()));

    await page.goto('/login');
    // Wait for network idle to ensure hydration
    try {
      await page.waitForLoadState('networkidle', { timeout: 10000 });
    } catch (e) {
      console.log('Network idle timeout, proceeding...');
    }
  });

  test('should display login form correctly', async ({ page }) => {
    await expect(page.locator('input[name="email"]')).toBeVisible();
    await expect(page.locator('input[name="pin"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeDisabled(); // Initially disabled
  });

  test('should show error for invalid credentials', async ({ page }) => {
    // Mock 401 response
    await page.route(/.*\/api\/auth\/login/, async (route) => {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({
          detail: 'Invalid email or PIN',
        }),
      });
    });

    await page.fill('input[name="email"]', 'invalid@example.com');
    await page.fill('input[name="pin"]', '000000');
    await page.click('button[type="submit"]');

    // Verify error message
    await expect(page.getByText(/Invalid email or PIN/i)).toBeVisible({ timeout: 10000 });
  });

  test('should validate input constraints', async ({ page }) => {
    // Invalid PIN length
    await page.fill('input[name="email"]', 'test@balizero.com');
    await page.fill('input[name="pin"]', '123');
    await expect(page.locator('button[type="submit"]')).toBeDisabled();

    // Valid inputs
    await page.fill('input[name="pin"]', '123456');
    await expect(page.locator('button[type="submit"]')).toBeEnabled();
  });

  test('should login successfully and redirect to chat', async ({ page }) => {
    // Listen to browser console
    page.on('console', (msg) => console.log(`BROWSER LOG: ${msg.text()}`));

    // Mock Success Response (Matches auth.py LoginResponse)
    await page.route(/.*\/api\/auth\/login/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          message: 'Login successful',
          data: {
            token: 'mock-jwt-token-123',
            token_type: 'Bearer',
            expiresIn: 3600,
            user: {
              id: '1',
              email: 'test@balizero.com',
              name: 'Test User',
              role: 'user',
              status: 'active',
            },
          },
        }),
      });
    });

    await page.fill('input[name="email"]', 'test@balizero.com');
    await page.fill('input[name="pin"]', '123456');
    await page.click('button[type="submit"]');

    // Verify Redirect
    await page.waitForURL('/chat');
    await expect(page).toHaveURL('/chat');
  });

  test('should persist login session after reload', async ({ page }) => {
    // Mock Login
    await page.route(/.*\/api\/auth\/login/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          message: 'Login successful',
          data: {
            token: 'mock-jwt-token-persist',
            token_type: 'Bearer',
            expiresIn: 3600,
            user: { id: '1', email: 'persist@balizero.com', name: 'Persist User', role: 'user' },
          },
        }),
      });
    });

    // Perform Login
    await page.fill('input[name="email"]', 'persist@balizero.com');
    await page.fill('input[name="pin"]', '123456');
    await page.click('button[type="submit"]');
    await page.waitForURL('/chat');

    // Reload Page
    await page.reload();
    await expect(page).toHaveURL('/chat');
  });
});
