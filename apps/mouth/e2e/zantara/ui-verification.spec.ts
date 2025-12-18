import { test, expect, Page } from '@playwright/test';

const TEST_CONFIG = {
  email: process.env.E2E_TEST_EMAIL || 'zero@balizero.com',
  pin: process.env.E2E_TEST_PIN || '010719',
  baseUrl: 'https://zantara.balizero.com',
};

async function login(page: Page) {
  await page.goto(`${TEST_CONFIG.baseUrl}/login`);
  await page.waitForLoadState('domcontentloaded');

  const emailInput = page.locator('input[type="email"], input[placeholder*="email"]').first();
  await emailInput.fill(TEST_CONFIG.email);

  const pinInput = page.locator('input[type="password"], input[placeholder*="PIN"]').first();
  await pinInput.fill(TEST_CONFIG.pin);

  await page.locator('button[type="submit"]').click();
  await page.waitForURL('**/chat', { timeout: 60000 });
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(2000);
}

test.describe('Zantara UI Integration & Valorization', () => {
  test.setTimeout(120000);

  test('Verify RAG Sources & Markdown Rendering', async ({ page }) => {
    await login(page);

    // Ask complex question to trigger RAG
    const question = 'Quali sono le imposte sui dividendi per una PT PMA?';
    const input = page.locator('textarea, input[placeholder*="message"]').first();
    await input.fill(question);

    const sendButton = page
      .locator('button')
      .filter({ has: page.locator('svg') })
      .last();
    await sendButton.click();

    // Wait for response - Deep Thinking/RAG can take 20s+ to start streaming
    await page.waitForTimeout(30000);

    // Evaluate "Valorization" elements

    // 1. Check for Markdown formatting (Bold text)
    // We expect the answer to contain some bold text like **Dividendi** or **10%**
    const prose = page.locator('.prose').last();
    await expect(prose).toBeVisible({ timeout: 60000 });
    // Text might stream in slowly, wait for meaningful content
    await expect(prose).not.toBeEmpty({ timeout: 60000 });

    // Wait for stream to likely finish or at least show structure
    await page.waitForTimeout(5000);

    // Check for bold content
    await expect(prose.locator('strong').first()).toBeVisible({ timeout: 60000 });

    // 2. Check for RAG Source Pills (The "Valorization")
    // Based on MessageBubble.tsx: text-xs text-[var(--accent)]
    // Usually contains "FileText" icon.
    // We look for the container of sources.
    const sourcePills = page.locator('.inline-flex.items-center.gap-1.px-2.py-1');
    // This selector targets the pill class structure seen in MessageBubble.tsx check

    // Wait for at least one source to appear
    await expect(sourcePills.first()).toBeVisible({ timeout: 10000 });

    // 3. Count sources
    const count = await sourcePills.count();
    console.log(`Found ${count} source citations in UI.`);
    expect(count).toBeGreaterThan(0);

    // 4. Capture screenshot for proof
    await page.screenshot({ path: 'ui-valorization-proof.png', fullPage: true });

    // 5. Log the text to verify quality
    const text = await prose.textContent();
    console.log('Response text:', text);
    expect(text).toContain('dividendi');
  });
});
