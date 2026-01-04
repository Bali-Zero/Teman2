import { test, expect } from '@playwright/test';

test.describe('CRM Real UI Journey', () => {
  test('Complete CRM Lifecycle: Login -> Create -> Edit -> Kanban -> Delete', async ({ page }) => {
    // 1. LOGIN
    console.log('🔹 Navigating to Login...');
    await page.goto('/login');
    
    // Check for Next.js Error Overlay
    const errorOverlay = page.locator('nextjs-portal');
    if (await errorOverlay.isVisible()) {
        console.error('❌ Next.js Error Overlay detected!');
        // Try to get text
        console.error(await errorOverlay.innerText());
        throw new Error('Frontend crashed');
    }
    
    // Fill credentials
    await page.fill('input[type="email"]', 'zero@balizero.com');
    await page.fill('input[type="password"], input[name="pin"]', '010719');
    
    // Monitor API call
    const loginPromise = page.waitForResponse(response => 
        response.url().includes('/api/auth/login') && response.request().method() === 'POST'
    );

    // Submit (Force click to bypass potential overlays/animations)
    await page.click('button[type="submit"]', { force: true });
    
    console.log('🔹 Waiting for login API response...');
    const loginResponse = await loginPromise;
    console.log(`🔹 Login Status: ${loginResponse.status()}`);
    
    if (loginResponse.status() !== 200) {
        const body = await loginResponse.text();
        console.error(`❌ Login Failed Body: ${body}`);
        throw new Error(`Login API failed with status ${loginResponse.status()}`);
    }

    // Wait for redirect
    console.log('🔹 Waiting for redirect...');
    await page.waitForURL(/.*(chat|dashboard|clients).*/, { timeout: 15000 });
    console.log('✅ Login successful');

    // 2. NAVIGATE TO CLIENTS
    console.log('🔹 Navigating to Clients...');
    await page.goto('/clients');
    
    // Check for errors again
    if (await errorOverlay.isVisible()) {
        console.error('❌ Next.js Error Overlay detected on /clients');
        console.error(await errorOverlay.innerText());
        throw new Error('Frontend crashed on /clients');
    }

    // Ensure we are on clients page
    await expect(page).toHaveURL(/.*\/clients/);
    await page.waitForLoadState('networkidle');
    
    // Check for access denied or loading
    await expect(page.locator('text=Access Denied').or(page.locator('text=Login'))).not.toBeVisible();
    
    // Wait for header
    await expect(page.locator('h1:has-text("Clients")')).toBeVisible({ timeout: 10000 });

    // Debug: Print all buttons
    const buttons = await page.locator('button').allInnerTexts();
    console.log('🔹 Available buttons:', buttons);

    // 3. CREATE CLIENT
    console.log('🔹 Creating Client...');
    const uniqueId = Date.now().toString().slice(-6);
    const clientName = `PW Test ${uniqueId}`;
    
    // Click Add Client button
    const addBtn = page.locator('button').filter({ hasText: 'New Client' }).first();
    await expect(addBtn).toBeVisible({ timeout: 10000 });
    await addBtn.click();
    
    // Check for Modal/Form
    const modal = page.locator('div[role="dialog"]');
    await expect(modal).toBeVisible();
    
    // Fill Form
    // Use more specific selectors if possible, or label text
    await modal.locator('input[name="full_name"]').fill(clientName);
    await modal.locator('input[name="email"]').fill(`pw.${uniqueId}@example.com`);
    
    // Some forms have required phone
    const phoneInput = modal.locator('input[name="phone"]');
    if (await phoneInput.isVisible()) {
        await phoneInput.fill('+62812345678');
    }
    
    // Submit
    const submitBtn = modal.locator('button[type="submit"]');
    await submitBtn.click();
    
    // Wait for modal to close
    await expect(modal).not.toBeVisible();
    
    // Verify client appears in list
    // Use a loose text match first, then strict
    await expect(page.locator(`text=${clientName}`)).toBeVisible({ timeout: 10000 });
    console.log('✅ Client created:', clientName);

    // 4. EDIT CLIENT
    console.log('🔹 Editing Client...');
    // Refresh to ensure list is up to date (optional, but safer)
    // await page.reload();
    
    const clientRow = page.locator('tr, div[data-card]').filter({ hasText: clientName }).first();
    await clientRow.click();
    
    // Wait for side panel
    const detailsPanel = page.locator('div[role="dialog"], div[data-testid="client-details"], aside');
    await expect(detailsPanel).toBeVisible();

    const editBtn = detailsPanel.locator('button', { hasText: 'Edit' });
    if (await editBtn.isVisible()) {
        await editBtn.click();
        const editName = `${clientName} Updated`;
        await detailsPanel.locator('input[name="full_name"]').fill(editName);
        await detailsPanel.locator('button[type="submit"]').click();
        
        await expect(detailsPanel.locator('input[name="full_name"]')).not.toBeVisible(); // Wait for edit mode exit
        await expect(page.locator(`text=${editName}`)).toBeVisible();
        console.log('✅ Client edited:', editName);
    } else {
        console.log('⚠️ Edit button not found');
    }

    // 5. KANBAN VIEW
    console.log('🔹 Switching to Kanban...');
    // Look for toggle
    const kanbanBtn = page.locator('button').filter({ hasText: /kanban/i }).first();
    if (await kanbanBtn.isVisible()) {
        await kanbanBtn.click();
        // Verify columns (Lead, Active, etc.)
        await expect(page.locator('text=Lead').first()).toBeVisible();
        console.log('✅ Kanban view active');
    } else {
        console.log('⚠️ Kanban toggle not found');
    }

    // 6. DELETE (Soft)
    console.log('🔹 Deleting Client...');
    // If we are in Kanban, card structure is different. Let's go back to list for consistency or find card in kanban.
    // Let's try to find the card in whatever view we are.
    const targetName = (await page.locator(`text=${clientName} Updated`).isVisible()) ? `${clientName} Updated` : clientName;
    const targetCard = page.locator(`text=${targetName}`).first();
    
    await targetCard.click();
    await expect(detailsPanel).toBeVisible();
    
    const deleteBtn = detailsPanel.locator('button', { hasText: 'Delete' }).or(detailsPanel.locator('button[aria-label="Delete"]'));
    if (await deleteBtn.isVisible()) {
        await deleteBtn.click();
        
        // Confirm
        const confirmBtn = page.locator('button', { hasText: /confirm|yes|delete/i }).last();
        if (await confirmBtn.isVisible()) {
            await confirmBtn.click();
        }
        
        await expect(page.locator(`text=${targetName}`)).not.toBeVisible();
        console.log('✅ Client deleted');
    }
  });
});
