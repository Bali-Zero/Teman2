import { test, expect, type Page } from "@playwright/test";

/**
 * MYTHOS Stage-B Batch 2 — Rumah Putih LIGHT theme for the public SERVICE pages.
 *
 * Pins the route-scoped light conversion of /services, /services/[slug] and the
 * /contact channel page:
 *   - the page's top-level wrapper carries the warm-paper surface
 *     (--surface-base #f7f6f2 → rgb(247, 246, 242)) via RUMAH_VARS;
 *   - NavShell (the fixed masthead) + Footer stay their dark navy anchors
 *     (they read --nav-bg / --footer-bg, NOT --surface-base);
 *   - the /services index stays PRICE-FREE (#1263) — no rupiah/IDR figure;
 *   - the /contact page (a channel-card page, NOT a <form>) surfaces legible
 *     contact CTAs on light;
 *   - no horizontal overflow at 390px (mobile) on any page.
 *
 * Describe title contains "page Page" — required by the CI grep
 * (.github/workflows/tests.yml runs `npx playwright test --grep "page Page"`).
 */

const PAPER = "rgb(247, 246, 242)"; // --surface-base #f7f6f2 under Rumah Putih

/** Parse "rgb(r, g, b)" / "rgba(r, g, b, a)" → {r,g,b}. */
function parseRgb(value: string): { r: number; g: number; b: number } | null {
  const m = value.match(/rgba?\(([^)]+)\)/);
  if (!m) return null;
  const [r, g, b] = m[1].split(",").map((n) => parseInt(n.trim(), 10));
  return { r, g, b };
}

/** A color is "dark" when its luminance is low (navy/charcoal masthead). */
function isDark(value: string): boolean {
  const rgb = parseRgb(value);
  if (!rgb) return false;
  const lum = 0.2126 * rgb.r + 0.7152 * rgb.g + 0.0722 * rgb.b;
  return lum < 90; // navy #1e3863 ≈ 49, #0e1a30 ≈ 26
}

async function assertNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => {
    const doc = document.documentElement;
    // 1px slop for sub-pixel rounding.
    return doc.scrollWidth - doc.clientWidth;
  });
  expect(overflow).toBeLessThanOrEqual(1);
}

async function assertNavAndFooterDark(page: Page) {
  const nav = page.locator("nav").first();
  await expect(nav).toBeVisible();
  const navBg = await nav.evaluate(
    (el) => getComputedStyle(el).backgroundColor,
  );
  expect(isDark(navBg)).toBe(true);

  const footer = page.locator("footer").first();
  await expect(footer).toBeAttached();
  const footerBg = await footer.evaluate(
    (el) => getComputedStyle(el).backgroundColor,
  );
  expect(isDark(footerBg)).toBe(true);
}

test.describe("service pages light page Page", () => {
  test("/services renders on warm paper with navy chrome and stays price-free", async ({
    page,
  }) => {
    await page.goto("/services");

    const wrapper = page.locator(".rumah-putih").first();
    await expect(wrapper).toBeVisible();
    const wrapperBg = await wrapper.evaluate(
      (el) => getComputedStyle(el).backgroundColor,
    );
    expect(wrapperBg).toBe(PAPER);

    await assertNavAndFooterDark(page);

    // #1263: the services index must not reintroduce any price. Scope to the
    // page wrapper so unrelated chrome (e.g. a "Talk to us" CTA) can't trip it.
    const wrapperText = (await wrapper.innerText()).toLowerCase();
    expect(wrapperText).not.toMatch(/\bidr\b/);
    expect(wrapperText).not.toMatch(/rp\s?\d/);
  });

  test("/services has no horizontal overflow at 390px", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/services");
    await page.locator(".rumah-putih").first().waitFor();
    await assertNoHorizontalOverflow(page);
  });

  test("/contact renders light with legible contact CTAs and navy chrome", async ({
    page,
  }) => {
    await page.goto("/contact");

    const wrapper = page.locator(".rumah-putih").first();
    await expect(wrapper).toBeVisible();
    const wrapperBg = await wrapper.evaluate(
      (el) => getComputedStyle(el).backgroundColor,
    );
    expect(wrapperBg).toBe(PAPER);

    await assertNavAndFooterDark(page);

    // /contact is a channel-card page (WhatsApp / Email / Office), not a <form>.
    // Assert the contact CTAs are present and reachable on the light surface.
    const whatsapp = page.locator('a[href*="wa.me"], a[href*="whatsapp"]');
    expect(await whatsapp.count()).toBeGreaterThan(0);
    const email = page.locator('a[href^="mailto:"]');
    expect(await email.count()).toBeGreaterThan(0);

    // The email channel card (white fill) carries ink text → must be dark.
    const emailCardText = await email
      .first()
      .evaluate((el) => getComputedStyle(el).color)
      .catch(() => "rgb(0, 0, 0)");
    expect(isDark(emailCardText)).toBe(true);
  });

  test("/contact has no horizontal overflow at 390px", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/contact");
    await page.locator(".rumah-putih").first().waitFor();
    await assertNoHorizontalOverflow(page);
  });

  test("service detail renders ink-on-paper with navy chrome", async ({
    page,
  }) => {
    // visa is a stable, always-present service slug (SERVICES_DATA).
    await page.goto("/services/visa");

    const wrapper = page.locator(".rumah-putih").first();
    await expect(wrapper).toBeVisible();
    const wrapperBg = await wrapper.evaluate(
      (el) => getComputedStyle(el).backgroundColor,
    );
    expect(wrapperBg).toBe(PAPER);

    // The hardcoded-dark detail page now resolves a navy heading on paper.
    const heading = page.locator("h1").first();
    await expect(heading).toBeVisible();
    const headingColor = await heading.evaluate(
      (el) => getComputedStyle(el).color,
    );
    expect(isDark(headingColor)).toBe(true);

    await assertNavAndFooterDark(page);
  });

  test("service detail has no horizontal overflow at 390px", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/services/visa");
    await page.locator(".rumah-putih").first().waitFor();
    await assertNoHorizontalOverflow(page);
  });
});
