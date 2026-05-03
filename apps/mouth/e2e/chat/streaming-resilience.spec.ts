import { test, expect } from '@playwright/test';

/**
 * E2E coverage for the streaming resilience layer added in
 * `feat(chat): streaming resilience v2 + session continuity + tool-use UI`.
 *
 * Three scenarios mirror the brief:
 *   1. happy path  — single SSE response renders fully
 *   2. mid-stream drop — server closes after a few tokens; user sees an
 *      error/retry surface (toast or inline banner)
 *   3. refresh resume — after sending a turn, reload should restore the
 *      conversation instantly from the localStorage snapshot
 */

const STREAM_GLOB = '**/api/agentic-rag/stream**';
const HISTORY_GLOB = '**/api/bali-zero/conversations/history**';

const buildSseBody = (events: Array<{ type: string; data?: unknown; content?: string }>) => {
  return events
    .map((evt) => `data: ${JSON.stringify(evt)}\n\n`)
    .concat(['data: [DONE]\n\n'])
    .join('');
};

async function login(page: import('@playwright/test').Page) {
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
      body: JSON.stringify({ success: true, messages: [], total_messages: 0 }),
    });
  });

  await page.goto('/login');
  await page.fill('input#email, input[name="email"]', 'test@balizero.com');
  await page.fill('input#pin, input[name="pin"]', '123456');
  await page.click('button[type="submit"]');
  await page.waitForURL('/chat');
}

test.describe('Streaming resilience', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

  test('happy path: full streamed response renders', async ({ page }) => {
    await page.route(STREAM_GLOB, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        headers: { 'Cache-Control': 'no-cache', Connection: 'keep-alive' },
        body: buildSseBody([
          { type: 'token', data: 'Hello' },
          { type: 'token', data: 'Hello, ' },
          { type: 'token', data: 'Hello, world!' },
        ]),
      });
    });

    await page.locator('textarea, input[type="text"]').first().fill('Say hello');
    await page.locator('button[aria-label="Send message"], button[type="submit"]').first().click();

    await expect(page.locator('text=Hello, world!')).toBeVisible({
      timeout: 8000,
    });
  });

  test('mid-stream drop surfaces an error/retry signal', async ({ page }) => {
    let attempts = 0;
    await page.route(STREAM_GLOB, async (route) => {
      attempts += 1;
      // Drop the connection after sending a single token.
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: `data: ${JSON.stringify({ type: 'token', data: 'Started…' })}\n\n`,
      });
    });

    await page.locator('textarea, input[type="text"]').first().fill('Trigger drop');
    await page.locator('button[aria-label="Send message"], button[type="submit"]').first().click();

    // The partial token shows up first.
    await expect(page.locator('text=Started…')).toBeVisible({ timeout: 8000 });

    // Once the response ends without [DONE] the client surfaces an error.
    // Accept either a toast or an inline indicator (text varies by locale).
    const errorSurface = page.locator('text=/timeout|connection|error|riprova|try again|please/i');
    await expect(errorSurface.first()).toBeVisible({ timeout: 12000 });
    expect(attempts).toBeGreaterThanOrEqual(1);
  });

  test('refresh restores the snapshot from localStorage', async ({ page }) => {
    await page.route(STREAM_GLOB, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: buildSseBody([
          { type: 'token', data: 'Cached ' },
          { type: 'token', data: 'Cached answer body.' },
        ]),
      });
    });

    await page.locator('textarea, input[type="text"]').first().fill('Cache me');
    await page.locator('button[aria-label="Send message"], button[type="submit"]').first().click();

    await expect(page.locator('text=Cached answer body.')).toBeVisible({
      timeout: 8000,
    });

    // Reload — the snapshot under bz_chat_session_<email> should paint
    // synchronously, and the subsequent history call (mocked empty) should
    // NOT replace it with nothing.
    await page.reload();
    await expect(page.locator('text=Cache me')).toBeVisible({ timeout: 4000 });
    await expect(page.locator('text=Cached answer body.')).toBeVisible({
      timeout: 4000,
    });
  });
});
