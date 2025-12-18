import { test, expect, Page } from '@playwright/test';

const TEST_CONFIG = {
  email: process.env.E2E_TEST_EMAIL || 'zero@balizero.com',
  pin: process.env.E2E_TEST_PIN || '010719',
  baseUrl: 'https://zantara.balizero.com',
};

test.describe('Zantara Surf Camp Analysis (Gemini 3 Pro)', () => {
  test.setTimeout(120000); // 2 mins for Deep Thinking

  test('Reasoning on Surf School setup', async ({ page }) => {
    // 1. Login
    await page.goto(`${TEST_CONFIG.baseUrl}/login`);
    await page.getByPlaceholder('email').fill(TEST_CONFIG.email);
    await page.getByPlaceholder('PIN').fill(TEST_CONFIG.pin);
    await page.getByRole('button', { name: /Sign in/i }).click();
    await page.waitForURL('**/chat');

    // 2. Clear previous chat if needed (Clean slate for reasoning)
    // Optional: click 'New Chat' if available
    try {
      await page.getByRole('button', { name: 'New Chat' }).click({ timeout: 2000 });
    } catch (e) {
      // Ignore if not found
    }

    // 3. Ask the Complex Question
    const question =
      'Voglio aprire una scuola di surf a Canggu. 1. Posso usare un Virtual Office? 2. Che visto serve ai miei 2 istruttori australiani? 3. Capitale minimo versato? Usa KBLI corretti.';

    await page.locator('textarea, input[type="text"]').last().fill(question);
    await page
      .locator('button')
      .filter({ has: page.locator('svg') })
      .last()
      .click();

    // 4. Trace the "Moves" (Watch for status updates or response)
    console.log('Question sent. Waiting for reasoning...');

    // Wait for response bubble to start appearing
    const prose = page.locator('.prose').last();
    await expect(prose).toBeVisible({ timeout: 60000 });

    // Wait for generation to finish (bold text implies parsing done)
    await expect(prose).not.toBeEmpty();
    await page.waitForTimeout(10000); // Allow stream to complete

    // 5. Capture the "Brain Output"
    const responseText = await prose.textContent();
    console.log('\n====== ZANTARA RESPONSE (GEMINI 3 PRO) ======\n');
    console.log(responseText);
    console.log('\n=============================================\n');

    // 6. Capture Sources (The RAG "Moves")
    const sourcePills = page.locator(
      '[class*="inline-flex"][class*="items-center"][class*="bg-[var(--accent)]"]'
    );
    const sourceCount = await sourcePills.count();
    console.log(`Sources Cited: ${sourceCount}`);

    for (let i = 0; i < sourceCount; i++) {
      const sourceText = await sourcePills.nth(i).textContent();
      console.log(`- Source ${i + 1}: ${sourceText}`);
    }

    // 7. Verification Assertions (Did it beat Deepseek?)
    // Deepseek failed on: Virtual Office logic & Capital
    // Zantara SHOULD mention:
    // - KBLI 85410/85420 (Education/Sports) or 93293 (Recreation)
    // - Virtual Office restriction for Tourism/Physical activities
    // - Capital: 10 Billion IDR (PMA)
    // - Visas: E31A/C312 (Work KITAS) - NO Tourist/VOA

    expect(responseText).toContain('10 Miliar'); // Capital
    expect(responseText).toContain('KITAS'); // Visa
    expect(responseText?.toLowerCase()).toContain('australian'); // Context check

    // Virtual Office check (It should likely say NO or Warning)
    if (responseText?.includes('Virtual Office')) {
      console.log('Virtual Office addressed.');
    }

    await page.screenshot({ path: 'surf-camp-reasoning.png', fullPage: true });
  });
});
