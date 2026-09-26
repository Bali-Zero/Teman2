import { test, expect } from "@playwright/test";

/**
 * Tool links on the home — MYTHOS B2R2, on the R19 home.
 *
 * B2R2 (Antonello 2026-06-11) moved the tool identities into the persona
 * doors as tool links with the href byte-identical to the old chip
 * (= FunnelFeature.FUNNEL_HREF; D10 deliberately not resolved here). The R19
 * home has no persona-door cards: each of the four tools now sits in its
 * service article of the #tools band, as a `data-tool` link. The destinations
 * are the contract, and they are unchanged.
 *
 * History: the previous version of this spec asserted the FunnelChips
 * strip (4 chips + "when you already know what you need" header). Before
 * that, a `.funnel-ctas` section from page.v1-backup with a stale
 * `/contact?service=tax` target.
 *
 * Describe title contains "page Page" — required by the CI grep
 * (.github/workflows/tests.yml runs `npx playwright test --grep "page Page|@offline"`).
 */
const TOOLS = [
  {
    tool: "visa",
    article: "visa-tool",
    name: "Visa Oracle",
    href: "https://visa.balizero.com/",
  },
  {
    tool: "kbli",
    article: "business-tool",
    name: "KBLI Navigator",
    href: "/kbli",
  },
  {
    tool: "tax",
    article: "tax-tool",
    name: "Tax Compliance Calendar",
    href: "https://tax.balizero.com/",
  },
  {
    tool: "property",
    article: "property-tool",
    name: "Property Check",
    href: "/property/eligibility",
  },
] as const;

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

  test("each tool has exactly one link on the home (4 total)", async ({
    page,
  }) => {
    const tools = page.locator("#tools");
    await expect(tools.locator("a[data-tool]")).toHaveCount(4);
    for (const { tool, article } of TOOLS) {
      await expect(tools.locator(`a[data-tool="${tool}"]`)).toHaveCount(1);
      await expect(
        tools.locator(`#${article} a[data-tool="${tool}"]`),
      ).toHaveCount(1);
    }
  });

  for (const { tool, article, name, href } of TOOLS) {
    test(`${name} tool link points at ${href}`, async ({ page }) => {
      const link = page.locator(`#tools a[data-tool="${tool}"]`);
      await expect(link).toBeVisible();
      await expect(link).toHaveAttribute("href", href);
      // The link sits under its tool's own heading.
      await expect(page.locator(`#${article} h3`)).toContainText(name);
    });
  }
});
