import { test, expect } from '@playwright/test';

test.describe('Chat Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Mock Auth
    await page.addInitScript(() => {
      localStorage.setItem('auth_token', 'mock-token');
      localStorage.setItem(
        'user_profile',
        JSON.stringify({ name: 'Test User', email: 'test@example.com' })
      );
    });

    // Mock Profile
    await page.route('**/api/users/me', async (route) => {
      await route.fulfill({ json: { name: 'Test User', email: 'test@example.com' } });
    });

    // Mock Conversations List
    await page.route('**/api/conversations', async (route) => {
      await route.fulfill({ json: { success: true, conversations: [] } });
    });

    // Mock Team Status
    await page.route('**/api/team/status', async (route) => {
      await route.fulfill({ json: { success: true, is_clocked_in: true } });
    });

    await page.goto('/chat');
  });

  test('should send text message and receive streaming response', async ({ page }) => {
    // Mock Stream
    await page.route('**/api/agentic-rag/stream', async (route) => {
      const chunks = [
        'data: {"type": "token", "content": "Hello"}\n\n',
        'data: {"type": "token", "content": " world"}\n\n',
        'data: {"type": "token", "content": "!"}\n\n',
        'data: [DONE]\n\n',
      ];
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: chunks.join(''),
      });
    });

    // Type and send message
    await page.fill('textarea[placeholder="Type your message..."]', 'Hello');
    await page.keyboard.press('Enter');

    // Check user message
    await expect(page.getByText('Hello', { exact: true })).toBeVisible();

    // Check assistant response
    await expect(page.getByText('Hello world!')).toBeVisible();
  });

  test('should generate image', async ({ page }) => {
    // Mock Image Gen
    await page.route('**/api/v1/image/generate', async (route) => {
      await route.fulfill({
        json: { success: true, images: ['https://placehold.co/600x400'] },
      });
    });

    // Open attach menu
    await page.click('button[aria-label="Attach file"]');
    await page.click('text=Generate image');

    // Verify placeholder changed
    await expect(page.locator('textarea[placeholder="Describe your image..."]')).toBeVisible();

    // Type prompt
    await page.fill('textarea[placeholder="Describe your image..."]', 'A cute cat');
    await page.click('button[aria-label="Generate image"]');

    // Verify user message
    await expect(page.getByText('Generate image: A cute cat')).toBeVisible();

    // Verify text first
    await expect(page.getByText('Here is your generated image:')).toBeVisible({ timeout: 10000 });

    // Verify image
    // The alt text in MessageBubble is "Generated content"
    await expect(page.locator('img[alt="Generated content"]')).toBeVisible({ timeout: 10000 });
  });
});
