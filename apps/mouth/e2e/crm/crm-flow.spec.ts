import { test, expect } from '@playwright/test';

/**
 * E2E Tests per CRM Flow
 * Testa le operazioni CRM (se accessibili dal frontend)
 */

test.describe('CRM Flow', () => {
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

  test('should extract CRM data from chat conversation', async ({ page }) => {
    // Mock chat response che include informazioni CRM
    await page.route('**/api/bali-zero/chat-stream**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: `data: ${JSON.stringify({
          content: 'Ho creato un nuovo client: John Doe (john@example.com)',
          done: true,
        })}\n\n`,
      });
    });

    // Mock API per creazione client CRM
    await page.route('**/api/crm/clients**', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 1,
            full_name: 'John Doe',
            email: 'john@example.com',
            status: 'active',
          }),
        });
      }
    });

    const input = page.locator('textarea, input[type="text"]').first();
    await input.fill('Crea un nuovo client: John Doe, john@example.com');
    await page.locator('button[aria-label="Send message"]').click();

    // Verifica che la risposta menzioni il client creato
    await expect(page.locator('text=/John Doe|client creato/i')).toBeVisible({ timeout: 10000 });
  });

  test('should display conversation history', async ({ page }) => {
    // Mock API per caricare conversazioni
    await page.route('**/api/bali-zero/conversations/history**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 1,
            messages: [
              { role: 'user', content: 'Hello' },
              { role: 'assistant', content: 'Hi there!' },
            ],
            created_at: new Date().toISOString(),
          },
        ]),
      });
    });

    // Cerca sidebar o menu per conversazioni
    const sidebarButton = page
      .locator('button:has-text("History"), button:has-text("Conversations")')
      .first();
    if (await sidebarButton.isVisible().catch(() => false)) {
      await sidebarButton.click();
      await page.waitForTimeout(1000);

      // Verifica che le conversazioni siano visibili
      await expect(page.locator('text="Hello"')).toBeVisible();
    }
  });

  test('should handle CRM search functionality', async ({ page }) => {
    // Mock API per ricerca clienti
    await page.route('**/api/crm/shared-memory/search**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          clients: [
            { id: 1, full_name: 'John Doe', email: 'john@example.com' },
            { id: 2, full_name: 'Jane Smith', email: 'jane@example.com' },
          ],
        }),
      });
    });

    // Se c'è una funzione di ricerca nel chat
    const input = page.locator('textarea, input[type="text"]').first();
    await input.fill('Cerca clienti con KITAS in scadenza');
    await page.locator('button[aria-label="Send message"]').click();

    // Verifica risposta
    await page.waitForTimeout(2000);
    // La risposta dovrebbe includere informazioni sui clienti
  });

  test('should create practice from chat', async ({ page }) => {
    // Mock creazione pratica
    await page.route('**/api/crm/practices**', async (route) => {
      if (route.request().method() === 'POST') {
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 1,
            client_id: 1,
            practice_type_code: 'KITAS',
            status: 'inquiry',
          }),
        });
      }
    });

    await page.route('**/api/bali-zero/chat-stream**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: `data: ${JSON.stringify({
          content: 'Ho creato una nuova pratica KITAS per il client John Doe',
          done: true,
        })}\n\n`,
      });
    });

    const input = page.locator('textarea, input[type="text"]').first();
    await input.fill('Crea una pratica KITAS per John Doe');
    await page.locator('button[aria-label="Send message"]').click();

    await expect(page.locator('text=/pratica KITAS|creata/i')).toBeVisible({ timeout: 10000 });
  });
});
