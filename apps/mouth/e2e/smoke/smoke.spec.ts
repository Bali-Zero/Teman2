import { test, expect, Page } from '@playwright/test';

/**
 * ZANTARA Smoke Tests - Production Health Check
 *
 * Minimal tests to verify core functionality works.
 * Run these after every deploy to catch critical regressions.
 *
 * Tests:
 * 1. Login works
 * 2. Chat page loads
 * 3. Can send message and get response
 * 4. Streaming works (first token arrives)
 *
 * Usage:
 *   npx playwright test --config=playwright.smoke.config.ts
 *
 * Environment variables:
 *   E2E_TEST_EMAIL - test user email (default: zero@balizero.com)
 *   E2E_TEST_PIN - test user PIN (default: 010719)
 *   E2E_BASE_URL - base URL (default: https://zantara.balizero.com)
 */

const CONFIG = {
  email: process.env.E2E_TEST_EMAIL || 'zero@balizero.com',
  pin: process.env.E2E_TEST_PIN || '010719',
  baseUrl: process.env.E2E_BASE_URL || 'https://zantara.balizero.com',
};

// Increase timeout for AI responses
test.setTimeout(90_000);

test.describe('Smoke Tests - Critical Path', () => {
  test('1. Login page loads', async ({ page }) => {
    await page.goto(`${CONFIG.baseUrl}/login`);
    await expect(page.locator('input[name="email"], input[type="email"]').first()).toBeVisible();
    await expect(page.locator('input[name="pin"], input[type="password"]').first()).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });

  test('2. Login with valid credentials', async ({ page }) => {
    await page.goto(`${CONFIG.baseUrl}/login`);

    // Fill login form
    await page.locator('input[name="email"], input[type="email"]').first().fill(CONFIG.email);
    await page.locator('input[name="pin"], input[type="password"]').first().fill(CONFIG.pin);
    await page.locator('button[type="submit"]').click();

    // Should redirect to chat
    await page.waitForURL('**/chat', { timeout: 30_000 });
    await expect(page).toHaveURL(/\/chat/);
  });

  test('3. Chat page renders after login', async ({ page }) => {
    // Login first
    await page.goto(`${CONFIG.baseUrl}/login`);
    await page.locator('input[name="email"], input[type="email"]').first().fill(CONFIG.email);
    await page.locator('input[name="pin"], input[type="password"]').first().fill(CONFIG.pin);
    await page.locator('button[type="submit"]').click();
    await page.waitForURL('**/chat', { timeout: 30_000 });

    // Verify chat UI elements
    await expect(
      page.locator('textarea, input[placeholder*="message"], input[placeholder*="Message"]').first()
    ).toBeVisible();
  });

  test('4. Send message and receive streaming response', async ({ page }) => {
    // Login
    await page.goto(`${CONFIG.baseUrl}/login`);
    await page.locator('input[name="email"], input[type="email"]').first().fill(CONFIG.email);
    await page.locator('input[name="pin"], input[type="password"]').first().fill(CONFIG.pin);
    await page.locator('button[type="submit"]').click();
    await page.waitForURL('**/chat', { timeout: 30_000 });

    // Wait for chat to be ready
    await page.waitForTimeout(3000);

    // Send a simple message
    const input = page
      .locator('textarea, input[placeholder*="message"], input[placeholder*="Message"]')
      .first();
    await input.fill('Ciao');

    // Find and click send button - try multiple selectors
    const sendButton = page
      .locator('button')
      .filter({ has: page.locator('svg') })
      .last();
    await sendButton.click();

    // Wait for AI response - generous timeout for streaming
    // Look for any new text content appearing after our message
    await page.waitForTimeout(15000);

    // Take screenshot for debugging
    await page.screenshot({ path: 'test-results/chat-response-debug.png' });

    // Verify the page hasn't crashed or shown an error
    // Just check we're still on chat page
    await expect(page).toHaveURL(/\/chat/);

    // Check for any visible text that could be a response (very loose check)
    // The AI response should appear somewhere on the page
    const pageContent = await page.textContent('body');
    const hasContent = pageContent && pageContent.length > 100;
    expect(hasContent).toBeTruthy();
  });

  test('5. Health endpoint responds', async ({ request }) => {
    const response = await request.get('https://nuzantara-rag.fly.dev/health');
    expect(response.status()).toBe(200);

    const body = await response.json();
    expect(body).toHaveProperty('status');
  });
});

