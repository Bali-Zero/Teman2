import { chromium } from 'playwright';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  
  console.log('Navigating to https://zantara.balizero.com...');
  await page.goto('https://zantara.balizero.com', { waitUntil: 'networkidle' });
  
  // Take a screenshot of the home/login page
  await page.screenshot({ path: 'zantara_home.png' });
  console.log('Screenshot saved to zantara_home.png');
  
  // Look for login fields
  const content = await page.content();
  console.log('Page title:', await page.title());
  
  // Check for email/password fields
  const hasEmail = await page.$('input[type="email"]') !== null;
  const hasPassword = await page.$('input[type="password"]') !== null;
  console.log('Has email field:', hasEmail);
  console.log('Has password field:', hasPassword);

  if (hasEmail && hasPassword) {
    console.log('Attempting login...');
    await page.fill('input[type="email"]', 'zero@balizero.com');
    await page.fill('input[type="password"]', '010719');
    
    // Find and click login button
    const loginButton = await page.$('button[type="submit"]') || await page.$('text="Login"') || await page.$('text="Sign In"');
    if (loginButton) {
      await loginButton.click();
      await page.waitForNavigation({ waitUntil: 'networkidle' }).catch(() => console.log('Navigation timeout or already on dashboard'));
      
      console.log('Post-login URL:', page.url());
      console.log('Post-login Title:', await page.title());
      await page.screenshot({ path: 'zantara_dashboard.png' });
      console.log('Dashboard screenshot saved to zantara_dashboard.png');
    } else {
      console.log('Login button not found');
    }
  } else {
    console.log('Login fields not found. Checking for a "Login" link...');
    const loginLink = await page.$('text="Login"') || await page.$('a[href*="login"]');
    if (loginLink) {
      await loginLink.click();
      await page.waitForLoadState('networkidle');
      console.log('URL after clicking login link:', page.url());
      // Re-check fields
      await page.fill('input[type="email"]', 'zero@balizero.com');
      await page.fill('input[type="password"]', '010719');
      const submitBtn = await page.$('button[type="submit"]') || await page.$('text="Login"');
      if (submitBtn) {
        await submitBtn.click();
        await page.waitForNavigation({ waitUntil: 'networkidle' });
        console.log('Final URL:', page.url());
        await page.screenshot({ path: 'zantara_final.png' });
      }
    }
  }

  await browser.close();
})();
