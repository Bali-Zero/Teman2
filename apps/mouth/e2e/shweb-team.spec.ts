import { test, expect, type Page } from "@playwright/test";

/**
 * SHWEB-20260911 / W2-WEB-TEAM — the browser half of the acceptance.
 *
 * Three things are checked here and nowhere else:
 *  1. the two people the owner excluded are absent from every PUBLIC surface,
 *     under either spelling and through no photo path either;
 *  2. the R19 composition actually shipped — the measures, not just the filter
 *     (container width, the founder-band portrait, the 44/48px targets);
 *  3. the page behaves at 360 → 1440: no horizontal overflow, visible focus,
 *     decoded portraits, measured contrast on the text this window introduces.
 */

const EXCLUDED = /faisha|faysha|sahira/i;
const EXCLUDED_PHOTOS = [
  "/static/team/faisha.jpg",
  "/static/team/sahira.jpg",
] as const;

const VIEWPORTS = [
  { name: "360", width: 360, height: 780 },
  { name: "390", width: 390, height: 844 },
  { name: "768", width: 768, height: 1024 },
  { name: "1280", width: 1280, height: 800 },
  { name: "1440", width: 1440, height: 900 },
] as const;

/** Relative luminance per WCAG 2.x, from a computed `rgb()/rgba()` string. */
function luminance(color: string): number {
  const m = color.match(/\d+(\.\d+)?/g);
  if (!m) throw new Error(`unparsable colour: ${color}`);
  const [r, g, b] = m.slice(0, 3).map((v) => {
    const c = Number(v) / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(fg: string, bg: string): number {
  const a = luminance(fg);
  const b = luminance(bg);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

async function expectNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(
    () =>
      document.documentElement.scrollWidth -
      document.documentElement.clientWidth,
  );
  expect(overflow, "horizontal overflow in px").toBeLessThanOrEqual(1);
}

test.describe("W2 — the two excluded people are on no public surface", () => {
  for (const path of [
    "/team",
    "/",
    "/v2",
    "/v2/company/about",
    "/book/team",
    "/book",
  ]) {
    test(`${path} publishes neither of them`, async ({ page }) => {
      const response = await page.goto(path, { waitUntil: "domcontentloaded" });
      expect(response?.status(), `${path} did not answer 200`).toBe(200);
      // Hydration, not the network: these pages keep a long-poll open, so
      // `networkidle` never settles and would time the sweep out instead of
      // measuring it.
      await page
        .locator("main, body > div")
        .first()
        .waitFor({ state: "attached" });

      const html = await page.content();
      expect(html, `${path} still names one of them`).not.toMatch(EXCLUDED);
      for (const photo of EXCLUDED_PHOTOS) {
        expect(html, `${path} still links ${photo}`).not.toContain(photo);
      }
    });
  }
});

test.describe("W2 — /team keeps the directory it had, plus the tool links", () => {
  test("every other person is still listed", async ({ page }) => {
    await page.goto("/team", { waitUntil: "domcontentloaded" });

    for (const name of [
      "Pak Heru",
      "Zainal Abidin",
      "Ruslana",
      "Veronika",
      "Adit",
      "Ari",
      "Krisna",
      "Dea",
      "Candra",
      "Vino",
      "Angel",
      "Kadek",
      "Dewa Ayu",
      "Asya Nadia",
      "Rina",
      "Zero",
      "Surya",
      "Damar",
      "Subhi",
    ]) {
      await expect(
        page.getByRole("heading", { name, level: 3 }),
        `${name} is missing from /team`,
      ).toBeVisible();
    }
  });

  test("the tool owners reach their real tool", async ({ page }) => {
    await page.goto("/team", { waitUntil: "domcontentloaded" });

    const studio = page.getByRole("link", { name: /Second Home Studio/i });
    await expect(studio).toHaveAttribute("href", "/visa/second-home/studio");
    await studio.click();
    await page.waitForURL(/\/visa\/second-home\/studio/);
    expect(page.url()).toContain("/visa/second-home/studio");
    // a real page, not a 200 not-found body
    await expect(page).toHaveTitle(/Second Home/i);

    await page.goto("/team", { waitUntil: "domcontentloaded" });
    const evoa = page.getByRole("link", { name: /E-VOA/i });
    await expect(evoa).toHaveAttribute("href", "/visa/voa");
    await evoa.click();
    await page.waitForURL(/\/visa\/voa/);
    expect(page.url()).toContain("/visa/voa");
    await expect(page).toHaveTitle(/Visa on Arrival/i);
  });

  test("the section nav reaches every section it names", async ({ page }) => {
    await page.goto("/team", { waitUntil: "domcontentloaded" });

    const nav = page.getByRole("navigation", { name: "Team sections" });
    const links = await nav.getByRole("link").all();
    expect(links.length).toBe(5);
    for (const link of links) {
      const href = await link.getAttribute("href");
      expect(href).toMatch(/^#/);
      await expect(page.locator(href!)).toHaveCount(1);
    }
  });
});

test.describe("W2 — the R19 composition actually shipped", () => {
  test("/team uses the reference container and directory grid at 1440", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/team", { waitUntil: "domcontentloaded" });

    // container: width min(1320px, 90%) → 1320 at 1440 (allowing the scrollbar)
    const intro = page.locator("h1").first();
    const width = await intro.evaluate((el) => {
      const page = el.closest("div")?.parentElement as HTMLElement;
      return page.getBoundingClientRect().width;
    });
    expect(width).toBeGreaterThan(1280);
    expect(width).toBeLessThanOrEqual(1320);

    // the directory of a responsibility group is 3 columns
    const columns = await page.evaluate(() => {
      const heading = document.getElementById("setup");
      const group = heading?.closest("section");
      const directory = group?.lastElementChild as HTMLElement;
      return getComputedStyle(directory).gridTemplateColumns.split(" ").length;
    });
    expect(columns).toBe(3);
  });

  test("the home founder band carries the reference portrait geometry", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/", { waitUntil: "domcontentloaded" });

    const band = page.locator("figure", { hasText: "Zainal Abidin" }).first();
    await expect(band).toBeVisible();
    const portrait = band.locator("img").first();
    const box = await portrait.boundingBox();
    expect(box?.width, "founder portrait width").toBeCloseTo(78, 0);
    expect(box?.height, "founder portrait height").toBeCloseTo(94, 0);

    const radius = await band
      .locator("div")
      .first()
      .evaluate((el) => getComputedStyle(el).borderRadius);
    expect(radius.replace(/\s+/g, " ")).toContain("48px 48px 3px 3px");

    // only the founders on the home — the four-row list belongs to /v2
    await expect(page.getByText("The team behind them")).toHaveCount(0);
    const link = page.getByRole("link", { name: /Meet the team/i });
    await expect(link).toHaveAttribute("href", "/team");
    const linkBox = await link.boundingBox();
    expect(linkBox?.height, "band link target height").toBeGreaterThanOrEqual(
      48,
    );
  });

  test("/v2 still renders the default: founders AND the four behind them", async ({
    page,
  }) => {
    await page.goto("/v2", { waitUntil: "domcontentloaded" });

    await expect(page.getByText("The team behind them")).toBeVisible();
    for (const name of ["Ruslana", "Veronika", "Adit", "Angel"]) {
      await expect(
        page.getByText(name).first(),
        `${name} missing on /v2`,
      ).toBeVisible();
    }
    await expect(page.getByRole("link", { name: /All 18\+/ })).toBeVisible();
  });
});

test.describe("W2 — /team at every viewport", () => {
  for (const vp of VIEWPORTS) {
    test(`${vp.name}px: no overflow, portraits decoded, targets ≥44px`, async ({
      page,
    }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto("/team", { waitUntil: "domcontentloaded" });

      await expectNoHorizontalOverflow(page);

      // every portrait that has a photo actually decoded
      const broken = await page.evaluate(() =>
        Array.from(document.images)
          .filter((img) => img.src.includes("/static/team/"))
          .filter((img) => !img.complete || img.naturalWidth === 0)
          .map((img) => img.src),
      );
      expect(broken, "portraits that did not decode").toEqual([]);

      // interactive targets inside the directory
      const small = await page.evaluate(() => {
        const root = document.querySelector("nav[aria-label='Team sections']")
          ?.parentElement?.parentElement;
        if (!root) return ["directory root not found"];
        return Array.from(root.querySelectorAll("a"))
          .filter((a) => (a as HTMLElement).offsetParent !== null)
          .map((a) => ({
            text: (a.textContent ?? "").trim().slice(0, 24),
            h: a.getBoundingClientRect().height,
          }))
          .filter((t) => t.h < 44)
          .map((t) => `${t.text} = ${Math.round(t.h)}px`);
      });
      expect(small, "targets under 44px").toEqual([]);
    });
  }

  test("keyboard reaches the directory and focus stays visible", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/team", { waitUntil: "domcontentloaded" });

    const seen: string[] = [];
    for (let i = 0; i < 40; i++) {
      await page.keyboard.press("Tab");
      const info = await page.evaluate(() => {
        const el = document.activeElement as HTMLElement | null;
        if (!el || el === document.body) return null;
        const s = getComputedStyle(el);
        return {
          tag: el.tagName,
          href: el.getAttribute("href") ?? "",
          outlined:
            s.outlineStyle !== "none" ||
            s.boxShadow !== "none" ||
            s.borderBottomColor !== "rgba(0, 0, 0, 0)",
        };
      });
      if (!info) continue;
      seen.push(info.href);
      expect(
        info.outlined,
        `focused ${info.tag} ${info.href} shows no focus`,
      ).toBe(true);
      if (info.href === "/visa/second-home/studio") break;
    }
    expect(seen, "the Studio link was never reached by keyboard").toContain(
      "/visa/second-home/studio",
    );
  });

  test("the text this window introduces clears the contrast floor", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/team", { waitUntil: "domcontentloaded" });

    const samples = await page.evaluate(() => {
      const pick = (el: Element | null) => {
        if (!el) return null;
        const s = getComputedStyle(el as HTMLElement);
        let bgEl: HTMLElement | null = el as HTMLElement;
        let bg = "rgba(0, 0, 0, 0)";
        while (bgEl) {
          const c = getComputedStyle(bgEl).backgroundColor;
          if (c && c !== "rgba(0, 0, 0, 0)" && c !== "transparent") {
            bg = c;
            break;
          }
          bgEl = bgEl.parentElement;
        }
        return {
          label: (el.textContent ?? "").trim().slice(0, 28),
          fg: s.color,
          bg,
          size: parseFloat(s.fontSize),
          weight: Number(s.fontWeight),
        };
      };
      const group = document.getElementById("setup")?.closest("section");
      return [
        pick(document.querySelector("nav[aria-label='Team sections'] a")),
        pick(group?.querySelector("h2") ?? null),
        pick(group?.querySelectorAll("p")[0] ?? null), // group description
        pick(group?.querySelector("article p") ?? null), // a person's role label
        pick(document.querySelector("a[href='/visa/second-home/studio']")),
      ].filter(Boolean);
    });

    expect(samples.length).toBe(5);
    for (const s of samples as Array<{
      label: string;
      fg: string;
      bg: string;
      size: number;
      weight: number;
    }>) {
      const large = s.size >= 24 || (s.size >= 18.66 && s.weight >= 700);
      const floor = large ? 3 : 4.5;
      const ratio = contrast(s.fg, s.bg);
      expect(
        ratio,
        `"${s.label}" ${s.fg} on ${s.bg} = ${ratio.toFixed(2)}:1 (floor ${floor})`,
      ).toBeGreaterThanOrEqual(floor);
    }
  });
});
