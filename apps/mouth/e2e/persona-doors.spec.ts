import { test, expect } from "@playwright/test";
import { contrast, over, parseColor, type Rgba } from "./support/contrast";

/**
 * Home doors + single-primary discipline (MYTHOS B2R2 IA-1 + P2), on the R19 home.
 *
 * The pre-R19 home carried four "Start where you are." persona-door cards
 * (data-testid="persona-doors", data-door, "See how it works"). R19 replaced
 * that band with the hero's "Choose where to start" doors, which link the
 * existing service pages, and the #tools band, whose ids keep the in-page
 * anchors the navigation and external links resolve (#visa #kbli #tax
 * #property). What these tests pin is the contract those cards carried, not
 * their markup:
 *   - a door for each of visa, company, tax and property, in that order
 *   - the four nav anchors resolve to exactly one element each, in #tools
 *   - exactly ONE primary CTA on the page, and it is the WhatsApp hero
 *   - the doors band has no competing primary styling
 *   - the fold's supporting text and the header CTA stay readable
 *
 * Describe title contains "page Page" — required by the CI grep
 * (.github/workflows/tests.yml runs `npx playwright test --grep "page Page|@offline"`).
 */
const COPPER = "rgb(164, 75, 54)"; // R19 primary, #A44B36

const DOORS = [
  { door: "visa", label: "Visas & residence", href: "/services/visa" },
  { door: "company", label: "Business & company", href: "/services/company" },
  { door: "tax", label: "Tax", href: "/services/tax" },
  { door: "property", label: "Property", href: "/services/property" },
  { door: "compliance", label: "Compliance", href: "/services/compliance" },
] as const;

test.describe("persona doors homepage page Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("renders the doors with correct targets", async ({ page }) => {
    // Old: four cards, /visa /kbli /taxes/gap /property, with the
    // "I'm moving to Bali" copy. New: the hero doors to the existing service
    // pages (the four funnels stay reachable through the tool links pinned in
    // funnel-ctas.spec.ts).
    const doors = page.locator(".entry-hero .entry-categories");
    await expect(doors).toBeVisible();
    await expect(page.getByText("Choose where to start")).toBeVisible();
    const links = doors.locator("a");
    await expect(links).toHaveCount(DOORS.length);
    for (const [index, { label, href }] of DOORS.entries()) {
      const link = links.nth(index);
      await expect(link).toBeVisible();
      await expect(link).toContainText(label);
      await expect(link).toHaveAttribute("href", href);
    }
  });

  test("doors are ordered visa · company · tax · property (tax third)", async ({
    page,
  }) => {
    const order = await page
      .locator(".entry-hero .entry-categories a")
      .evaluateAll((els) => els.map((el) => el.getAttribute("href")));
    expect(order.slice(0, 4)).toEqual(DOORS.slice(0, 4).map((d) => d.href));
  });

  test("the #visa/#kbli/#tax/#property nav anchors resolve", async ({
    page,
  }) => {
    // Old: an <article id> inside the persona-doors band. New: the heading of
    // each service in #tools carries the id; the header's Explore link points
    // at #tools itself. Zero dead anchors.
    await expect(page.locator("#tools")).toHaveCount(1);
    await expect(page.locator('header a[href="/#tools"]')).toHaveCount(1);
    for (const anchor of ["visa", "kbli", "tax", "property"]) {
      await expect(page.locator(`#${anchor}`)).toHaveCount(1);
      await expect(page.locator(`#tools #${anchor}`)).toHaveCount(1);
    }
  });

  test("exactly one primary CTA on the page (P2)", async ({ page }) => {
    const primaries = page.locator(".cta-primary");
    await expect(primaries).toHaveCount(1);

    // Structure, not prose. What is load-bearing is that the one primary is
    // the WhatsApp hero: the header's WhatsApp action is the outline variant.
    // R19 copper is #A44B36 = rgb(164,75,54). The href pattern avoids
    // pinning the business number.
    const primary = primaries.first();
    await expect(primary).toHaveAttribute(
      "href",
      /(?:wa\.me|api\.whatsapp\.com)\//,
    );
    await expect(primary).toBeVisible();
    await expect(page.locator(".entry-hero .cta-primary")).toHaveCount(1);
    const bg = await primary.evaluate(
      (el) => getComputedStyle(el).backgroundColor,
    );
    expect(bg).toBe(COPPER);
    // Old: exactly 48px. R19's hero action is 52px; the contract is the
    // touch-target floor.
    const minHeight = await primary.evaluate((el) =>
      parseFloat(getComputedStyle(el).minHeight),
    );
    expect(minHeight).toBeGreaterThanOrEqual(48);

    const header = page.locator(".site-header a[href*='wa.me']");
    await expect(header).toHaveCount(1);
    await expect(header).not.toHaveClass(/cta-primary/);
    expect(
      await header.evaluate((el) => getComputedStyle(el).backgroundColor),
    ).not.toBe(COPPER);
  });

  test("R19 fold keeps its supporting text and nav CTA readable", async ({
    page,
  }) => {
    // Old: the hero's supporting sentence carried a text-shadow to stay legible
    // over the photograph. R19's supporting text sits on its own paper panel;
    // the panel has to stay opaque enough to hold 4.5:1 over a neutral ground.
    const neutral: Rgba = [128, 128, 128, 1];
    for (const selector of [".entry-category-label", ".hero-caption"]) {
      const { color, background } = await page
        .locator(selector)
        .evaluate((el) => {
          const style = getComputedStyle(el);
          return {
            color: style.color,
            background: style.backgroundColor,
          };
        });
      const panel = over(parseColor(background), neutral);
      expect(
        contrast(over(parseColor(color), panel), panel),
        selector,
      ).toBeGreaterThanOrEqual(4.5);
    }

    const navCta = page
      .locator(".site-header")
      .getByRole("link", { name: /Get Started.*via WhatsApp/i });
    await navCta.hover();
    await expect(navCta).toHaveCSS("background-color", "rgb(234, 227, 216)");
    await expect(navCta).toHaveCSS("color", "rgb(29, 44, 59)");
  });

  test("doors band contains no red primary styling", async ({ page }) => {
    // Old: every "See how it works" link was brand navy, no .cta-primary.
    // New: the doors and the tool links are soft links on paper; none carries
    // the primary class or the copper fill.
    const doors = page.locator(".entry-hero .entry-categories");
    await expect(doors.locator(".cta-primary")).toHaveCount(0);
    await expect(page.locator("#tools .cta-primary")).toHaveCount(0);
    for (const { href } of DOORS) {
      const link = doors.locator(`a[href="${href}"]`);
      await expect(link).toHaveCount(1);
      const { color, background } = await link.evaluate((el) => {
        const style = getComputedStyle(el);
        return { color: style.color, background: style.backgroundColor };
      });
      expect(background).not.toBe(COPPER);
      expect(color).not.toBe(COPPER);
    }
  });
});
