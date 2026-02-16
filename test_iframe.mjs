import { chromium } from 'playwright';

async function finalTest() {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  try {
    console.log('--- Loading KBLI Navigator (iframe fix) ---');
    await page.goto('https://www.balizero.com/kbli-navigator', { waitUntil: 'networkidle' });
    
    console.log('Waiting for overlay to disappear...');
    await page.waitForTimeout(7000);

    const frame = page.frame({ url: /index.html/ });
    if (frame) {
      console.log('✅ Iframe found. Testing internal click...');
      const dashboardLink = frame.locator('text="Dashboard"').first();
      if (await dashboardLink.isVisible()) {
        await dashboardLink.click();
        console.log('✅ Click inside iframe successful!');
      } else {
        console.log('❌ Dashboard link not found inside iframe');
      }
    } else {
      console.log('❌ Iframe NOT found');
    }

  } catch (err) {
    console.log('Error during final test:', err.message);
  } finally {
    await browser.close();
  }
}

finalTest();
