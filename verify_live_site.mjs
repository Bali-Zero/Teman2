import { chromium } from 'playwright';

async function verifyLiveSite() {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const liveUrl = 'https://www.balizero.com/kbli-navigator'; 

  console.log(`🌐 Monitoring Live Site: ${liveUrl}`);
  try {
    const response = await page.goto(liveUrl, { waitUntil: 'networkidle', timeout: 60000 });
    console.log(`HTTP Status: ${response.status()}`);
    
    if (response.status() === 200) {
      console.log('✅ LIVE SITE IS UP!');
      const iframeVisible = await page.isVisible('#kbli-frame');
      console.log(`Iframe Navigator Visible: ${iframeVisible}`);
    } else {
      console.log(`❌ LIVE SITE ERROR: Status ${response.status()}`);
    }
  } catch (error) {
    console.error(`❌ Connection failed: ${error.message}`);
  }
  await browser.close();
}

verifyLiveSite().catch(console.error);