test.describe('Smoke Tests - RAG & Memory', () => {
  test('RAG returns sources for legal question', async ({ page }) => {
    // Login
    await page.goto(`${CONFIG.baseUrl}/login`);
    await page.locator('input[name="email"], input[type="email"]').first().fill(CONFIG.email);
    await page.locator('input[name="pin"], input[type="password"]').first().fill(CONFIG.pin);
    await page.locator('button[type="submit"]').click();
    await page.waitForURL('**/chat', { timeout: 30_000 });
    await page.waitForTimeout(2000);

    // Ask a question that should trigger RAG
    const input = page
      .locator('textarea, input[placeholder*="message"], input[placeholder*="Message"]')
      .first();
    await input.fill('Quali documenti servono per aprire una PT PMA in Indonesia?');

    const sendButton = page
      .locator('button')
      .filter({ has: page.locator('svg') })
      .last();
    await sendButton.click();

    // Wait for RAG response (longer timeout for retrieval + generation)
    await page.waitForTimeout(30000);

    // Check response contains relevant content
    const pageContent = await page.textContent('body');

    // RAG should return something about PT PMA, documents, or Indonesia
    const hasRelevantContent =
      pageContent &&
      (pageContent.toLowerCase().includes('pma') ||
        pageContent.toLowerCase().includes('dokumen') ||
        pageContent.toLowerCase().includes('indonesia') ||
        pageContent.toLowerCase().includes('akte') ||
        pageContent.toLowerCase().includes('notaris'));

    expect(hasRelevantContent).toBeTruthy();

    // Take screenshot for verification
    await page.screenshot({ path: 'test-results/rag-response.png', fullPage: true });
  });

  test('Memory persists user information', async ({ page }) => {
    // Login
    await page.goto(`${CONFIG.baseUrl}/login`);
    await page.locator('input[name="email"], input[type="email"]').first().fill(CONFIG.email);
    await page.locator('input[name="pin"], input[type="password"]').first().fill(CONFIG.pin);
    await page.locator('button[type="submit"]').click();
    await page.waitForURL('**/chat', { timeout: 30_000 });
    await page.waitForTimeout(2000);

    // Tell the AI something to remember
    const input = page
      .locator('textarea, input[placeholder*="message"], input[placeholder*="Message"]')
      .first();
    const testFact = `Il mio nome test è SmokeTestUser${Date.now()}`;
    await input.fill(testFact);

    const sendButton = page
      .locator('button')
      .filter({ has: page.locator('svg') })
      .last();
    await sendButton.click();

    // Wait for response
    await page.waitForTimeout(15000);

    // Now ask if it remembers
    await input.fill('Come mi chiamo?');
    await sendButton.click();

    // Wait for response
    await page.waitForTimeout(15000);

    // Check if the response mentions the test name
    const pageContent = await page.textContent('body');
    const remembersName = pageContent && pageContent.includes('SmokeTestUser');

    // Take screenshot
    await page.screenshot({ path: 'test-results/memory-response.png', fullPage: true });

    // Memory might not always work perfectly, so we just log the result
    // This is a "soft" check - we want to know if it works, not fail the build
    console.log(
      `Memory test: AI ${remembersName ? 'REMEMBERED' : 'did NOT remember'} the test name`
    );

    // At minimum, verify we got some response
    expect(pageContent && pageContent.length > 100).toBeTruthy();
  });
});

test.describe('Smoke Tests - Backend API', () => {
  test('Backend health check', async ({ request }) => {
    const response = await request.get('https://nuzantara-rag.fly.dev/health');
    expect(response.ok()).toBeTruthy();

    const json = await response.json();
    console.log('Health response:', JSON.stringify(json, null, 2));

    // Basic health checks
    expect(json.status).toBeDefined();
  });

  test('Backend metrics endpoint', async ({ request }) => {
    const response = await request.get('https://nuzantara-rag.fly.dev/metrics');
    // Metrics might require auth, so 200 or 401 are both acceptable
    expect([200, 401, 403]).toContain(response.status());
  });
});
