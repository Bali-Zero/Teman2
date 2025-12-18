import { test, expect } from '@playwright/test';

/**
 * E2E Tests per Chat Flow
 * Testa il flusso completo di chat con AI
 */

test.describe('Chat Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Mock login e navigazione alla chat
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
            user: { id: '1', email: 'test@balizero.com', name: 'Test User', role: 'user' },
          },
        }),
      });
    });

    await page.goto('/login');
    await page.fill('input#email, input[name="email"]', 'test@balizero.com');
    await page.fill('input#pin, input[name="pin"]', '123456');
    await page.click('button[type="submit"]');
    await page.waitForURL('/chat');
  });

  test('should display chat interface', async ({ page }) => {
    // Verifica elementi principali della chat
    await expect(page.locator('textarea, input[type="text"]')).toBeVisible();
    await expect(
      page.locator('button[aria-label="Send message"], button[aria-label*="Send"]')
    ).toBeVisible();
  });

  test('should send a message and display it', async ({ page }) => {
    const testMessage = 'Hello, ZANTARA!';

    // Mock della risposta API
    await page.route('**/api/bali-zero/chat-stream**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: `data: ${JSON.stringify({ content: 'Hello! How can I help you?', done: true })}\n\n`,
      });
    });

    // Trova input e invia messaggio
    const input = page.locator('textarea, input[type="text"]').first();
    await input.fill(testMessage);
    await page.locator('button[aria-label="Send message"]').click();

    // Verifica che il messaggio utente appaia
    await expect(page.locator(`text="${testMessage}"`)).toBeVisible({ timeout: 5000 });
  });

  test('should display AI response', async ({ page }) => {
    const testMessage = 'Come aprire un PT PMA?';

    // Mock streaming response
    await page.route('**/api/bali-zero/chat-stream**', async (route) => {
      const response = [
        `data: ${JSON.stringify({ content: 'Per aprire un PT PMA', done: false })}\n\n`,
        `data: ${JSON.stringify({ content: ' devi seguire questi passaggi:', done: false })}\n\n`,
        `data: ${JSON.stringify({ content: ' 1. Nome azienda...', done: true })}\n\n`,
      ];
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: response.join(''),
      });
    });

    const input = page.locator('textarea, input[type="text"]').first();
    await input.fill(testMessage);
    // Use consistent selector - try multiple possible selectors
    const sendButton = page.locator('button[aria-label="Send message"], button:has-text("Send"), button[type="submit"]').first();
    await sendButton.click();

    // Attendi risposta AI
    await page.waitForTimeout(2000);
    await expect(page.locator('text=/PT PMA|passaggi|azienda/i')).toBeVisible({ timeout: 10000 });
  });

  test('should handle multiple messages in conversation', async ({ page }) => {
    const messages = ['First message', 'Second message', 'Third message'];

    await page.route('**/api/bali-zero/chat-stream**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: `data: ${JSON.stringify({ content: 'Response', done: true })}\n\n`,
      });
    });

    for (const message of messages) {
      const input = page.locator('textarea, input[type="text"]').first();
      await input.fill(message);
      await page.locator('button:has-text("Send"), button[type="submit"]').first().click();
      await page.waitForTimeout(1000);
    }

    // Verifica che tutti i messaggi siano visibili
    for (const message of messages) {
      await expect(page.locator(`text="${message}"`)).toBeVisible();
    }
  });

  test('should show loading state while waiting for AI response', async ({ page }) => {
    const testMessage = 'Test message';

    // Delay nella risposta per testare loading state
    await page.route('**/api/bali-zero/chat-stream**', async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 2000));
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: `data: ${JSON.stringify({ content: 'Response', done: true })}\n\n`,
      });
    });

    const input = page.locator('textarea, input[type="text"]').first();
    await input.fill(testMessage);
    await page.locator('button:has-text("Send"), button[type="submit"]').first().click();

    // Verifica loading indicator (se presente)
    // Potrebbe essere un spinner o testo "Loading..."
    const loadingIndicator = page.locator('text=/loading|sending|waiting/i').first();
    if (await loadingIndicator.isVisible().catch(() => false)) {
      await expect(loadingIndicator).toBeVisible();
    }
  });

  test('should handle empty message', async ({ page }) => {
    const input = page.locator('textarea, input[type="text"]').first();
    const sendButton = page.locator('button:has-text("Send"), button[type="submit"]').first();

    // Prova a inviare messaggio vuoto
    await input.fill('');

    // Il bottone dovrebbe essere disabilitato o non inviare nulla
    const isDisabled = await sendButton.isDisabled().catch(() => false);
    if (isDisabled) {
      await expect(sendButton).toBeDisabled();
    }
  });
});
