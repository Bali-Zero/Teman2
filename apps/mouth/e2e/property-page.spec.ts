import { test, expect } from "@playwright/test";

test.describe("Property Landing Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/property");
  });

  test("renders hero section", async ({ page }) => {
    await expect(page.locator('h1:has-text("Property in Bali")')).toBeVisible();
    await expect(page.locator('text=done right')).toBeVisible();
  });

  test("renders 3 service cards", async ({ page }) => {
    await expect(page.locator('h3:has-text("Leasehold Advisory")')).toBeVisible();
    await expect(page.locator('h3:has-text("Freehold Structuring")')).toBeVisible();
    await expect(page.locator('h3:has-text("Investment Analysis")')).toBeVisible();
  });

  test("has WhatsApp CTA link", async ({ page }) => {
    const whatsappLinks = page.locator('a[href*="wa.me/628213107363"]');
    const count = await whatsappLinks.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test("has Prime Intelligence section", async ({ page }) => {
    await expect(page.locator('text=Powered by Prime Intelligence')).toBeVisible();
    const primeLink = page.locator('a[href="https://prime.balizero.com"]');
    const count = await primeLink.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test("has correct page title", async ({ page }) => {
    await expect(page).toHaveTitle(/Property Services/);
  });
});
