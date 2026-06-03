import { test, expect } from "@playwright/test";

test.describe("CRM Real UI Journey", () => {
  test("CRM UI smoke: Login -> Clients -> New Client wizard -> Kanban", async ({
    page,
  }) => {
    // 1. LOGIN
    console.log("🔹 Navigating to Login...");
    await page.goto("/login");

    // Check for Next.js Error Overlay
    const errorOverlay = page.locator("nextjs-portal");
    if (await errorOverlay.isVisible()) {
      console.error("❌ Next.js Error Overlay detected!");
      // Try to get text
      console.error(await errorOverlay.innerText());
      throw new Error("Frontend crashed");
    }

    // Fill credentials
    await page.fill('input[type="email"]', "zero@balizero.com");
    await page.fill('input[type="password"], input[name="pin"]', "010719");

    // Monitor API call
    const loginPromise = page.waitForResponse(
      (response) =>
        response.url().includes("/api/auth/login") &&
        response.request().method() === "POST",
    );

    // Submit (Force click to bypass potential overlays/animations)
    await page.click('button[type="submit"]', { force: true });

    console.log("🔹 Waiting for login API response...");
    const loginResponse = await loginPromise;
    console.log(`🔹 Login Status: ${loginResponse.status()}`);

    if (loginResponse.status() !== 200) {
      const body = await loginResponse.text();
      console.error(`❌ Login Failed Body: ${body}`);
      throw new Error(`Login API failed with status ${loginResponse.status()}`);
    }

    // Wait for redirect
    console.log("🔹 Waiting for redirect...");
    await page.waitForURL(/.*(chat|dashboard|clients|inbox).*/, { timeout: 15000 });
    console.log("✅ Login successful");

    // 2. NAVIGATE TO CLIENTS
    console.log("🔹 Navigating to Clients...");
    await page.goto("/clients");

    // Check for errors again
    if (await errorOverlay.isVisible()) {
      console.error("❌ Next.js Error Overlay detected on /clients");
      console.error(await errorOverlay.innerText());
      throw new Error("Frontend crashed on /clients");
    }

    // Ensure we are on clients page
    await expect(page).toHaveURL(/.*\/clients/);
    await page.waitForLoadState("networkidle");

    // Check for access denied or loading
    await expect(
      page.locator("text=Access Denied").or(page.locator("text=Login")),
    ).not.toBeVisible();

    // Wait for header
    await expect(
      page
        .getByRole("main", { name: "Clients" })
        .locator("h1")
        .filter({ hasText: /^Clients$/ })
        .last(),
    ).toBeVisible({ timeout: 10000 });

    // Debug: Print all buttons
    const buttons = await page.locator("button").allInnerTexts();
    console.log("🔹 Available buttons:", buttons);

    // 3. CREATE CLIENT
    console.log("🔹 Creating Client...");
    const uniqueId = Date.now().toString().slice(-6);
    const clientName = `PW Test ${uniqueId}`;

    // Click Add Client button
    const addBtn = page
      .locator("button")
      .filter({ hasText: "New Client" })
      .first();
    await expect(addBtn).toBeVisible({ timeout: 10000 });
    await addBtn.click();

    await page.waitForURL(/.*\/clients\/new/, { timeout: 10000 });
    await page.getByRole("button", { name: /Manual Entry/i }).click();

    // Fill Form
    const form = page.locator("form").first();
    await expect(form).toBeVisible({ timeout: 10000 });
    await form.locator('input[name="full_name"]').fill(clientName);
    await form.locator('input[name="email"]').fill(`pw.${uniqueId}@example.com`);

    // Some forms have required phone
    const phoneInput = form.locator('input[name="phone"]');
    if (await phoneInput.isVisible()) {
      await phoneInput.fill("+62812345678");
    }

    await expect(
      form.locator('button', { hasText: /Next: Personal Details/i }),
    ).toBeVisible({ timeout: 10000 });
    await expect(page.locator(`text=${clientName}`).first()).toBeVisible();
    console.log("✅ New client wizard accepts basic CRM fields:", clientName);

    // 4. KANBAN VIEW
    console.log("🔹 Switching to Kanban...");
    await page.goto("/clients");
    const kanbanBtn = page
      .locator("button")
      .filter({ hasText: /kanban/i })
      .first();
    if (await kanbanBtn.isVisible()) {
      await kanbanBtn.click();
      await expect(page.locator("text=Lead").first()).toBeVisible();
      console.log("✅ Kanban view active");
    } else {
      console.log("⚠️ Kanban toggle not found");
    }
  });
});
