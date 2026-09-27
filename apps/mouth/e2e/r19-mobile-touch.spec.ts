import { test, expect, type Page } from "@playwright/test";

/**
 * Findings from the physical-device (iQOO, ~390px) QA sweep of balizero.com:
 * the fixed "Ask Zantara" FAB sat on top of the home footer's Cookies link and
 * the hero caption, and several public tap targets were far below 44 CSS px.
 * Real CSS is needed to prove any of it, so this is a browser spec.
 *
 * The describe title contains "page Page" — the CI grep discovery contract.
 */
const MIN_TAP = 44;

test.beforeEach(async ({ page }) => {
  await page.route("**/*", (route) =>
    !["GET", "HEAD"].includes(route.request().method()) ||
    /google-analytics|doubleclick|\/api\/funnel\//.test(route.request().url())
      ? route.fulfill({ status: 204, body: "" })
      : route.continue(),
  );
});

async function heights(locators: ReturnType<Page["locator"]>) {
  const boxes = await locators.evaluateAll((els) =>
    els.map((el) => {
      const r = el.getBoundingClientRect();
      return {
        label: (el.textContent ?? "").trim().slice(0, 40),
        w: Math.round(r.width * 10) / 10,
        h: Math.round(r.height * 10) / 10,
      };
    }),
  );
  return boxes;
}

test.describe("R19 mobile touch page Page", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("home: the FAB never sits on the footer legal links at the page bottom", async ({
    page,
  }) => {
    await page.goto("/");
    await expect(page.locator("#zantara-fab")).toBeVisible();
    for (const name of ["Privacy", "Terms", "Cookies"]) {
      const link = page.locator("footer").getByRole("link", {
        name,
        exact: true,
      });
      await expect
        .poll(
          async () => {
            await page.evaluate(() =>
              window.scrollTo(0, document.documentElement.scrollHeight),
            );
            return link.evaluate((el) => {
              const r = el.getBoundingClientRect();
              const hit = document.elementFromPoint(
                r.left + r.width / 2,
                r.top + r.height / 2,
              );
              return hit !== null && el.contains(hit);
            });
          },
          { message: `${name} link must be the topmost element at its centre` },
        )
        .toBe(true);
    }
  });

  test("home: the FAB does not cover the hero caption on first paint", async ({
    page,
  }) => {
    // 711px is the physical device's viewport height (the covered case).
    for (const height of [711, 844]) {
      await page.setViewportSize({ width: 390, height });
      await page.goto("/");
      await expect(page.locator("#zantara-fab")).toBeVisible();
      const caption = page.locator(".hero-caption");
      await expect(caption).toBeVisible();
      const overlap = await page.evaluate(() => {
        const a = document
          .querySelector(".hero-caption")!
          .getBoundingClientRect();
        const b = document
          .querySelector("#zantara-fab")!
          .getBoundingClientRect();
        const w = Math.min(a.right, b.right) - Math.max(a.left, b.left);
        const h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
        return w > 0 && h > 0 ? Math.round(w * h) : 0;
      });
      expect(overlap, `caption/FAB overlap area @${height}h`).toBe(0);
    }
  });

  test("news: topic pills are at least 44px tall", async ({ page }) => {
    await page.goto("/news");
    const pills = page
      .locator("section a")
      .filter({ hasText: /^(KITAS|Golden Visa)$/ });
    await expect(pills.first()).toBeVisible();
    const boxes = await heights(pills);
    expect(boxes.length).toBeGreaterThan(0);
    for (const b of boxes) expect(b.h, b.label).toBeGreaterThanOrEqual(MIN_TAP);
  });

  test("category page: category chips are at least 44px tall", async ({
    page,
  }) => {
    await page.goto("/business");
    const chips = page
      .locator("nav")
      .filter({ has: page.getByRole("button", { name: "Trends" }) })
      .getByRole("button");
    await expect(chips.first()).toBeVisible();
    const boxes = await heights(chips);
    expect(boxes.length).toBeGreaterThanOrEqual(7);
    for (const b of boxes) expect(b.h, b.label).toBeGreaterThanOrEqual(MIN_TAP);
  });

  test("news: footer category and service links are at least 44px tall", async ({
    page,
  }) => {
    await page.goto("/news");
    const links = page.locator("footer ul a");
    await expect(links.first()).toBeAttached();
    const boxes = await heights(links);
    expect(boxes.length).toBeGreaterThanOrEqual(12);
    for (const b of boxes) expect(b.h, b.label).toBeGreaterThanOrEqual(MIN_TAP);
  });

  test("news: the drawer close button is at least 44x44 and the trigger names its state", async ({
    page,
  }) => {
    await page.goto("/news");
    const trigger = page.getByRole("button", { name: "Open menu" });
    await expect(trigger).toBeVisible();
    await trigger.click();
    const close = page.getByRole("button", { name: "Close menu" });
    await expect(close).toBeVisible();
    const box = (await close.boundingBox())!;
    expect(box.width).toBeGreaterThanOrEqual(MIN_TAP);
    expect(box.height).toBeGreaterThanOrEqual(MIN_TAP);
  });
});
