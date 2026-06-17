import { test, expect } from "@playwright/test";

/**
 * Persona doors + single-primary discipline — MYTHOS B2R2 (IA-1 + P2).
 *
 * Pins the FOUR "Start where you are." doors (B2R2: tax added as the THIRD
 * door), their targets + copy + order, and the load-bearing brand rule:
 * exactly ONE red primary CTA on the page (`.cta-primary`, computed
 * background = --color-red-500 #ff2d4c), with zero red CTAs inside the
 * doors band (rule: NO red in that section).
 *
 * Describe title contains "page Page" — required by the CI grep
 * (.github/workflows/tests.yml runs `npx playwright test --grep "page Page"`).
 */
test.describe("persona doors homepage page Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("renders the four persona doors with correct targets", async ({
    page,
  }) => {
    const doors = page.getByTestId("persona-doors");
    await expect(doors).toBeVisible();
    await expect(doors.getByText("Start where you are.")).toBeVisible();

    const visa = doors.locator('a[data-door="visa"]');
    const company = doors.locator('a[data-door="company"]');
    const tax = doors.locator('a[data-door="tax"]');
    const property = doors.locator('a[data-door="property"]');

    await expect(visa).toHaveAttribute("href", "/visa");
    await expect(company).toHaveAttribute("href", "/kbli");
    await expect(tax).toHaveAttribute("href", "https://tax.balizero.com/");
    await expect(property).toHaveAttribute("href", "/property");

    await expect(doors.getByText("I'm moving to Bali")).toBeVisible();
    await expect(doors.getByText("I'm starting a business")).toBeVisible();
    await expect(
      doors.getByText("I'm already here — taxes confuse me"),
    ).toBeVisible();
    await expect(doors.getByText("I'm buying property")).toBeVisible();
  });

  test("doors are ordered visa · company · tax · property (tax third)", async ({
    page,
  }) => {
    const order = await page
      .getByTestId("persona-doors")
      .locator("article a[data-door]")
      .evaluateAll((els) => els.map((el) => el.getAttribute("data-door")));
    expect(order).toEqual(["visa", "company", "tax", "property"]);
  });

  test("door cards carry the #visa/#kbli/#tax/#property nav anchors", async ({
    page,
  }) => {
    // B2R2: the chips strip is gone — the navbar in-page anchors must
    // resolve to the door cards. Zero dead anchors.
    const doors = page.getByTestId("persona-doors");
    for (const anchor of ["visa", "kbli", "tax", "property"]) {
      await expect(doors.locator(`article#${anchor}`)).toHaveCount(1);
    }
  });

  test("exactly one red primary CTA on the page (P2)", async ({ page }) => {
    const primaries = page.locator(".cta-primary");
    await expect(primaries).toHaveCount(1);

    // The single primary is the hero WhatsApp CTA, wording intact (#1205),
    // painted brand red (--cta-primary-bg → --color-red-500 #ff2d4c).
    const primary = primaries.first();
    await expect(primary).toContainText("Chat with us — avg reply: 2 min");
    const bg = await primary.evaluate(
      (el) => getComputedStyle(el).backgroundColor,
    );
    expect(bg).toBe("rgb(255, 45, 76)");
  });

  test("doors band contains no red primary styling", async ({ page }) => {
    const doors = page.getByTestId("persona-doors");
    await expect(doors.locator(".cta-primary")).toHaveCount(0);
    // Every door CTA is a soft navy link.
    for (const door of ["visa", "company", "tax", "property"]) {
      const link = doors.locator(`a[data-door="${door}"]`);
      await expect(link).toContainText("See how it works");
      const color = await link.evaluate((el) => getComputedStyle(el).color);
      expect(color).toBe("rgb(30, 56, 99)"); // brand navy #1e3863
    }
  });
});
