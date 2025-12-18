import { test, expect, Page } from '@playwright/test';

/**
 * Memory Debug Test Suite
 * Isolated tests to debug conversation memory issues
 */

const TEST_CONFIG = {
  email: process.env.E2E_TEST_EMAIL || 'zero@balizero.com',
  pin: process.env.E2E_TEST_PIN || '010719',
  baseUrl: process.env.PLAYWRIGHT_BASE_URL || 'https://zantara.balizero.com',
  responseTimeout: 60000,
  waitBetweenMessages: 3000, // Wait 3 seconds between messages to ensure save completes
};

// Helper to send message and wait for response
async function sendMessageAndWaitForResponse(
  page: Page,
  message: string,
  _timeout: number = TEST_CONFIG.responseTimeout
): Promise<string> {
  const input = page.locator('textarea[placeholder*="message"], input[placeholder*="message"], textarea').first();
  await input.fill(message);

  const sendButton = page.locator('button').filter({ has: page.locator('svg') }).last();
  await sendButton.click();

  await page.waitForTimeout(1000);

  let attempts = 0;
  let response = '';
  const maxAttempts = 30;

  while (attempts < maxAttempts) {
    attempts++;
    const proseContainers = await page.locator('.prose').all();

    for (const container of proseContainers) {
      const text = await container.textContent() || '';
      if (text.length > 20 && !text.includes(message)) {
        response = text;
      }
    }

    if (response.length > 30) {
      await page.waitForTimeout(3000);
      const updatedContainers = await page.locator('.prose').all();
      let updatedResponse = '';
      for (const container of updatedContainers) {
        const text = await container.textContent() || '';
        if (text.length > 20 && !text.includes(message)) {
          updatedResponse = text;
        }
      }

      if (updatedResponse.length > response.length) {
        response = updatedResponse;
        await page.waitForTimeout(2000);
      }
      break;
    }

    await page.waitForTimeout(2000);
  }

  console.log(`[TEST] User: "${message}"`);
  console.log(`[TEST] AI Response (${response.length} chars): "${response.substring(0, 300)}..."`);

  return response;
}

// Helper to check if response contains keywords
function responseContains(response: string, keywords: string[]): boolean {
  const lowerResponse = response.toLowerCase();
  return keywords.some((kw) => lowerResponse.includes(kw.toLowerCase()));
}

test.describe('Memory Debug Tests', () => {
  test.setTimeout(180000); // 3 minutes

  test.beforeEach(async ({ page }) => {
    await page.goto(`${TEST_CONFIG.baseUrl}/login`);
    await page.waitForLoadState('domcontentloaded');

    const emailInput = page.locator('input[placeholder*="balizero"], input[type="email"], input').first();
    await emailInput.waitFor({ timeout: 15000 });
    await emailInput.fill(TEST_CONFIG.email);

    const pinInput = page.locator('input[placeholder*="PIN"], input[placeholder*="digit"], input[type="password"], input').nth(1);
    await pinInput.fill(TEST_CONFIG.pin);

    await page.locator('button:has-text("Sign in"), button[type="submit"]').click();
    await page.waitForURL('**/chat', { timeout: 30000 });
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);
  });

  test('should remember name across multiple turns', async ({ page }) => {
    // Turn 1: Provide name
    const response1 = await sendMessageAndWaitForResponse(page, 'Mi chiamo Marco');
    console.log('[TEST] Response 1:', response1.substring(0, 200));
    
    // Wait for conversation to be saved
    await page.waitForTimeout(TEST_CONFIG.waitBetweenMessages);
    
    // Turn 2: Ask about name
    const response2 = await sendMessageAndWaitForResponse(page, 'Come mi chiamo?');
    console.log('[TEST] Response 2:', response2.substring(0, 200));
    
    // Should contain "Marco"
    expect(responseContains(response2, ['Marco'])).toBeTruthy();
  });

  test('should remember city across multiple turns', async ({ page }) => {
    // Turn 1: Provide city
    const response1 = await sendMessageAndWaitForResponse(page, 'Sono di Milano');
    console.log('[TEST] Response 1:', response1.substring(0, 200));
    
    // Wait for conversation to be saved
    await page.waitForTimeout(TEST_CONFIG.waitBetweenMessages);
    
    // Turn 2: Ask about city
    const response2 = await sendMessageAndWaitForResponse(page, 'Di quale città sono?');
    console.log('[TEST] Response 2:', response2.substring(0, 500));
    
    // Should contain "Milano" or "Milan"
    const cityFound = responseContains(response2, ['Milano', 'Milan', 'milano', 'MILANO']);
    if (!cityFound) {
      console.error('[TEST] City not found. Full response:', response2);
    }
    expect(cityFound).toBeTruthy();
  });

  test('should remember both name and city', async ({ page }) => {
    // Turn 1: Provide both
    const response1 = await sendMessageAndWaitForResponse(page, 'Mi chiamo Marco e sono di Milano');
    console.log('[TEST] Response 1:', response1.substring(0, 200));
    
    // Wait for conversation to be saved
    await page.waitForTimeout(TEST_CONFIG.waitBetweenMessages);
    
    // Turn 2: Ask about name
    const response2 = await sendMessageAndWaitForResponse(page, 'Come mi chiamo?');
    console.log('[TEST] Response 2 (name):', response2.substring(0, 200));
    expect(responseContains(response2, ['Marco'])).toBeTruthy();
    
    // Wait again
    await page.waitForTimeout(TEST_CONFIG.waitBetweenMessages);
    
    // Turn 3: Ask about city
    const response3 = await sendMessageAndWaitForResponse(page, 'Di quale città sono?');
    console.log('[TEST] Response 3 (city):', response3.substring(0, 500));
    
    const cityFound = responseContains(response3, ['Milano', 'Milan', 'milano', 'MILANO']);
    if (!cityFound) {
      console.error('[TEST] City not found. Full response:', response3);
    }
    expect(cityFound).toBeTruthy();
  });

  test('should remember information after multiple unrelated messages', async ({ page }) => {
    // Turn 1: Provide information
    await sendMessageAndWaitForResponse(page, 'Mi chiamo Marco e sono di Milano');
    await page.waitForTimeout(TEST_CONFIG.waitBetweenMessages);
    
    // Turn 2: Unrelated question
    await sendMessageAndWaitForResponse(page, 'Cosa fa Bali Zero?');
    await page.waitForTimeout(TEST_CONFIG.waitBetweenMessages);
    
    // Turn 3: Another unrelated question
    await sendMessageAndWaitForResponse(page, 'Come funziona il visto per l\'Indonesia?');
    await page.waitForTimeout(TEST_CONFIG.waitBetweenMessages);
    
    // Turn 4: Ask about name
    const nameResponse = await sendMessageAndWaitForResponse(page, 'Come mi chiamo?');
    console.log('[TEST] Name response after unrelated messages:', nameResponse.substring(0, 200));
    expect(responseContains(nameResponse, ['Marco'])).toBeTruthy();
    
    await page.waitForTimeout(TEST_CONFIG.waitBetweenMessages);
    
    // Turn 5: Ask about city
    const cityResponse = await sendMessageAndWaitForResponse(page, 'Di quale città sono?');
    console.log('[TEST] City response after unrelated messages:', cityResponse.substring(0, 500));
    
    const cityFound = responseContains(cityResponse, ['Milano', 'Milan', 'milano', 'MILANO']);
    if (!cityFound) {
      console.error('[TEST] City not found. Full response:', cityResponse);
    }
    expect(cityFound).toBeTruthy();
  });
});

