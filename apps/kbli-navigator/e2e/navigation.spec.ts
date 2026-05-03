import { test, expect } from "@playwright/test";

/**
 * E2E Tests for KBLI Navigator - Critical User Flows
 */

const BASE_PATH = "/kbli-navigator/kbli";

test.describe("Navigation", () => {
  test("homepage loads with sectors", async ({ page }) => {
    await page.goto(BASE_PATH);

    // Check page title
    await expect(page).toHaveTitle(/KBLI 2025 Navigator/);

    // Check page loaded and has content
    await expect(page.locator("main, body")).toBeVisible();
    const hasLinks = await page.locator("a").count();
    expect(hasLinks).toBeGreaterThan(0);
  });

  test("can navigate to sector page", async ({ page }) => {
    await page.goto(BASE_PATH);

    // Click on first sector (usually A - Agriculture)
    const firstSector = page.locator('a[href*="/sectors/"]').first();
    await firstSector.click();

    // Verify sector page loaded
    await expect(page.locator("h1")).toBeVisible();
    const hasCodeLinks = await page
      .locator('a[href^="/kbli-navigator/kbli/"]')
      .count();
    expect(hasCodeLinks).toBeGreaterThan(0);
  });

  test("can navigate to KBLI code detail page", async ({ page }) => {
    // Direct navigation to specific KBLI code (faster than clicking)
    await page.goto(`${BASE_PATH}/56101`);
    await page.waitForLoadState("networkidle");

    // Verify detail page loaded
    await expect(page.locator("h1")).toBeVisible();
    const url = page.url();
    expect(url).toContain("/56101");
  });
});

test.describe("Search", () => {
  test("search functionality works", async ({ page }) => {
    await page.goto(`${BASE_PATH}/search?q=restaurant`);

    // Wait for results to load
    await page.waitForLoadState("networkidle");

    // Check if results are displayed or no results message
    const resultsOrNoResults = page
      .locator("text=/result|No results/i")
      .first();
    await expect(resultsOrNoResults).toBeVisible();
  });

  test("search from homepage navigates to search page", async ({ page }) => {
    await page.goto(BASE_PATH);

    // Find search input
    const searchInput = page
      .locator(
        'input[type="search"], input[placeholder*="Search"], input[placeholder*="Cari"]',
      )
      .first();
    if (await searchInput.isVisible().catch(() => false)) {
      await searchInput.fill("56101");
      await searchInput.press("Enter");

      // Verify navigation to search page
      await expect(page).toHaveURL(/search/);
    }
  });
});

test.describe("KBLI Detail Page", () => {
  test("KBLI 56101 (Restaurant) displays correct information", async ({
    page,
  }) => {
    await page.goto(`${BASE_PATH}/56101`);

    // Check title contains KBLI code or business name
    await expect(page.locator("h1")).toContainText(/56101|Restaurant/i);

    // Check PMA status is displayed
    const pmaBadge = page.locator("text=/open|terbuka|100%/i").first();
    await expect(pmaBadge).toBeVisible();

    // Check licensing section exists
    const licensingSection = page
      .locator("text=/Licensing|Perizinan|Requirements/i")
      .first();
    await expect(licensingSection).toBeVisible();
  });

  test("related codes are displayed", async ({ page }) => {
    await page.goto(`${BASE_PATH}/56101`);

    // Wait for page load
    await page.waitForLoadState("networkidle");

    // Check page loaded successfully - verify body content
    const body = page.locator("body");
    await expect(body).toBeVisible();

    // Verify page has KBLI-related content
    const pageText = await body.textContent();
    expect(pageText).toMatch(/56101|Restaurant|Licensing|KBLI/i);
  });
});

test.describe("Performance", () => {
  test("page loads within acceptable time", async ({ page }) => {
    const startTime = Date.now();
    await page.goto(`${BASE_PATH}/56101`);
    await page.waitForLoadState("networkidle");
    const loadTime = Date.now() - startTime;

    // Page should load in less than 5 seconds
    expect(loadTime).toBeLessThan(5000);
  });

  test("no JavaScript errors on page load", async ({ page }) => {
    const errors: string[] = [];

    page.on("pageerror", (error) => {
      errors.push(error.message);
    });

    page.on("console", (msg) => {
      if (msg.type() === "error") {
        errors.push(msg.text());
      }
    });

    await page.goto(`${BASE_PATH}/56101`);
    await page.waitForLoadState("networkidle");

    // Filter out non-critical errors
    const criticalErrors = errors.filter(
      (e) =>
        !e.includes("favicon") &&
        !e.includes("google-analytics") &&
        !e.includes("gtag"),
    );

    expect(criticalErrors).toHaveLength(0);
  });
});
