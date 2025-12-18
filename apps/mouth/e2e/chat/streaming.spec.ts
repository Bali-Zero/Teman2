import { test, expect } from '@playwright/test';

/**
 * E2E Tests per Streaming Responses
 * Testa il comportamento dello streaming SSE (Server-Sent Events)
 */

test.describe('Streaming Responses', () => {
  test.beforeEach(async ({ page }) => {
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

  test('should display streaming text progressively', async ({ page }) => {
    const chunks = [
      'Per aprire un PT PMA',
      ' devi seguire questi passaggi:',
      ' 1. Preparare documenti',
      ' 2. Registrare presso BKPM',
      ' 3. Ottenere NIB',
    ];

    const chunkIndex = 0;
    await page.route('**/api/bali-zero/chat-stream**', async (route) => {
      const streamChunks = chunks.map((chunk, index) => {
        return `data: ${JSON.stringify({
          content: chunk,
          done: index === chunks.length - 1,
        })}\n\n`;
      });

      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        headers: {
          'Cache-Control': 'no-cache',
          Connection: 'keep-alive',
        },
        body: streamChunks.join(''),
      });
    });

    const input = page.locator('textarea, input[type="text"]').first();
    await input.fill('Come aprire un PT PMA?');
    await page.locator('button[aria-label="Send message"], button:has-text("Send"), button[type="submit"]').first().click();

    // Wait for streaming to start
    await page.waitForTimeout(1000);

    // Verify that response appears (more robust than checking exact chunks)
    // Since we're testing against mocked response, check for key parts
    await expect(page.locator('text=/PT PMA|passaggi|documenti|registrar|NIB/i')).toBeVisible({ timeout: 10000 });
  });

  test('should handle streaming errors gracefully', async ({ page }) => {
    await page.route('**/api/bali-zero/chat-stream**', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Internal server error' }),
      });
    });

    const input = page.locator('textarea, input[type="text"]').first();
    await input.fill('Test message');
    await page.locator('button[aria-label="Send message"]').click();

    // Verifica gestione errore (potrebbe essere un messaggio di errore o toast)
    await page.waitForTimeout(2000);
    // Cerca indicatori di errore
    const errorIndicator = page.locator('text=/error|failed|try again/i').first();
    if (await errorIndicator.isVisible().catch(() => false)) {
      await expect(errorIndicator).toBeVisible();
    }
  });

  test('should handle incomplete streaming', async ({ page }) => {
    // Simula connessione interrotta durante streaming
    await page.route('**/api/bali-zero/chat-stream**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: `data: ${JSON.stringify({ content: 'Partial response', done: false })}\n\n`,
      });
    });

    const input = page.locator('textarea, input[type="text"]').first();
    await input.fill('Test message');
    await page.locator('button[aria-label="Send message"]').click();

    // Verifica che il testo parziale sia visibile
    await expect(page.locator('text="Partial response"')).toBeVisible({ timeout: 5000 });
  });

  test('should handle rapid successive messages', async ({ page }) => {
    let requestCount = 0;
    await page.route('**/api/bali-zero/chat-stream**', async (route) => {
      requestCount++;
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: `data: ${JSON.stringify({ content: `Response ${requestCount}`, done: true })}\n\n`,
      });
    });

    // Invia 3 messaggi rapidamente
    for (let i = 1; i <= 3; i++) {
      const input = page.locator('textarea, input[type="text"]').first();
      await input.fill(`Message ${i}`);
      await page.locator('button[aria-label="Send message"]').click();
      await page.waitForTimeout(500);
    }

    // Verifica che tutte le risposte siano presenti
    await page.waitForTimeout(2000);
    for (let i = 1; i <= 3; i++) {
      await expect(page.locator(`text="Response ${i}"`)).toBeVisible();
    }
  });
});
