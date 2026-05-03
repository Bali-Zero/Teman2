import { test, expect } from "@playwright/test";

test.describe("Funnel CTAs on Homepage", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("renders 4 funnel CTA cards", async ({ page }) => {
    const ctaSection = page.locator(".funnel-ctas");
    await expect(ctaSection).toBeVisible();

    const cards = ctaSection.locator("a");
    await expect(cards).toHaveCount(4);
  });

  test("Visa Oracle CTA links to visa.balizero.com", async ({ page }) => {
    const visaLink = page.locator('.funnel-ctas a:has-text("Visa Oracle")');
    await expect(visaLink).toBeVisible();
    await expect(visaLink).toHaveAttribute("href", "https://visa.balizero.com");
  });

  test("KBLI Navigator CTA links to /kbli", async ({ page }) => {
    const kbliLink = page.locator('.funnel-ctas a:has-text("KBLI Navigator")');
    await expect(kbliLink).toBeVisible();
    await expect(kbliLink).toHaveAttribute("href", "/kbli");
  });

  test("Tax CTA links to /contact?service=tax", async ({ page }) => {
    const taxLink = page.locator('.funnel-ctas a:has-text("Tax & Compliance")');
    await expect(taxLink).toBeVisible();
    await expect(taxLink).toHaveAttribute("href", "/contact?service=tax");
  });

  test("Property CTA links to /property", async ({ page }) => {
    const propertyLink = page.locator('.funnel-ctas a:has-text("Property")');
    await expect(propertyLink).toBeVisible();
    await expect(propertyLink).toHaveAttribute("href", "/property");
  });

  test("Intelligence Tools section header is visible", async ({ page }) => {
    await expect(page.locator('.funnel-ctas h2:has-text("Intelligence Tools")')).toBeVisible();
  });
});
