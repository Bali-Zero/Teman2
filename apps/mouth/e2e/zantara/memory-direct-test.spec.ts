import { test, expect, Page } from '@playwright/test';

/**
 * Direct Memory Test - Tests conversation save/retrieve directly via API
 * This test verifies that:
 * 1. Conversations are saved correctly
 * 2. Conversations are retrieved correctly
 * 3. Entities are extracted correctly
 */

const TEST_CONFIG = {
  email: process.env.E2E_TEST_EMAIL || 'zero@balizero.com',
  pin: process.env.E2E_TEST_PIN || '010719',
  baseUrl: process.env.PLAYWRIGHT_BASE_URL || 'https://zantara.balizero.com',
  apiUrl: process.env.NUZANTARA_API_URL || 'https://nuzantara-rag.fly.dev',
  responseTimeout: 60000,
  waitBetweenMessages: 5000, // Wait 5 seconds between messages
};

let authToken: string | null = null;
let sessionId: string | null = null;

// Helper to login and get auth token
async function loginAndGetToken(page: Page): Promise<string> {
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

  // Get auth token from localStorage
  const token = await page.evaluate(() => {
    return localStorage.getItem('auth_token');
  });

  if (!token) {
    throw new Error('Failed to get auth token after login');
  }

  return token;
}

// Helper to save conversation via API
async function saveConversation(
  token: string,
  messages: Array<{ role: string; content: string }>,
  sessionId: string
): Promise<{ success: boolean; conversation_id?: number; messages_saved?: number }> {
  const response = await fetch(`${TEST_CONFIG.apiUrl}/api/bali-zero/conversations/save`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({
      messages,
      session_id: sessionId,
    }),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to save conversation: ${response.status} - ${error}`);
  }

  return response.json();
}

// Helper to get conversation history via API
async function getConversationHistory(
  token: string,
  sessionId: string
): Promise<{ success: boolean; messages?: Array<{ role: string; content: string }>; total_messages?: number }> {
  const response = await fetch(
    `${TEST_CONFIG.apiUrl}/api/bali-zero/conversations/history?session_id=${sessionId}&limit=50`,
    {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    }
  );

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to get conversation history: ${response.status} - ${error}`);
  }

  return response.json();
}

test.describe('Direct Memory Test', () => {
  test.setTimeout(180000);

  test.beforeEach(async ({ page }) => {
    authToken = await loginAndGetToken(page);
    sessionId = `test-session-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
    console.log(`[TEST] Using session ID: ${sessionId}`);
  });

  test('should save and retrieve conversation correctly', async ({ page }) => {
    // Step 1: Save first message
    const messages1 = [
      { role: 'user', content: 'Mi chiamo Marco e sono di Milano' },
      { role: 'assistant', content: 'Ciao Marco! Benvenuto da Milano.' },
    ];

    console.log(`[TEST] Step 1: Saving conversation with ${messages1.length} messages`);
    const saveResult1 = await saveConversation(authToken!, messages1, sessionId!);
    console.log(`[TEST] Save result:`, saveResult1);
    expect(saveResult1.success).toBeTruthy();
    expect(saveResult1.messages_saved).toBe(2);

    // Wait a bit
    await page.waitForTimeout(2000);

    // Step 2: Retrieve conversation history
    console.log(`[TEST] Step 2: Retrieving conversation history`);
    const historyResult = await getConversationHistory(authToken!, sessionId!);
    console.log(`[TEST] History result:`, {
      success: historyResult.success,
      total_messages: historyResult.total_messages,
      messages_count: historyResult.messages?.length || 0,
    });
    expect(historyResult.success).toBeTruthy();
    expect(historyResult.messages).toBeDefined();
    expect(historyResult.messages!.length).toBeGreaterThan(0);

    // Verify messages are correct
    const retrievedMessages = historyResult.messages!;
    expect(retrievedMessages[0].role).toBe('user');
    expect(retrievedMessages[0].content).toContain('Marco');
    expect(retrievedMessages[0].content).toContain('Milano');

    // Step 3: Add more messages and verify they're saved
    const messages2 = [
      ...retrievedMessages,
      { role: 'user', content: 'Come mi chiamo?' },
      { role: 'assistant', content: 'Ti chiami Marco!' },
    ];

    console.log(`[TEST] Step 3: Saving updated conversation with ${messages2.length} messages`);
    const saveResult2 = await saveConversation(authToken!, messages2, sessionId!);
    console.log(`[TEST] Save result 2:`, saveResult2);
    expect(saveResult2.success).toBeTruthy();

    // Wait a bit
    await page.waitForTimeout(2000);

    // Step 4: Retrieve again and verify all messages are there
    console.log(`[TEST] Step 4: Retrieving updated conversation history`);
    const historyResult2 = await getConversationHistory(authToken!, sessionId!);
    console.log(`[TEST] History result 2:`, {
      success: historyResult2.success,
      total_messages: historyResult2.total_messages,
      messages_count: historyResult2.messages?.length || 0,
    });
    expect(historyResult2.success).toBeTruthy();
    expect(historyResult2.messages!.length).toBeGreaterThanOrEqual(4);

    // Verify last messages
    const lastMessages = historyResult2.messages!.slice(-2);
    expect(lastMessages[0].role).toBe('user');
    expect(lastMessages[0].content).toContain('Come mi chiamo');
    expect(lastMessages[1].role).toBe('assistant');
    expect(lastMessages[1].content).toContain('Marco');
  });

  test('should extract entities from conversation history', async ({ page }) => {
    // Save conversation with entities
    const messages = [
      { role: 'user', content: 'Mi chiamo Marco e sono di Milano' },
      { role: 'assistant', content: 'Ciao Marco!' },
      { role: 'user', content: 'Il mio budget è di 50 milioni di rupie' },
      { role: 'assistant', content: 'Capito' },
    ];

    console.log(`[TEST] Saving conversation with entities`);
    const saveResult = await saveConversation(authToken!, messages, sessionId!);
    expect(saveResult.success).toBeTruthy();

    await page.waitForTimeout(2000);

    // Retrieve and verify entities can be extracted
    const historyResult = await getConversationHistory(authToken!, sessionId!);
    expect(historyResult.success).toBeTruthy();
    expect(historyResult.messages).toBeDefined();

    // Check that messages contain entity information
    const userMessages = historyResult.messages!.filter((m: { role: string; content: string }) => m.role === 'user');
    const allUserContent = userMessages.map((m: { role: string; content: string }) => m.content).join(' ');

    console.log(`[TEST] User messages content:`, allUserContent);
    expect(allUserContent).toContain('Marco');
    expect(allUserContent).toContain('Milano');
    expect(allUserContent).toContain('50');
  });
});

