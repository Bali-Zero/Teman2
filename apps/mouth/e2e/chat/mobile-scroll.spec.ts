import { test, expect, devices } from '@playwright/test';

const STREAM_GLOB = '**/api/agentic-rag/stream**';
const HISTORY_GLOB = '**/api/bali-zero/conversations/history**';

test.use({ ...devices['iPhone 14'] });

test.describe('Mobile scroll anchor', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/auth/login', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          message: 'Login successful',
          data: {
            token: 'mock-jwt',
            token_type: 'Bearer',
            expiresIn: 3600,
            user: {
              id: '1',
              email: 'test@balizero.com',
              name: 'Test User',
              role: 'user',
            },
          },
        }),
      });
    });
    await page.route('**/api/auth/profile', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: '1',
          email: 'test@balizero.com',
          name: 'Test User',
          role: 'user',
        }),
      });
    });
    await page.route(HISTORY_GLOB, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          messages: [],
          total_messages: 0,
        }),
      });
    });
    await page.goto('/login');
    await page.fill('input#email, input[name="email"]', 'test@balizero.com');
    await page.fill('input#pin, input[name="pin"]', '123456');
    await page.click('button[type="submit"]');
    await page.waitForURL('/chat');
  });

  test('scrolling up during stream pins the view and shows the pill', async ({ page }) => {
    // A long response so the message list has room to scroll inside the
    // viewport. Each chunk grows the bubble.
    const longChunks = Array.from(
      { length: 12 },
      (_, i) =>
        'Lorem ipsum dolor sit amet, consectetur adipiscing elit. '.repeat(6) + `Chunk ${i + 1}.`
    );

    await page.route(STREAM_GLOB, async (route) => {
      const body =
        longChunks
          .map(
            (acc, i) =>
              `data: ${JSON.stringify({
                type: 'token',
                data: longChunks.slice(0, i + 1).join(' '),
              })}\n\n`
          )
          .join('') + 'data: [DONE]\n\n';
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body,
      });
    });

    await page.locator('textarea, input[type="text"]').first().fill('Tell me a long story');
    await page.locator('button[aria-label="Send message"], button[type="submit"]').first().click();

    // Once we see the first chunk, scroll the chat pane to the top.
    await expect(page.locator('text=Lorem ipsum')).toBeVisible({
      timeout: 8000,
    });

    const chatLog = page.locator('[role="log"][aria-label="Chat messages"]');
    await chatLog.evaluate((el) => {
      el.scrollTop = 0;
    });

    // The pill should appear once the list grew while we were scrolled up.
    const pill = page.locator('[data-testid="new-messages-pill"]');
    await expect(pill).toBeVisible({ timeout: 8000 });

    // Click it: the list should jump to the bottom and the pill should hide.
    await pill.click();
    await expect(pill).toBeHidden({ timeout: 4000 });
  });
});
