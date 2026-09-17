import { readFileSync } from "node:fs";
import { join } from "node:path";
import { test, expect, type Page } from "@playwright/test";
import { VOA_PRIMARY_ACTION_STYLE } from "../src/app/visa/voa/voa-action-style";

/**
 * GARUDA VOA — design-A-claude.md §8 guard #4: "assert the computed
 * `background-color` of the primary CTA on checkout, verdict and tracker is
 * not in the red family. M6 is one specificity accident from red." (M6:
 * `background: var(--accent-funnel, #ff3344)`, the fallback this PR removes
 * at all four call sites.)
 *
 * WHY THIS IS A PLAYWRIGHT SPEC, NOT A VITEST `.test.tsx` — said explicitly,
 * per the instruction that a jsdom guard should be tried first and a
 * Playwright spec used only if jsdom genuinely cannot do it. It cannot:
 * verified empirically before writing this file (rendered a button with
 * `style={{ background: "var(--state-success)" }}` inside a wrapper that
 * sets `--state-success` inline, then read
 * `getComputedStyle(button).backgroundColor` under vitest/jsdom). Result:
 * `background` came back as the UNRESOLVED string `"var(--state-success)"`
 * and `backgroundColor` came back `"rgba(0, 0, 0, 0)"` — jsdom has no CSS
 * cascade engine and does not resolve custom properties through
 * `getComputedStyle`, matching this codebase's own precedent
 * (`clients-desk.test.tsx`: "jsdom applies no stylesheet (no layout engine)
 * — a getComputedStyle assertion here would be a no-op that always
 * 'passes'"). A file at the vitest-scanned path/extension the mandate named
 * would silently be collected by `vitest.config.ts`'s
 * `include: ["src/**\/*.test.{ts,tsx}"]` and run under jsdom — i.e. it would
 * assert nothing while reporting green. That is worse than not writing it,
 * so this lives under `e2e/` instead, where a REAL Chromium resolves the
 * REAL `color-mix()`/`var()` chain from the REAL `globals.css`.
 *
 * SCOPE — deliberately narrower than "all three screens live", and why.
 * Rendering checkout/verdict/tracker through the actual app requires either
 * flipping `GARUDA_PAYMENTS_LIVE` (checkout's form is gated behind it, and
 * it is DISARMED in production today per the mission's own delibera — not
 * a flag this PR's worktree should flip in the shared `playwright.config.ts`
 * webServer, since that env applies to every spec in the suite) or mocking
 * two different backend contracts (eligibility-check GET for verdict,
 * order-tracking GET for tracker) to reach an error/decline state — each a
 * meaningfully larger task than this CTA-removal PR's one theme. All three
 * sites instead share ONE constant, `VOA_PRIMARY_ACTION_STYLE`
 * (`voa-action-style.ts`), spread verbatim into their `style={{...}}` — so
 * this spec renders that EXACT constant, resolved against the EXACT
 * `[data-theme][data-product="my"]` blocks `globals.css` declares, in a
 * real browser. Proving the shared constant never resolves to red proves it
 * for all four usages transitively, without needing to reach each screen's
 * live data. A full live-app version (once payments are live, or with
 * hand-off route mocks) is a natural follow-up, not this PR's.
 */

const GLOBALS_CSS_PATH = join(__dirname, "..", "src", "app", "globals.css");

/** Extracts one `selector { ... }` block, brace-depth aware (nested rules included). */
function extractBlock(css: string, selector: string): string {
  const start = css.indexOf(`${selector} {`);
  if (start === -1) {
    throw new Error(`${selector} not found in globals.css`);
  }
  let depth = 0;
  let i = css.indexOf("{", start);
  for (; i < css.length; i++) {
    if (css[i] === "{") depth++;
    else if (css[i] === "}") {
      depth--;
      if (depth === 0) break;
    }
  }
  return css.slice(start, i + 1);
}

const globalsCss = readFileSync(GLOBALS_CSS_PATH, "utf8");
const LIGHT_MY_BLOCK = extractBlock(
  globalsCss,
  '[data-theme="operative-light"][data-product="my"]',
);
const DARK_MY_BLOCK = extractBlock(
  globalsCss,
  '[data-theme="operative-dark"][data-product="my"]',
);

