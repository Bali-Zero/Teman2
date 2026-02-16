import { chromium } from 'playwright';
import path from 'path';

async function run() {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const htmlPath = `file://${path.join(process.cwd(), 'apps', 'mouth', 'public', 'kbli-navigator', 'index.html')}`;

  console.log('🌐 Loading Navigator...');
  await page.goto(htmlPath);

  console.log('🧹 Removing any overlays...');
  await page.evaluate(() => {
    // Remove everything that might block clicks
    const overlays = document.querySelectorAll('[class*="overlay"], [class*="intro"], [class*="splash"]');
    overlays.forEach(o => o.remove());
    document.body.style.opacity = '1';
    document.body.style.visibility = 'visible';
    // Make nav items visible
    const nav = document.querySelector('.bottom-nav');
    if (nav) nav.style.display = 'block';
  });

  console.log('💬 Clicking Zantara button via JS...');
  await page.evaluate(() => {
    // Call the global function directly since we can't click a hidden element
    if (typeof openChat === 'function') openChat();
  });

  console.log('⏳ Waiting for chat input...');
  const chatInput = page.locator('#chat-input');
  await chatInput.waitFor({ state: 'visible', timeout: 5000 });

  console.log('⌨️ Typing: "KBLI 55101"');
  await chatInput.fill('Parlami del KBLI 55101');
  await page.click('#chat-send');

  console.log('⏳ Waiting for Zantara Expert response...');
  // Check every second for the response
  let found = false;
  for(let i=0; i<20; i++) {
    const html = await page.locator('#chat-msgs').innerHTML();
    if (html.includes('PP 28/2025')) {
      console.log('\n--- AI RESPONSE DETECTED ---');
      const lastMsg = await page.locator('.msg-a:last-child').innerText();
      console.log(lastMsg);
      console.log('----------------------------\n');
      found = true;
      break;
    }
    await new Promise(r => setTimeout(r, 1000));
  }

  if (found) {
    console.log('✅ SUCCESS: Zantara AI is LIVE and EXPERT!');
  } else {
    console.log('❌ FAILURE: AI response not found or not enriched.');
    const fullHtml = await page.locator('#chat-msgs').innerHTML();
    console.log('Debug Chat HTML:', fullHtml);
  }

  await browser.close();
}

run().catch(console.error);
