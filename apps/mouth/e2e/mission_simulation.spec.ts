import { test, expect } from '@playwright/test';

// Configuration for the mission
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || 'https://zantara.balizero.com';
const USER_EMAIL = 'zero@balizero.com';
const USER_PIN = '010719';

test.describe('Nuzantara Mission Simulation', () => {
  // Use a dedicated browser context for the session
  test.use({
    storageState: undefined, // Ensure clean state
    baseURL: BASE_URL,
  });

  test('Complete Mission: Login -> Dashboard -> Chat -> Blog', async ({ page }) => {
    // 1. LOGIN
    console.log(`🚀 [Mission] Navigating to ${BASE_URL}...`);
    await page.goto(`${BASE_URL}/login`);

    // Wait for login form
    await page.waitForSelector('input[name="email"]');
    
    console.log('🔑 [Mission] Entering credentials...');
    await page.fill('input[name="email"]', USER_EMAIL);
    await page.fill('input[name="pin"]', USER_PIN);
    
    // Submit
    await page.click('button[type="submit"]');

    // 2. DASHBOARD NAVIGATION
    console.log('⏳ [Mission] Waiting for Dashboard...');
    // Wait for URL to change to dashboard or portal
    await page.waitForURL(/\/dashboard|\/portal/);
    
    const url = page.url();
    console.log(`✅ [Mission] Access Granted. Current URL: ${url}`);
    expect(url).toContain('/dashboard');

    // Analyze Dashboard Content
    console.log('📊 [Mission] Analyzing Dashboard...');
    // Wait for some content to load (e.g., stats cards)
    // Looking for text like "Active Cases" or similar based on dashboard component
    try {
        await page.waitForSelector('text=Active Cases', { timeout: 10000 });
        const activeCases = await page.locator('text=Active Cases').first().textContent();
        console.log(`   - Found Widget: ${activeCases}`);
    } catch (e) {
        console.log('   - "Active Cases" widget not found or timed out');
    }

    // Check for "AiPulseWidget" content (Zantara v6.0)
    try {
        const pulse = await page.locator('text=Zantara v6.0').count();
        if (pulse > 0) {
            console.log('   - Zantara v6.0 System Pulse is ACTIVE');
        }
    } catch (e) {}

    // 3. ZANTARA AI CHAT
    console.log('💬 [Mission] Entering Zantara AI Chat...');
    // Navigate to chat
    await page.goto(`${BASE_URL}/chat`);
    await page.waitForURL(/\/chat/);

    // Wait for chat input
    await page.waitForSelector('textarea');
    
    // Type a question
    const question = 'Ciao Zantara, dimmi lo stato attuale del sistema e quanti documenti hai in memoria.';
    console.log(`   - Asking: "${question}"`);
    await page.fill('textarea', question);
    await page.press('textarea', 'Enter');

    // Wait for response (streaming)
    console.log('⏳ [Mission] Waiting for AI response...');
    // Wait for a new message bubble to appear (assistant message)
    // We assume the user message appears first, then assistant
    // Assistant message bubbles usually have specific styling (e.g., different background or icon)
    // Based on code: assistant role messages have `bg-[#2a2a2a]` and border.
    
    // Let's wait for the response to contain some text or stop streaming
    // Simulating a wait since streaming is dynamic
    await page.waitForTimeout(5000); 

    const responses = await page.locator('.whitespace-pre-wrap').allTextContents();
    const lastResponse = responses[responses.length - 1];
    console.log(`🤖 [AI Response] (Partial/Full): ${lastResponse?.substring(0, 100)}...`);

    // 4. INSIGHTS / BLOG
    console.log('📰 [Mission] Navigating to Insights (Blog)...');
    await page.goto(`${BASE_URL}/insights`);
    await page.waitForURL(/\/insights/);

    // Analyze Blog
    console.log('   - Analyzing Articles...');
    await page.waitForSelector('article');
    const articleTitles = await page.locator('article h2, article h3').allTextContents();
    
    if (articleTitles.length > 0) {
        console.log(`   - Found ${articleTitles.length} articles.`);
        console.log(`   - Featured: "${articleTitles[0]}"`);
    } else {
        console.log('   - No articles found.');
    }

    console.log('✅ [Mission] Mission Complete.');
  });
});
