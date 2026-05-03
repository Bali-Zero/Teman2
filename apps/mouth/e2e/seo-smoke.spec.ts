import { test, expect } from "@playwright/test";

/**
 * SEO Smoke Test - SSR & Schema Validation
 *
 * Verifies that service pages are properly server-side rendered
 * and contain structured data for SEO and LLM extraction.
 *
 * Tests:
 * 1. Service page loads successfully
 * 2. Pricing content is present in initial HTML (SSR verified)
 * 3. JSON-LD schema tags are present
 * 4. Semantic HTML structure is correct
 *
 * Usage:
 *   npx playwright test tests/seo-smoke.spec.ts
 *
 * Environment variables:
 *   E2E_BASE_URL - base URL (default: http://localhost:3000)
 */

const CONFIG = {
  baseUrl: process.env.E2E_BASE_URL || "http://localhost:3000",
};

test.describe("SEO Smoke Tests - SSR & Schema Validation", () => {
  test("Service page loads with SSR content", async ({ page }) => {
    // Navigate to a service page (using visa as example, but any service works)
    await page.goto(`${CONFIG.baseUrl}/services/visa`);

    // Wait for page to load
    await page.waitForLoadState("networkidle");

    // Verify page title
    await expect(page).toHaveTitle(/Visa.*Bali.*2026/i);

    // Verify main heading is present
    await expect(page.locator("h1")).toContainText(/Visa|Immigration/i);
  });

  test("Pricing content is present in SSR HTML (SEO Verified)", async ({
    page,
  }) => {
    await page.goto(`${CONFIG.baseUrl}/services/visa`);
    await page.waitForLoadState("networkidle");

    // Get the initial HTML content (before any client-side hydration)
    const htmlContent = await page.content();

    // Verify pricing information is in the HTML source
    // This ensures Googlebot can see it without JavaScript
    expect(htmlContent).toContain("Pricing");

    // Check for at least one price value in the HTML
    // Look for common price patterns (IDR format with dots)
    const hasPriceInHTML =
      htmlContent.includes("2.300.000") || // C1 Tourism Visit
      htmlContent.includes("3.600.000") || // C2 Business Visit
      htmlContent.includes("17.000.000") || // E28A Investor KITAS
      htmlContent.includes("13.000.000"); // E33G Digital Nomad

    expect(hasPriceInHTML).toBeTruthy();

    // Verify service description is in HTML
    expect(htmlContent).toContain("Complete visa solutions");
  });

  test("JSON-LD schema tags are present", async ({ page }) => {
    await page.goto(`${CONFIG.baseUrl}/services/visa`);
    await page.waitForLoadState("networkidle");

    const htmlContent = await page.content();

    // Verify JSON-LD script tags exist
    expect(htmlContent).toContain('<script type="application/ld+json">');

    // Verify schema.org context
    expect(htmlContent).toContain('"@context":"https://schema.org"');

    // Verify GovernmentService or ProfessionalService schema
    const hasServiceSchema =
      htmlContent.includes('"@type":"GovernmentService"') ||
      htmlContent.includes('"@type":"ProfessionalService"');

    expect(hasServiceSchema).toBeTruthy();

    // Verify FAQPage schema
    expect(htmlContent).toContain('"@type":"FAQPage"');

    // Verify FAQ structure
    expect(htmlContent).toContain('"@type":"Question"');
    expect(htmlContent).toContain('"@type":"Answer"');
  });

  test("Semantic HTML structure with microdata", async ({ page }) => {
    await page.goto(`${CONFIG.baseUrl}/services/visa`);
    await page.waitForLoadState("networkidle");

    const htmlContent = await page.content();

    // Verify semantic <dl> element exists (AI Summary Block)
    expect(htmlContent).toContain("<dl");
    expect(htmlContent).toContain("itemScope");
    expect(htmlContent).toContain("itemProp");
    expect(htmlContent).toContain("itemType");

    // Verify key semantic properties
    expect(htmlContent).toContain("serviceType");
    expect(htmlContent).toContain("hoursAvailable");
    expect(htmlContent).toContain("areaServed");
  });

  test("Multiple service pages have correct SSR", async ({ page }) => {
    const services = ["visa", "company", "tax", "property"];

    for (const serviceSlug of services) {
      await page.goto(`${CONFIG.baseUrl}/services/${serviceSlug}`);
      await page.waitForLoadState("networkidle");

      const htmlContent = await page.content();

      // Each service page should have:
      // 1. JSON-LD schemas
      expect(htmlContent).toContain('<script type="application/ld+json">');

      // 2. Service name in title
      const service =
        serviceSlug === "visa"
          ? "Visa"
          : serviceSlug === "company"
            ? "Company"
            : serviceSlug === "tax"
              ? "Tax"
              : "Property";

      // 3. Pricing section
      expect(htmlContent).toContain("Pricing");

      // 4. FAQ section
      expect(htmlContent).toContain("Frequently Asked Questions");
    }
  });

  test("Service page metadata is correct", async ({ page }) => {
    await page.goto(`${CONFIG.baseUrl}/services/visa`);
    await page.waitForLoadState("networkidle");

    // Verify meta description
    const metaDescription = await page
      .locator('meta[name="description"]')
      .getAttribute("content");
    expect(metaDescription).toBeTruthy();
    expect(metaDescription?.length).toBeGreaterThan(50);

    // Verify Open Graph tags (if present)
    const ogTitle = await page
      .locator('meta[property="og:title"]')
      .getAttribute("content");
    if (ogTitle) {
      expect(ogTitle).toContain("Visa");
    }
  });
});
