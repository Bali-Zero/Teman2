import { test, expect } from "@playwright/test";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000";

test.describe("Zantara AI Expert - Intense Browser Validation", () => {
  test.beforeEach(async ({ page }) => {
    // Intercept backend calls to point to our local backend
    await page.route("**/api/v1/kbli-notebook/chat", async (route) => {
      // Mock directly for consistency in E2E
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          answer:
            "### 📋 Executive Brief: KBLI 55101\nIn base al **PP 28/2025**, per un Hotel 5 stelle serve il **Sertifikat Laik Sehat** e la licenza **SKPL**.",
          results: [
            {
              code: "55101",
              title: "Hotel Bintang Lima",
              risk_category: "Menengah Tinggi",
            },
          ],
          suggested_queries: ["Quali licenze servono?"],
        }),
      });
    });

    await page.goto(`${BASE_URL}/kbli`);
    await page.waitForLoadState("networkidle");
  });

  test("Should load KBLI page and show Zantara chat section", async ({
    page,
  }) => {
    await expect(page.locator("h1")).toContainText("KBLI 2025 Navigator");
    await expect(page.getByPlaceholder(/search kbli/i)).toBeVisible();
    // ZantaraChat section with opener text
    await expect(
      page.getByText(/I'm Zantara, your KBLI expert/i),
    ).toBeVisible();
  });

  test.skip("Legacy: enriched AI response with Markdown - needs update for new /kbli UI", async () => {
    // TODO: Rewrite for new ZantaraChat component structure (no #sec-chat, .msg-a, .kbli-card-mini)
  });

  test.skip("Legacy: History Synchronization - needs update for new /kbli UI", async () => {
    // TODO: Old static HTML had bottom-nav sections; new page has different structure
  });
});
