import { test, expect } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("**/*", (route) =>
    !["GET", "HEAD"].includes(route.request().method()) ||
    /google-analytics|doubleclick|\/api\/funnel\//.test(route.request().url())
      ? route.fulfill({ status: 204, body: "" })
      : route.continue(),
  );
});

test.afterEach(async ({ page }) => {
  await page.close();
});

type Rgba = [number, number, number, number];
const parseColor = (css: string): Rgba => {
  const [r, g, b, a] = css.match(/[\d.]+/g)!.map(Number);
  return [r, g, b, a ?? 1];
};
const over = (fg: Rgba, bg: Rgba): Rgba => [
  fg[0] * fg[3] + bg[0] * (1 - fg[3]),
  fg[1] * fg[3] + bg[1] * (1 - fg[3]),
  fg[2] * fg[3] + bg[2] * (1 - fg[3]),
  1,
];
const luminance = ([r, g, b]: Rgba) => {
  const [lr, lg, lb] = [r, g, b].map((v) => {
    const c = v / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * lr + 0.7152 * lg + 0.0722 * lb;
};
const contrast = (a: Rgba, b: Rgba) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

test.describe("R19 integration page Page", () => {
  for (const width of [980, 981, 1024]) {
    test(`header and sticky photo stay aligned at ${width}px`, async ({
      page,
    }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.goto("/news");
      await page.evaluate(() => document.fonts.ready);
      const photo = page
        .locator('div[class*="md:sticky"][class*="md:max-h-"]')
        .first();
      await expect(photo).toBeVisible();
      await page.evaluate(() => document.fonts.ready);
      const target = await photo.evaluate(
        (el) => el.getBoundingClientRect().top + scrollY,
      );
      await page.evaluate(
        (y) => scrollTo({ top: y + 60, behavior: "instant" }),
        target,
      );
      await expect
        .poll(() =>
          photo.evaluate((el) =>
            Math.abs(
              el.getBoundingClientRect().top -
                document.querySelector("nav")!.getBoundingClientRect().bottom,
            ),
          ),
        )
        .toBeLessThanOrEqual(1);
      const nav = await page
        .locator("nav")
        .first()
        .evaluate((el) => ({
          height: el.getBoundingClientRect().height,
          wrappedLinks: [...el.querySelectorAll("[data-nav-center] a")].filter(
            (a) => a.getBoundingClientRect().height > 44,
          ).length,
        }));
      expect(nav.height).toBe(width < 981 ? 72 : 88);
      expect(nav.wrappedLinks).toBe(0);
    });
  }

  test("portal has a visible keyboard focus ring and aligned header", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/news");
    const trigger = page.getByRole("button", { name: "Open menu" });
    // Reach the real trigger with the keyboard, then exercise Radix autofocus.
    for (
      let i = 0;
      i < 30 &&
      !(await trigger.evaluate((el) => el === document.activeElement));
      i++
    ) {
      await page.keyboard.press("Tab");
    }
    await expect(trigger).toBeFocused();
    await page.keyboard.press("Enter");
    const dialog = page.locator('[role="dialog"]');
    const close = page.getByRole("button", { name: "Close menu" });
    await expect(close).toBeFocused();
    await page.keyboard.press("Shift+Tab");
    await expect(
      dialog.getByRole("link", { name: "Login", exact: true }),
    ).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(close).toBeFocused();
    const focusableCount = await dialog.locator("a[href],button").count();
    for (const key of ["Tab", "Shift+Tab"]) {
      for (let i = 0; i < focusableCount; i++) {
        await page.keyboard.press(key);
        await expect
          .poll(() =>
            dialog.evaluate((el) => el.contains(document.activeElement)),
          )
          .toBe(true);
      }
      await expect(close).toBeFocused();
    }
    const style = await close.evaluate((el) => {
      const s = getComputedStyle(el);
      return {
        color: s.outlineColor,
        width: s.outlineWidth,
        row: el.parentElement!.getBoundingClientRect().height,
      };
    });
    expect(style).toEqual({ color: "rgb(164, 75, 54)", width: "2px", row: 72 });
    expect(
      await page
        .getByRole("dialog")
        .evaluate((el) => getComputedStyle(el).minHeight),
    ).toBe("0px");
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    await expect(trigger).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(close).toBeFocused();
    await page.setViewportSize({ width: 981, height: 844 });
    // DOM locator deliberately includes hidden nodes at the desktop breakpoint.
    await expect(dialog).toHaveCount(0);
    // Radix restores body interaction in its unmount effect, after DOM removal.
    await expect
      .poll(
        () =>
          page
            .locator("body")
            .evaluate((el) => getComputedStyle(el).pointerEvents),
        { timeout: 1000 },
      )
      .not.toBe("none");
  });

  test("home hero and FAB retain visible focus on their own backgrounds", async ({
    page,
  }) => {
    await page.goto("/");
    await page.keyboard.press("Tab");
    const heroLink = page.locator(".entry-hero .entry-categories a").first();
    await heroLink.focus();
    // Light hero: the ring is judged by contrast, not by a pinned colour. It
    // must clear 3:1 (WCAG 1.4.11) against the link's own surface as painted
    // over the hero ground, and against the hero ground itself. The ring
    // floats in the offset gap over the illustration, which is not sampled.
    const ring = await heroLink.evaluate((el) => {
      const s = getComputedStyle(el);
      return {
        style: s.outlineStyle,
        width: parseFloat(s.outlineWidth),
        color: s.outlineColor,
        surface: s.backgroundColor,
        ground: getComputedStyle(el.closest(".entry-hero")!).backgroundColor,
      };
    });
    expect(ring.style).toBe("solid");
    expect(ring.width).toBeGreaterThanOrEqual(2);
    const ground = parseColor(ring.ground);
    const surface = over(parseColor(ring.surface), ground);
    expect(contrast(parseColor(ring.color), surface)).toBeGreaterThanOrEqual(3);
    expect(contrast(parseColor(ring.color), ground)).toBeGreaterThanOrEqual(3);
    const heading = page.locator("h1").first();
    // Variable face: the computed weight must lie inside the face's declared
    // axis and that face must be loaded, so the browser has nothing to fake.
    const face = await page.evaluate(async () => {
      await document.fonts.ready;
      const s = getComputedStyle(document.querySelector("h1")!);
      const weight = Number(s.fontWeight);
      const faces = [...document.fonts]
        .filter((f) => f.family.replace(/["']/g, "") === "R19 Home Fraunces")
        .map((f) => ({ status: f.status, weight: f.weight }));
      return {
        family: s.fontFamily,
        weight,
        faces,
        applied: document.fonts.check(`${weight} 1em "R19 Home Fraunces"`),
      };
    });
    expect(face.family).toMatch(/^"R19 Home Fraunces"/);
    expect(face.faces.length).toBeGreaterThan(0);
    expect(face.faces.every((f) => f.status === "loaded")).toBe(true);
    expect(
      face.faces.some((f) => {
        const [lo, hi = lo] = f.weight.split(/\s+/).map(Number);
        return lo <= face.weight && face.weight <= hi;
      }),
    ).toBe(true);
    expect(face.applied).toBe(true);
    expect(await heading.count()).toBe(1);
    await page.goto("/news");
    const fab = page.locator("#zantara-fab");
    await page.keyboard.press("Tab");
    await fab.focus();
    await expect
      .poll(() => fab.evaluate((el) => getComputedStyle(el).outlineColor))
      .toBe("rgb(164, 75, 54)");
    expect(
      await page
        .locator(".brand-tagline")
        .evaluate((el) => getComputedStyle(el).textShadow),
    ).toBe("none");
  });

  test("home CTA geometry stays stable while the display fonts arrive", async ({
    page,
  }) => {
    let releaseFonts!: () => void;
    let requestedFonts = 0;
    const blocked = new Promise<void>((resolve) => {
      releaseFonts = resolve;
    });
    await page.route("**/fonts/*-r19-home.woff2", async (route) => {
      requestedFonts++;
      await blocked;
      await route.continue();
    });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/", { waitUntil: "domcontentloaded" });
    const button = page.locator(".entry-hero .entry-categories a").first();
    await button.waitFor({ state: "visible" });
    const geometry = () =>
      button.evaluate((el) => ({
        width: el.getBoundingClientRect().width,
        arrowX: el.querySelector("span")!.getBoundingClientRect().x,
      }));
    const fontsLoaded = () =>
      page.evaluate(() => [
        document.fonts.check('400 15px "R19 Home Manrope"'),
        document.fonts.check('500 38px "R19 Home Fraunces"'),
      ]);
    const before = await geometry();
    try {
      await expect.poll(() => requestedFonts).toBe(2);
      expect(await fontsLoaded()).toEqual([false, false]);
    } finally {
      releaseFonts();
    }
    await page.evaluate(() => document.fonts.ready);
    expect(await fontsLoaded()).toEqual([true, true]);
    const after = await geometry();
    expect(Math.abs(before.width - after.width)).toBeLessThanOrEqual(0.1);
    expect(Math.abs(before.arrowX - after.arrowX)).toBeLessThanOrEqual(0.1);
  });

  for (const [language, heading] of Object.entries({
    en: "A considered next step for everyone building a home and a lasting business in Indonesia, with room for every question along the way",
    id: "Langkah berikutnya yang terencana bagi setiap orang yang membangun rumah dan usaha berkelanjutan di Indonesia, sekarang dan pada masa mendatang",
    cjk: "在印度尼西亚建立家园和发展事业的每一个人都值得拥有清晰可靠的下一步计划，让今天的每一个决定都能支持未来的长期生活与事业",
  })) {
    for (const width of [360, 1440]) {
      test(`long ${language} home heading preserves the primary action at ${width}px`, async ({
        page,
      }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.goto("/");
        await page.evaluate(() => document.fonts.ready);
        const heroHeight = () =>
          page
            .locator(".entry-hero")
            .evaluate((el) => el.getBoundingClientRect().height);
        const baseline = await heroHeight();
        await page.getByRole("heading", { level: 1 }).evaluate((el, text) => {
          el.textContent = text;
        }, heading);
        const geometry = await page.evaluate(() => {
          const rect = (selector: string) => {
            const r = document.querySelector(selector)!.getBoundingClientRect();
            return { top: r.top, bottom: r.bottom };
          };
          return {
            nav: rect(".site-header"),
            hero: rect(".entry-hero"),
            title: rect("h1"),
            cta: rect(".entry-hero .entry-categories li:last-child a"),
            overflow: document.documentElement.scrollWidth - innerWidth,
          };
        });
        expect(geometry.title.top).toBeGreaterThanOrEqual(geometry.nav.bottom);
        expect(geometry.cta.bottom).toBeLessThanOrEqual(geometry.hero.bottom);
        expect(geometry.overflow).toBeLessThanOrEqual(1);
        // A heading that runs away must show up as a hero that ballooned.
        expect(await heroHeight()).toBeLessThanOrEqual(baseline * 1.5);
        // The last action stays reachable: nothing (the caption included)
        // sits on top of its centre or intersects its box.
        const covered = await page.evaluate(() => {
          const last = document.querySelector<HTMLElement>(
            ".entry-hero .entry-categories li:last-child a",
          )!;
          last.scrollIntoView({ block: "center" });
          const l = last.getBoundingClientRect();
          const hit = document.elementFromPoint(
            l.left + l.width / 2,
            l.top + l.height / 2,
          );
          const c = document
            .querySelector(".entry-hero .hero-caption")!
            .getBoundingClientRect();
          return {
            reachable: !!hit && last.contains(hit),
            captionOverlaps: !(
              c.right <= l.left ||
              c.left >= l.right ||
              c.bottom <= l.top ||
              c.top >= l.bottom
            ),
          };
        });
        expect(covered).toEqual({ reachable: true, captionOverlaps: false });
      });
    }
  }

  for (const route of ["/v2", "/property"]) {
    test(`${route} retains the existing dark navigation`, async ({ page }) => {
      await page.goto(route);
      await expect(page.locator('[data-presentation="r19"]')).toHaveCount(0);
      const color = await page
        .locator("nav")
        .first()
        .evaluate((el) => getComputedStyle(el).backgroundColor);
      const rgb = color
        .match(/[\d.]+/g)!
        .slice(0, 3)
        .map(Number);
      expect(0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]).toBeLessThan(
        90,
      );
    });
  }
});
