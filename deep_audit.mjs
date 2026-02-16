import { chromium } from 'playwright';

async function deepAudit() {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  try {
    const errors = [];
    page.on('pageerror', err => errors.push(err));
    page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });

    console.log('--- Loading Page ---');
    await page.goto('https://www.balizero.com/kbli-navigator', { waitUntil: 'networkidle' });
    
    console.log('Waiting for Overlay removal...');
    await page.waitForTimeout(8000); 

    console.log('Checking for pointer events on body...');
    const pointerEvents = await page.evaluate(() => window.getComputedStyle(document.body).pointerEvents);
    console.log('Body pointer-events:', pointerEvents);

    const overlayExists = await page.locator('div:has-text("Loading KBLI Navigator")').count();
    console.log('Overlay still in DOM?', overlayExists > 0 ? 'YES' : 'NO');

    console.log('Attempting to click "Dashboard"...');
    const dashboardBtn = page.locator('text="Dashboard"').first();
    const isVisible = await dashboardBtn.isVisible();
    console.log('Dashboard visible:', isVisible);
    
    if (isVisible) {
      await dashboardBtn.click({ timeout: 5000 });
      await page.waitForTimeout(2000);
      console.log('URL after click:', page.url());
      
      console.log('Testing Back Button...');
      await page.goBack();
      await page.waitForTimeout(2000);
      console.log('URL after Back:', page.url());
    }

    console.log('Errors found:', errors.length);
    errors.forEach(e => console.log('JS Error:', e));

  } catch (err) {
    console.log('Audit failed:', err.message);
  } finally {
    await browser.close();
  }
}

deepAudit();