/**
 * `getComputedStyle().backgroundColor` -> `{r, g, b}` in [0, 1]. Chromium
 * reports a plain `color-mix()` result (the dark theme's `--state-success`)
 * in the CSS Color 4 `color(srgb r g b)` function, NOT `rgb()` — measured
 * running this very spec: `color(srgb 0.639216 0.671373 0.64)` for the dark
 * block. Both forms are handled; a computed colour outside both shapes
 * throws rather than silently misreading it as innocent.
 */
function computedColourToRgb01(value: string): {
  r: number;
  g: number;
  b: number;
} {
  const colorFn = value.match(/^color\(srgb\s+([^)]+)\)$/);
  if (colorFn) {
    const [r, g, b] = colorFn[1].trim().split(/\s+/).map(Number);
    return { r, g, b };
  }
  const rgbFn = value.match(/rgba?\(([^)]+)\)/);
  if (rgbFn) {
    const [r, g, b] = rgbFn[1]
      .split(",")
      .slice(0, 3)
      .map((n) => Number(n.trim()) / 255);
    return { r, g, b };
  }
  throw new Error(`unrecognised computed colour shape: ${value}`);
}

/** Computed colour string -> `{h, s, l}` (h in degrees, s/l in %). */
function rgbStringToHsl(rgb: string): { h: number; s: number; l: number } {
  const { r, g, b } = computedColourToRgb01(rgb);
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;
  if (max === min) return { h: 0, s: 0, l: l * 100 };
  const d = max - min;
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
  let h: number;
  switch (max) {
    case r:
      h = ((g - b) / d + (g < b ? 6 : 0)) * 60;
      break;
    case g:
      h = ((b - r) / d + 2) * 60;
      break;
    default:
      h = ((r - g) / d + 4) * 60;
  }
  return { h, s: s * 100, l: l * 100 };
}

/** Design doc §8 guard #4's own red-family definition: hue 340-360 or 0-20, sat >= 15%. */
function isRedFamily(hsl: { h: number; s: number }): boolean {
  const inRedHue = hsl.h >= 340 || hsl.h <= 20;
  return inRedHue && hsl.s >= 15;
}

async function computedBackgroundHsl(
  page: Page,
  {
    myBlock,
    theme,
    background,
  }: { myBlock: string; theme: string; background: string },
): Promise<{ h: number; s: number; l: number }> {
  await page.setContent(
    `<!doctype html><html><head><style>${myBlock}</style></head>` +
      `<body><div data-theme="${theme}" data-product="my">` +
      `<button id="cta" style="background: ${background};">Continue to payment</button>` +
      `</div></body></html>`,
  );
  const rgb = await page
    .locator("#cta")
    .evaluate((el) => getComputedStyle(el).backgroundColor);
  return rgbStringToHsl(rgb);
}

test.describe("VOA_PRIMARY_ACTION_STYLE computed background (guard #4)", () => {
  test("the hue/sat classifier is GUILTY on the retired red literal (guilt control)", async ({
    page,
  }) => {
    const hsl = await computedBackgroundHsl(page, {
      myBlock: LIGHT_MY_BLOCK,
      theme: "operative-light",
      background: "#ff3344",
    });
    expect(isRedFamily(hsl)).toBe(true);
  });

  test("VOA_PRIMARY_ACTION_STYLE resolves OFF the red family on the light ground (today's mounted theme)", async ({
    page,
  }) => {
    const hsl = await computedBackgroundHsl(page, {
      myBlock: LIGHT_MY_BLOCK,
      theme: "operative-light",
      background: VOA_PRIMARY_ACTION_STYLE.background as string,
    });
    expect(isRedFamily(hsl)).toBe(false);
  });

  test("VOA_PRIMARY_ACTION_STYLE resolves OFF the red family on the dark ground (S1's candidate flip)", async ({
    page,
  }) => {
    const hsl = await computedBackgroundHsl(page, {
      myBlock: DARK_MY_BLOCK,
      theme: "operative-dark",
      background: VOA_PRIMARY_ACTION_STYLE.background as string,
    });
    expect(isRedFamily(hsl)).toBe(false);
  });
});
