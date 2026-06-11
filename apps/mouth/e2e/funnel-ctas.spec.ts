import { test, expect } from "@playwright/test";

/**
 * Funnel chips strip — MYTHOS B2 (IA-7 demotion).
 *
 * The four full FunnelFeature blocks left the homepage; the tools live on
 * as a compact ghost-chip strip. These tests pin the strip's reality:
 * 4 chips, link targets verbatim from FunnelFeature.FUNNEL_HREF.
 *
 * History: the previous version of this spec asserted a `.funnel-ctas`
 * section (FunnelCTAs.tsx — only used by page.v1-backup since the v2
 * homepage shipped) including a stale `/contact?service=tax` target. It
 * also never ran in CI (no "page Page" in the describe title). Both fixed.
 *
 * Describe title contains "page Page" — required by the CI grep
 * (.github/workflows/tests.yml runs `npx playwright test --grep "page Page"`).
 */
test.describe("funnel chips strip page Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("renders 4 tool chips", async ({ page }) => {
    const strip = page.getByTestId("funnel-chips");
    await expect(strip).toBeVisible();
    await expect(strip.locator("a")).toHaveCount(4);
  });

  test("Visa Oracle chip links to visa.balizero.com", async ({ page }) => {
    const chip = page.getByTestId("funnel-chips").locator("#visa");
    await expect(chip).toContainText("Visa Oracle");
    await expect(chip).toHaveAttribute("href", "https://visa.balizero.com/");
  });

  test("KBLI Navigator chip links to /kbli", async ({ page }) => {
    const chip = page.getByTestId("funnel-chips").locator("#kbli");
    await expect(chip).toContainText("KBLI Navigator");
    await expect(chip).toHaveAttribute("href", "/kbli");
  });

  test("Tax Intelligence chip links to tax.balizero.com", async ({ page }) => {
    const chip = page.getByTestId("funnel-chips").locator("#tax");
    await expect(chip).toContainText("Tax Intelligence");
    await expect(chip).toHaveAttribute("href", "https://tax.balizero.com/");
  });

  test("Property Map chip links to /property/eligibility", async ({ page }) => {
    const chip = page.getByTestId("funnel-chips").locator("#property");
    await expect(chip).toContainText("Property Map");
    await expect(chip).toHaveAttribute("href", "/property/eligibility");
  });

  test("strip header frames the chips as shortcuts", async ({ page }) => {
    await expect(
      page
        .getByTestId("funnel-chips")
        .getByText("when you already know what you need"),
    ).toBeVisible();
  });
});
