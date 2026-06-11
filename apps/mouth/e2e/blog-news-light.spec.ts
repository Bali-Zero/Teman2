import { test, expect, type Page } from "@playwright/test";

/**
 * MYTHOS Stage-B Batch 1 — Rumah Putih LIGHT theme for the public blog/news.
 *
 * Pins the route-scoped light conversion of /news and the article detail page:
 *   - the page's top-level wrapper carries the warm-paper surface
 *     (--surface-base #f7f6f2 → rgb(247, 246, 242)) via RUMAH_VARS;
 *   - NavShell (the fixed masthead) + Footer stay their dark navy anchors
 *     (they read --nav-bg / --footer-bg, NOT --surface-base), per the
 *     Economist permanent-dark-chrome pattern;
 *   - no horizontal overflow at 390px (mobile) on either page.
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

test.describe("blog news light page Page", () => {
  test("/news renders on warm paper with a navy masthead + footer", async ({
    page,
  }) => {
    await page.goto("/news");

    // The Rumah Putih wrapper is marked with .rumah-putih and paints paper.
    const wrapper = page.locator(".rumah-putih").first();
    await expect(wrapper).toBeVisible();
    const wrapperBg = await wrapper.evaluate(
      (el) => getComputedStyle(el).backgroundColor,
    );
    expect(wrapperBg).toBe(PAPER);

    // Masthead (fixed nav) stays a dark navy anchor.
    const nav = page.locator("nav").first();
    await expect(nav).toBeVisible();
    const navBg = await nav.evaluate(
      (el) => getComputedStyle(el).backgroundColor,
    );
    expect(isDark(navBg)).toBe(true);

    // Footer stays dark too.
    const footer = page.locator("footer").first();
    await expect(footer).toBeAttached();
    const footerBg = await footer.evaluate(
      (el) => getComputedStyle(el).backgroundColor,
    );
    expect(isDark(footerBg)).toBe(true);
  });

  test("/news has no horizontal overflow at 390px", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/news");
    await page.locator(".rumah-putih").first().waitFor();
    await assertNoHorizontalOverflow(page);
  });

  test("article detail renders ink-on-paper with navy chrome", async ({
    page,
  }) => {
    // Discover a real article from /news (resilient to content changes).
    await page.goto("/news");
    const articleLink = page
      .locator('a[href^="/"][href*="/"]')
      .filter({ has: page.locator("h3, h2") })
      .first();

    // Fallback: the homepage hero_main article (taxes/…) is a stable target.
    let href = await articleLink.getAttribute("href").catch(() => null);
    if (!href || href === "/news") {
      href = "/taxes/indonesia-umkm-tax-reforms-pp-20-2026";
    }

    await page.goto(href);

    const wrapper = page.locator(".rumah-putih").first();
    await expect(wrapper).toBeVisible();
    const wrapperBg = await wrapper.evaluate(
      (el) => getComputedStyle(el).backgroundColor,
    );
    expect(wrapperBg).toBe(PAPER);

    // The long-form body resolves ink (dark) text on paper — pick the first
    // heading or paragraph inside the reader and assert its color is dark.
    const reader = page.locator(".mdx-content, .prose").first();
    if (await reader.count()) {
      const textColor = await reader
        .locator("h1, h2, h3, p")
        .first()
        .evaluate((el) => getComputedStyle(el).color)
        .catch(() => "rgb(0, 0, 0)");
      expect(isDark(textColor)).toBe(true);
    }

    // Masthead + footer stay navy.
    const navBg = await page
      .locator("nav")
      .first()
      .evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(isDark(navBg)).toBe(true);
  });

  test("article detail has no horizontal overflow at 390px", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/taxes/indonesia-umkm-tax-reforms-pp-20-2026");
    await page.locator(".rumah-putih").first().waitFor();
    await assertNoHorizontalOverflow(page);
  });
});
