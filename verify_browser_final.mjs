import { chromium } from 'playwright';
import path from 'path';

async function run() {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const htmlPath = `file://${path.join(process.cwd(), 'apps', 'mouth', 'public', 'kbli-navigator', 'index.html')}`;

  console.log('🌐 Loading KBLI Navigator...');
  await page.goto(htmlPath);

  await page.evaluate(() => {
    document.body.style.opacity = '1';
    const nav = document.querySelector('.bottom-nav');
    if (nav) nav.style.display = 'block';
  });

  console.log('💬 Opening Zantara Chat...');
  await page.click('.bottom-nav button:last-child');
  
  console.log('⌨️ Sending Query: "Cosa serve per KBLI 55101?"');
  await page.fill('#chat-input', 'Cosa serve per KBLI 55101?');
  await page.click('#chat-send');

  console.log('⏳ Waiting for AI Response...');
  try {
    await page.waitForSelector('.typing-dots', { state: 'hidden', timeout: 15000 });
  } catch (e) {
    console.log('Timeout waiting for response, proceeding anyway...');
  }

  const responseText = await page.innerText('.msg-a:last-child div');
  console.log('\n--- AI RESPONSE ---');
  console.log(responseText);
  console.log('-------------------\n');

  const cardCount = await page.locator('.kbli-card-mini').count();
  console.log(`KBLI Cards rendered: ${cardCount}`);

  if (cardCount > 0) {
    console.log('🖱️ Clicking KBLI Card...');
    await page.click('.kbli-card-mini:first-child');
    const isFinderActive = await page.evaluate(() => document.getElementById('sec-finder').classList.contains('active'));
    const detailCode = await page.innerText('#detail-code');
    console.log(`Navigation to Finder successful: ${isFinderActive}`);
    console.log(`Finder showing code: ${detailCode}`);
  }

  await browser.close();
  console.log('\n✅ Test Completed.');
}

run().catch(console.error);
