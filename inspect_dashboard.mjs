import { chromium } from 'playwright';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  await page.goto('https://zantara.balizero.com', { waitUntil: 'networkidle' });
  await page.fill('input[type="email"]', 'zero@balizero.com');
  await page.fill('input[type="password"]', '010719');
  await page.click('button[type="submit"]');
  await page.waitForNavigation({ waitUntil: 'networkidle' });

  console.log('--- DASHBOARD CONTENT ---');
  const bodyText = await page.innerText('body');
  console.log(bodyText);
  
  // Look for specific elements like client lists, stats, or KBLI related info
  const h1s = await page.$$eval('h1', nodes => nodes.map(n => n.innerText));
  const h2s = await page.$$eval('h2', nodes => nodes.map(n => n.innerText));
  console.log('Headers H1:', h1s);
  console.log('Headers H2:', h2s);

  // Take a high-res screenshot of the dashboard sections
  await page.setViewportSize({ width: 1280, height: 2000 });
  await page.screenshot({ path: 'zantara_dashboard_full.png', fullPage: true });

  await browser.close();
})();
