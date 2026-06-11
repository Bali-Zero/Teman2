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

  test("real doors (visa·company) navigate; Soon doors (tax·property) do not", async ({
    page,
  }) => {
    const doors = page.getByTestId("persona-doors");
    await expect(doors).toBeVisible();
    await expect(doors.getByText("Start where you are.")).toBeVisible();

    // Visa + KBLI are real tools — keep their navigable links.
    const visa = doors.locator('a[data-door="visa"]');
    const company = doors.locator('a[data-door="company"]');
    await expect(visa).toHaveAttribute("href", "/visa");
    await expect(company).toHaveAttribute("href", "/kbli");

    // Tax + Property are "Soon" — the door CTA is a non-navigating element
    // (no <a href>) and the article carries the coming-soon marker + badge.
    await expect(doors.locator('a[data-door="tax"]')).toHaveCount(0);
    await expect(doors.locator('a[data-door="property"]')).toHaveCount(0);
    await expect(doors.locator('[data-door="tax"]')).toHaveCount(1);
    await expect(doors.locator('[data-door="property"]')).toHaveCount(1);
    for (const persona of ["tax", "property"]) {
      const article = doors.locator(
        `article[data-coming-soon="true"]#${
          persona === "tax" ? "tax" : "property"
        }`,
      );
      await expect(article).toHaveCount(1);
      await expect(article.getByText("Soon", { exact: true })).toBeVisible();
    }
    // The tool-title line of a Soon door must NOT be a deep-link either.
    await expect(doors.locator('a[data-tool="tax"]')).toHaveCount(0);
    await expect(doors.locator('a[data-tool="property"]')).toHaveCount(0);

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
      .locator("[data-door]")
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
    // Real-tool door CTAs are soft navy links ("See how it works").
    for (const door of ["visa", "company"]) {
      const link = doors.locator(`a[data-door="${door}"]`);
      await expect(link).toContainText("See how it works");
      const color = await link.evaluate((el) => getComputedStyle(el).color);
      expect(color).toBe("rgb(30, 56, 99)"); // brand navy #1e3863
    }
    // "Soon" door CTAs are a muted non-navigating "Coming soon" line — never
    // red, never a link.
    for (const door of ["tax", "property"]) {
      const cta = doors.locator(`[data-door="${door}"]`);
      await expect(cta).toContainText("Coming soon");
      const color = await cta.evaluate((el) => getComputedStyle(el).color);
      expect(color).toBe("rgb(71, 83, 114)"); // muted ink #475372
    }
  });
});
