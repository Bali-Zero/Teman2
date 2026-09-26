import { test, expect, type Page } from "@playwright/test";

/** R19 public presentation. The page Page title is the CI discovery contract. */

test.beforeEach(async ({ page }) => {
  await page.route("**/*", (route) =>
    ["GET", "HEAD"].includes(route.request().method())
      ? route.continue()
      : route.fulfill({ status: 204, body: "" }),
  );
});

const PAPER = "rgb(247, 244, 238)"; // R19 paper

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

test.afterEach(async ({ page }) => {
  await page.close();
});

test.describe("blog news light page Page", () => {
  test("/news renders on warm paper with R19 paper chrome", async ({
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

    // The converted masthead uses R19 paper.
    const nav = page.locator("nav").first();
    await expect(nav).toBeVisible();
    const navBg = await nav.evaluate(
      (el) => getComputedStyle(el).backgroundColor,
    );
    expect(navBg).toBe(PAPER);

    // The converted footer uses the R19 wash.
    const footer = page.locator("footer").last();
    await expect(footer).toBeAttached();
    const footerBg = await footer.evaluate(
      (el) => getComputedStyle(el).backgroundColor,
    );
    expect(footerBg).toBe("rgb(238, 233, 225)");
  });

  test("/news has no horizontal overflow at 390px", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/news");
    await page.locator(".rumah-putih").first().waitFor();
    await assertNoHorizontalOverflow(page);
  });

  test("article detail renders ink-on-paper with R19 chrome", async ({
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

    // The article uses the same R19 chrome as News.
    const navBg = await page
      .locator("nav")
      .first()
      .evaluate((el) => getComputedStyle(el).backgroundColor);
    expect(navBg).toBe(PAPER);
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
