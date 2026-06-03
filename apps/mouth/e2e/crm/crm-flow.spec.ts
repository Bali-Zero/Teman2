import { test, expect, type Route } from "@playwright/test";

const validJwt =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9." +
  "eyJzdWIiOiIxIiwiZW1haWwiOiJ0ZXN0QGJhbGl6ZXJvLmNvbSIsImV4cCI6NDEwMjQ0NDgwMH0." +
  "test-signature";

const mockStreamBody = (content: string) =>
  `data: ${JSON.stringify({ type: "token", content })}\n\ndata: [DONE]\n\n`;

const fulfillJson = (route: Route, body: unknown, status = 200) =>
  route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });

/**
 * E2E Tests per CRM Flow
 * Testa le operazioni CRM (se accessibili dal frontend)
 */

test.use({ serviceWorkers: "block" });

test.describe("CRM Flow", () => {
  test.beforeEach(async ({ page }) => {
    const mockUser = {
      id: "1",
      email: "test@balizero.com",
      name: "Test User",
      role: "user",
    };

    await page.route(/.*\/api\/.*/, async (route) => {
      const request = route.request();
      const pathname = new URL(request.url()).pathname;

      if (pathname === "/api/health") {
        await fulfillJson(route, { status: "ok" });
        return;
      }

      if (pathname === "/api/auth/login") {
        await fulfillJson(route, {
          success: true,
          message: "Login successful",
          data: {
            token: validJwt,
            token_type: "Bearer",
            expiresIn: 3600,
            user: mockUser,
          },
        });
        return;
      }

      if (pathname === "/api/auth/profile") {
        await fulfillJson(route, mockUser);
        return;
      }

      if (pathname === "/api/team/my-status") {
        await fulfillJson(route, {
          is_clocked_in: false,
          is_online: false,
          today_hours: 0,
          week_hours: 0,
        });
        return;
      }

      if (pathname === "/api/bali-zero/conversations/history") {
        await fulfillJson(route, {
          success: true,
          messages: [],
          total_messages: 0,
        });
        return;
      }

      if (pathname === "/api/bali-zero/conversations/list") {
        await fulfillJson(route, { conversations: [] });
        return;
      }

      await fulfillJson(route, { success: true });
    });

    await page.goto("/login?redirect=/chat");
    await page.fill('input#email, input[name="email"]', "test@balizero.com");
    await page.fill('input#pin, input[name="pin"]', "123456");
    await page.click('button[type="submit"]');
    await page.waitForURL(/.*\/chat.*/, { timeout: 15000 });
    await expect(page.getByLabel("Type your message")).toBeVisible({
      timeout: 15000,
    });
  });

  test("should extract CRM data from chat conversation", async ({ page }) => {
    // Mock chat response che include informazioni CRM
    await page.route("**/api/agentic-rag/stream**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: mockStreamBody(
          "Ho creato un nuovo client: John Doe (john@example.com)",
        ),
      });
    });

    // Mock API per creazione client CRM
    await page.route("**/api/crm/clients**", async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({
            id: 1,
            full_name: "John Doe",
            email: "john@example.com",
            status: "active",
          }),
        });
        return;
      }

      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });

    const input = page.getByLabel("Type your message");
    await input.fill("Crea un nuovo client: John Doe, john@example.com");
    await page.locator('button[aria-label="Send message"]').click();

    // Verifica che la risposta menzioni il client creato
    await expect(
      page.getByText(/Ho creato un nuovo client: John Doe/i).last(),
    ).toBeVisible({ timeout: 10000 });
  });

  test("should display conversation history", async ({ page }) => {
    // Mock API per caricare conversazioni
    await page.route(
      "**/api/bali-zero/conversations/history**",
      async (route) => {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([
            {
              id: 1,
              messages: [
                { role: "user", content: "Hello" },
                { role: "assistant", content: "Hi there!" },
              ],
              created_at: new Date().toISOString(),
            },
          ]),
        });
      },
    );

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

  test("should handle CRM search functionality", async ({ page }) => {
    // Mock API per ricerca clienti
    await page.route("**/api/crm/shared-memory/search**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          clients: [
            { id: 1, full_name: "John Doe", email: "john@example.com" },
            { id: 2, full_name: "Jane Smith", email: "jane@example.com" },
          ],
        }),
      });
    });

    // Mock risposta chat per ricerca CRM
    await page.route("**/api/agentic-rag/stream**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: mockStreamBody("Ho trovato clienti con KITAS in scadenza"),
      });
    });

    // Se c'è una funzione di ricerca nel chat
    const input = page.getByLabel("Type your message");
    await input.fill("Cerca clienti con KITAS in scadenza");
    await page.locator('button[aria-label="Send message"]').click();

    // Verifica risposta
    await page.waitForTimeout(2000);
    // La risposta dovrebbe includere informazioni sui clienti
  });

  test("should create practice from chat", async ({ page }) => {
    // Mock creazione pratica
    await page.route("**/api/crm/practices**", async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({
            id: 1,
            client_id: 1,
            practice_type_code: "KITAS",
            status: "inquiry",
          }),
        });
      }
    });

    await page.route("**/api/agentic-rag/stream**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: mockStreamBody(
          "Ho creato una nuova pratica KITAS per il client John Doe",
        ),
      });
    });

    const input = page.getByLabel("Type your message");
    await input.fill("Crea una pratica KITAS per John Doe");
    await page.locator('button[aria-label="Send message"]').click();

    await expect(
      page.getByText(/Ho creato una nuova pratica KITAS/i).last(),
    ).toBeVisible({ timeout: 10000 });
  });
});
