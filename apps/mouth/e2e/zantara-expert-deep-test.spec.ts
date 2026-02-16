import { test, expect } from '@playwright/test';
import path from 'path';

test.describe('Zantara AI Expert - Intense Browser Validation', () => {
  const htmlPath = `file://${path.join(process.cwd(), 'public', 'kbli-navigator', 'index.html')}`;

  test.beforeEach(async ({ page }) => {
    // Intercept backend calls to point to our local backend
    await page.route('**/api/v1/kbli-notebook/chat', async route => {
      // Mock directly for consistency in E2E
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          answer: "### 📋 Executive Brief: KBLI 55101\nIn base al **PP 28/2025**, per un Hotel 5 stelle serve il **Sertifikat Laik Sehat** e la licenza **SKPL**.",
          results: [{ code: "55101", title: "Hotel Bintang Lima", risk_category: "Menengah Tinggi" }],
          suggested_queries: ["Quali licenze servono?"]
        })
      });
    });

    await page.goto(htmlPath);
    
    // Handle Splash Screen
    const skipBtn = page.locator('button:has-text("Skip Intro")');
    if (await skipBtn.isVisible()) {
      await skipBtn.click();
    } else {
      // If skip button not visible, maybe wait for overlay to fade
      await page.waitForSelector('.intro-overlay', { state: 'hidden', timeout: 10000 }).catch(() => {});
    }

    await page.waitForSelector('.bottom-nav', { state: 'visible' });
  });

  test('Should render enriched AI response with Markdown and Cards', async ({ page }) => {
    // 1. Open Chat
    await page.click('button:has-text("Zantara")');
    await expect(page.locator('#sec-chat')).toHaveClass(/active/);

    // 2. Send Message
    const input = page.locator('#chat-input');
    await input.fill('Parlami del KBLI 55101');
    await page.click('#chat-send');

    // 3. Verify Content (Markdown Check)
    const aiMsg = page.locator('.msg-a').last();
    // In our index.html, formatMarkdown converts **text** to <strong>text</strong>
    await expect(aiMsg.locator('strong').first()).toContainText('PP 28/2025');
    await expect(aiMsg.locator('strong').nth(1)).toContainText('Sertifikat Laik Sehat');

    // 4. Verify KBLI Card
    const card = page.locator('.kbli-card-mini');
    await expect(card).toBeVisible();
    await expect(card).toContainText('55101');
    
    // 5. Test Card Interaction (Navigation to Finder)
    await card.click();
    await expect(page.locator('#sec-finder')).toHaveClass(/active/);
  });

  test('Should handle History Synchronization (Back Button)', async ({ page }) => {
    // This requires being in an iframe to test the actual sync logic I added, 
    // but we can test if showSection pushes to history.
    await page.click('button:has-text("Codes")');
    const state = await page.evaluate(() => window.history.state);
    expect(state.section).toBe('finder');
  });
});
