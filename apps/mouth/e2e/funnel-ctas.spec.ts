import { test, expect } from "@playwright/test";

/**
 * Tool links inside the persona doors — MYTHOS B2R2.
 *
 * B2 demoted the four FunnelFeature blocks to a ghost-chip strip
 * (FunnelChips). B2R2 (Antonello 2026-06-11) kills the strip: the tool
 * identities move INTO the persona doors as bold tool-title links. These
 * tests pin that reality: the chips strip is GONE, and each door carries
 * its tool link with the href byte-identical to the old chip
 * (= FunnelFeature.FUNNEL_HREF; D10 deliberately not resolved here).
 *
 * History: the previous version of this spec asserted the FunnelChips
 * strip (4 chips + "when you already know what you need" header). Before
 * that, a `.funnel-ctas` section from page.v1-backup with a stale
 * `/contact?service=tax` target.
 *
 * Describe title contains "page Page" — required by the CI grep
 * (.github/workflows/tests.yml runs `npx playwright test --grep "page Page"`).
 */
test.describe("door tool links page Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("the chips strip is gone", async ({ page }) => {
    await expect(page.getByTestId("funnel-chips")).toHaveCount(0);
    await expect(
      page.getByText("when you already know what you need"),
    ).toHaveCount(0);
  });

  test("each door carries exactly one tool link (4 total)", async ({
    page,
  }) => {
    const doors = page.getByTestId("persona-doors");
    await expect(doors.locator("a[data-tool]")).toHaveCount(4);
    for (const funnel of ["visa", "kbli", "tax", "property"]) {
      await expect(doors.locator(`a[data-tool="${funnel}"]`)).toHaveCount(1);
    }
  });

  test("Visa Oracle tool link points at visa.balizero.com", async ({
    page,
  }) => {
    const link = page
      .getByTestId("persona-doors")
      .locator('a[data-tool="visa"]');
    await expect(link).toContainText("Visa Oracle");
    await expect(link).toContainText("check your visa");
    await expect(link).toHaveAttribute("href", "https://visa.balizero.com/");
  });

  test("KBLI Navigator tool link points at /kbli", async ({ page }) => {
    const link = page
      .getByTestId("persona-doors")
      .locator('a[data-tool="kbli"]');
    await expect(link).toContainText("KBLI Navigator");
    await expect(link).toContainText("find your code");
    await expect(link).toHaveAttribute("href", "/kbli");
  });

  test("Tax Intelligence tool link points at tax.balizero.com", async ({
    page,
  }) => {
    const link = page
      .getByTestId("persona-doors")
      .locator('a[data-tool="tax"]');
    await expect(link).toContainText("Tax Intelligence");
    await expect(link).toContainText("deadlines");
    await expect(link).toHaveAttribute("href", "https://tax.balizero.com/");
  });

  test("Property Map tool link points at /property/eligibility", async ({
    page,
  }) => {
    const link = page
      .getByTestId("persona-doors")
      .locator('a[data-tool="property"]');
    await expect(link).toContainText("Property Map");
    await expect(link).toContainText("zoning");
    await expect(link).toHaveAttribute("href", "/property/eligibility");
  });
});
