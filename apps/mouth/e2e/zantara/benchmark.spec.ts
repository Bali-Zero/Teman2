import { test, expect, Page } from '@playwright/test';

/**
 * ZANTARA BENCHMARK SUITE
 * 4 Complex Scenarios to compare against Global AI Models.
 */

const TEST_CONFIG = {
  email: process.env.E2E_TEST_EMAIL || 'zero@balizero.com',
  pin: process.env.E2E_TEST_PIN || '010719',
  baseUrl: 'https://zantara.balizero.com', // Production
};

// Helper to send message and grab full response
async function askZantara(page: Page, question: string): Promise<string> {
  // Input
  const input = page
    .locator('textarea[placeholder*="message"], input[placeholder*="message"], textarea')
    .first();
  await input.fill(question);

  // Send
  const sendButton = page
    .locator('button')
    .filter({ has: page.locator('svg') })
    .last();
  await sendButton.click();

  // Wait for response generation (allow up to 60s for deep RAG)
  await page.waitForTimeout(2000);

  // Wait until streaming stops (simple heuristic: no text change for 3s)
  let lastText = '';
  let stableCount = 0;

  while (stableCount < 3) {
    // Wait for 3 consecutive checks of stability
    const proseContainers = await page.locator('.prose').all();
    let currentText = '';
    // Get the LAST prose container (latest response)
    if (proseContainers.length > 0) {
      currentText = (await proseContainers[proseContainers.length - 1].textContent()) || '';
    }

    if (currentText.length > 20 && currentText === lastText) {
      stableCount++;
    } else {
      stableCount = 0;
    }
    lastText = currentText;
    await page.waitForTimeout(1000);
  }

  return lastText;
}

test.describe('Zantara Benchmark Challenge', () => {
  test.setTimeout(180000); // 3 mins total

  test.beforeEach(async ({ page }) => {
    // Real login (no mocking) - use full URL for production
    await page.goto(`${TEST_CONFIG.baseUrl}/login`);
    await page.waitForLoadState('domcontentloaded');

    // Wait for form to be visible - use placeholder text since name attribute may vary
    const emailInput = page
      .locator('input[placeholder*="balizero"], input[type="email"], input')
      .first();
    await emailInput.waitFor({ timeout: 15000 });

    // Fill email
    await emailInput.fill(TEST_CONFIG.email);

    // Fill PIN - look for PIN input by placeholder or position
    const pinInput = page
      .locator(
        'input[placeholder*="PIN"], input[placeholder*="digit"], input[type="password"], input'
      )
      .nth(1);
    await pinInput.fill(TEST_CONFIG.pin);

    // Click Sign in button
    await page.locator('button:has-text("Sign in"), button[type="submit"]').click();

    // Wait for redirect to chat
    await page.waitForURL('**/chat', { timeout: 60000 });
    await page.waitForLoadState('networkidle');

    // Additional wait for chat interface to load
    await page.waitForTimeout(2000);
  });

  // SCENARIO 1: IMMIGRATION (E33G Nuances)
  test('Immigration: E33G Dependents & KITAP', async ({ page }) => {
    const question =
      'Sono un nomade digitale con reddito 70k USD. Posso portare moglie e figlio col visto E33G? E posso convertirlo in KITAP dopo 5 anni?';
    console.log(`\n[QUESTION 1]: ${question}`);
    const answer = await askZantara(page, question);
    console.log(`[ZANTARA ANSWER]:\n${answer}\n-----------------------------------`);
  });

  // SCENARIO 2: KBLI (Glamping + alcohol + ownership)
  test('KBLI: Glamping & Restaurant Ownership', async ({ page }) => {
    const question =
      'Voglio aprire un Glamping di lusso a Ubud con ristorante che serve alcolici. Quali KBLI mi servono? Posso avere il 100% delle quote come straniero?';
    console.log(`\n[QUESTION 2]: ${question}`);
    const answer = await askZantara(page, question);
    console.log(`[ZANTARA ANSWER]:\n${answer}\n-----------------------------------`);
  });

  // SCENARIO 3: TAX (Dividend Withholding)
  test('Tax: Dividends & Treaties', async ({ page }) => {
    const question =
      'Ho una PT PMA. Se pago dividendi su conto estero (Italia), qual è la Withholding Tax esatta? Cambia se uso una holding a Singapore?';
    console.log(`\n[QUESTION 3]: ${question}`);
    const answer = await askZantara(page, question);
    console.log(`[ZANTARA ANSWER]:\n${answer}\n-----------------------------------`);
  });

  // SCENARIO 4: MULTI-TOPIC (Surf School)
  test('Multi: Surf School Setup', async ({ page }) => {
    const question =
      'Apro una scuola di surf a Canggu. 1. Posso usare un Virtual Office? 2. Che visto serve ai miei 2 istruttori australiani? 3. Capitale minimo versato?';
    console.log(`\n[QUESTION 4]: ${question}`);
    const answer = await askZantara(page, question);
    console.log(`[ZANTARA ANSWER]:\n${answer}\n-----------------------------------`);
  });
});
