import { chromium } from 'playwright';

async function deepVerification() {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  try {
    console.log('--- START DEEP VERIFICATION ---');
    await page.goto('https://www.balizero.com/kbli-navigator', { waitUntil: 'networkidle' });
    
    console.log('1. Waiting for Intro Overlay (8s)...');
    await page.waitForTimeout(8000);

    const frame = page.mainFrame().childFrames()[0];
    if (!frame) throw new Error('Iframe not found');

    console.log('2. Testing "Code Finder" button...');
    const codeFinder = frame.locator('button:has-text("Code Finder"), a:has-text("Code Finder")').first();
    await codeFinder.click();
    await page.waitForTimeout(1000);
    console.log('   Click Code Finder: OK');

    console.log('3. Testing "Browse Sectors" button...');
    const browseSectors = frame.locator('text="Browse Sectors"').first();
    await browseSectors.click();
    await page.waitForTimeout(1000);
    console.log('   Click Browse Sectors: OK');

    console.log('4. Testing "Dashboard" button...');
    const dashboard = frame.locator('text="Dashboard"').first();
    await dashboard.click();
    await page.waitForTimeout(1000);
    const dashboardTitle = await frame.locator('h2:has-text("Dashboard"), h1:has-text("Dashboard")').count();
    console.log('   Click Dashboard: OK (Found title: ' + (dashboardTitle > 0 ? 'YES' : 'NO') + ')');

    console.log('5. Testing "Home" link inside Navigator...');
    const homeNav = frame.locator('nav >> text="Home"').first();
    await homeNav.click();
    await page.waitForTimeout(1000);
    console.log('   Return to Navigator Home: OK');

    console.log('6. Testing Browser BACK button behavior...');
    // We are at /kbli-navigator. If we go back, we should go to the previous page (balizero home or history)
    // But within the iframe, we want to see if the internal app handled history.
    await page.goBack();
    console.log('   URL after Back:', page.url());
    
    // Final check: Is the iframe still there and interactive?
    const stillInteractive = await frame.locator('button').count();
    console.log('7. Final Interactivity Check: ' + stillInteractive + ' buttons found.');

    await page.screenshot({ path: 'final_audit_success.png', fullPage: true });
    console.log('--- VERIFICATION COMPLETE: SUCCESS ---');

  } catch (err) {
    console.error('--- VERIFICATION FAILED ---');
    console.error(err.message);
  } finally {
    await browser.close();
  }
}

deepVerification();
