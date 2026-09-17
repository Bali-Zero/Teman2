import { test, expect, type Page } from "@playwright/test";

/**
 * GARUDA VOA DELIBERA fase 2 (§8 guard 1) — `voa-tint.computed.guard`.
 *
 * FAILs if any element inside the R19 wrapper (`[data-garuda-voa="r19"]`)
 * carries a `color` or `background-color` whose HSL has saturation >= 15%
 * AND hue in [150, 300] (green/blue/purple), AND an absolute channel spread
 * (max−min of the 0-255 R/G/B values) of at least 20. Copper (~11.5°) and
 * the brand yellow (~45.3°) pass by construction; the dark ground's
 * `--state-info` grey (~201°, ~8% saturation) passes on the saturation
 * clause alone.
 *
 * The chroma clause exists because §8's rule, run literally against this
 * PR's own render, convicted `--bz-base` #121016 itself: at R18/G16/B22 its
 * HSL is h=260°, s=15.8% — just over the 15% floor — purely because
 * percentage saturation is unstable at very low lightness (l=7.5% here): a
 * 6-out-of-255 channel spread is not a perceptible hue to a person looking
 * at the screen, but the HSL formula reports it as a "15.8% saturated
 * purple-blue" anyway. Measured directly against the running dev server
 * before this clause existed (see this PR's own report for the failing
 * run). A lightness cutoff was considered and rejected — it would also
 * exempt a real dark, saturated fill at the same lightness (e.g. a navy
 * button background), which the guilt/innocence pair below pins: a
 * hypothetical dark-navy CTA bug at l=10.8%, chroma=29 still convicts,
 * while `--bz-base`'s chroma=6 and `--bz-elevated`'s chroma=5 (dark block,
 * `globals.css`) do not. 20 sits with clear margin on both sides of that
 * measured gap.
 *
 * Why this is a Playwright spec, not a vitest `.test.tsx` beside the other
 * VOA tests: see the docblock on `../playwright.voa-tint.config.ts` — jsdom
 * (this repo's vitest environment) does not resolve `var()` CSS custom
 * properties in `getComputedStyle`, verified empirically against this
 * repo's own jsdom before writing this file, and this entire surface is
 * built on `var()` tokens. Run via
 * `npx playwright test -c playwright.voa-tint.config.ts` — collected there
 * only (excluded from `playwright.config.ts`, see its own `testIgnore`),
 * because this funnel is gated by `GARUDA_PUBLIC_ENABLED` and this spec's
 * dedicated config is the one that sets it on its own `webServer`.
 *
 * Scope: reads the SIX purchase screens' computed paint. It does not itself
 * assert every mandatory state (empty/error/hover/focus/loading) for each
 * screen — that per-state matrix is `voa-order-state.coverage` (tracker) and
 * `voa-contrast.computed` (text contrast), named separately in §8. This
 * guard's one job is the tint band, on whatever the six routes render with
 * the fixtures below.
 */

const BANNED_SATURATION_MIN = 15;
const BANNED_HUE_MIN = 150;
const BANNED_HUE_MAX = 300;
/** Absolute 0-255 channel spread floor — see the docblock above for why
 * this exists and how 20 was measured. */
const BANNED_CHROMA_MIN = 20;

/** Parses a `getComputedStyle` colour string (`rgb(r, g, b)` /
 * `rgba(r, g, b, a)`) into channels. Returns null for anything else
 * (`transparent`, `rgba(0, 0, 0, 0)` still parses fine, keyword colours a
 * real browser never emits from `getComputedStyle` do not need handling). */
export function parseRgb(value: string): [number, number, number] | null {
  const m = value.match(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i);
  if (!m) return null;
  return [Number(m[1]), Number(m[2]), Number(m[3])];
}

export function rgbToHsl([r, g, b]: [number, number, number]): {
  h: number;
  s: number;
  l: number;
} {
  const rn = r / 255;
  const gn = g / 255;
  const bn = b / 255;
  const max = Math.max(rn, gn, bn);
  const min = Math.min(rn, gn, bn);
  const l = (max + min) / 2;
  if (max === min) return { h: 0, s: 0, l: l * 100 };
  const d = max - min;
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
  let h: number;
  switch (max) {
    case rn:
      h = (gn - bn) / d + (gn < bn ? 6 : 0);
      break;
    case gn:
      h = (bn - rn) / d + 2;
      break;
    default:
      h = (rn - gn) / d + 4;
  }
  return { h: h * 60, s: s * 100, l: l * 100 };
}

/** The entity this guard judges: a banned TINT, not a banned string. Reads
 * hue AND saturation together (cicatrix #3 — a hue-only scan convicts
 * copper, M4 in design-A-claude.md §0) — never a substring/spelling match.
 * The chroma clause (see the file docblock) keeps it from also convicting
 * a near-black/near-white neutral whose tiny absolute channel spread the
 * percentage-based saturation formula overstates. */
export function isBannedTint(rgb: [number, number, number] | null): boolean {
  if (!rgb) return false;
  const [r, g, b] = rgb;
  const chroma = Math.max(r, g, b) - Math.min(r, g, b);
  if (chroma < BANNED_CHROMA_MIN) return false;
  const { h, s } = rgbToHsl(rgb);
  if (s < BANNED_SATURATION_MIN) return false;
  return h >= BANNED_HUE_MIN && h <= BANNED_HUE_MAX;
}

test.describe("the tint classifier — guilt and innocence", () => {
  // GUILTY: the guard's own required guilt control (§8 guard 1) — raw slate
  // #233D52, the light block's --state-info (design-A-claude.md M2).
  test("convicts raw slate #233D52 — hue 207°, sat 40%", () => {
    expect(isBannedTint(parseRgb("rgb(35, 61, 82)"))).toBe(true);
  });

  test("convicts a plain CSS blue for the same reason", () => {
    expect(isBannedTint(parseRgb("rgb(37, 99, 235)"))).toBe(true);
  });

  test("convicts a teal-green in the banned band (hue 162°, chroma 100)", () => {
    expect(isBannedTint(parseRgb("rgb(20, 120, 90)"))).toBe(true);
  });

  test("still convicts a dark, saturated navy at low lightness — the chroma floor must not blind the guard to a real fill this dark (l=10.8%, chroma=29)", () => {
    expect(isBannedTint(parseRgb("rgb(13, 27, 42)"))).toBe(true);
  });

  // INNOCENT, each pinned with the reason a hue-only or spelling-only scan
  // would get wrong (over-match / under-match, cicatrix #3):
  test("acquits copper #A44B36 — hue 11.5°, a hue-only scan would flag it (M4)", () => {
    expect(isBannedTint(parseRgb("rgb(164, 75, 54)"))).toBe(false);
  });

  test("acquits brand yellow #F4C430 — hue 45.3°, outside the band regardless of saturation", () => {
    expect(isBannedTint(parseRgb("rgb(244, 196, 48)"))).toBe(false);
  });

  test("acquits the dark ground's --state-info grey — hue ~201° but sat ~8%, under the floor (M3)", () => {
    expect(isBannedTint(parseRgb("rgb(162, 171, 176)"))).toBe(false);
  });

  test("acquits the dark ground's --state-success forest mix — desaturated by the paper mix", () => {
    // color-mix(#253e33 40%, #f7f4ee) ≈ rgb(184, 189, 182), sat ~4.7%.
    expect(isBannedTint(parseRgb("rgb(184, 189, 182)"))).toBe(false);
  });

  test("acquits --bz-status-mark #D01033 — hue ~349°, the red family, outside the band", () => {
    expect(isBannedTint(parseRgb("rgb(208, 16, 51)"))).toBe(false);
  });

  test("acquits --bz-base #121016 itself — hue 260°/sat 15.8% on paper, but chroma 6 (see file docblock)", () => {
    expect(isBannedTint(parseRgb("rgb(18, 16, 22)"))).toBe(false);
  });

  test("acquits --bz-elevated/--bz-card #1A1A1F — same reason, chroma 5", () => {
    expect(isBannedTint(parseRgb("rgb(26, 26, 31)"))).toBe(false);
  });

  test("ignores an unparsable value instead of convicting it", () => {
    expect(isBannedTint(parseRgb("transparent"))).toBe(false);
    expect(isBannedTint(null)).toBe(false);
  });
});

const RESULT_ID_ACCEPT = "voa-tint-guard-accept";
const RESULT_ID_DECLINE = "voa-tint-guard-decline";
const RESULT_ID_UPLOAD = "voa-tint-guard-upload";
const RESULT_ID_CHECKOUT = "voa-tint-guard-checkout";
const ORDER_ID_TRACKER = "voa-tint-guard-order";

const ACCEPTED_BODY = {
  verdict: "ACCEPT",
  reason_codes: [],
  published_filing_deadline: "2026-11-01",
  price_idr: 2_500_000,
};

const DECLINED_BODY = {
  verdict: "DECLINE",
  reason_codes: ["NATIONALITY_NOT_ELIGIBLE"],
};

const ORDER_BODY = {
  order_id: ORDER_ID_TRACKER,
  order_state: "awaiting_payment",
  price_idr: 2_500_000,
  browser_observation: "browser_not_returned",
  practice: null,
};

/** Mocks every `/api/**` call the six routes below can make. No real
 * network call ever leaves the browser — mirrors the mocking pattern
 * `theme-toggle.spec.ts` / `bz-product-family.visual.spec.ts` already use
 * for this suite. Per-path bodies win over the generic fallback. */
async function mockVoaApi(page: Page): Promise<void> {
  await page.route("**/api/**", async (route) => {
    const url = route.request().url();
    if (url.includes(`/eligibility-checks/${RESULT_ID_ACCEPT}`)) {
      return route.fulfill({
        contentType: "application/json",
        body: JSON.stringify(ACCEPTED_BODY),
      });
    }
    if (url.includes(`/eligibility-checks/${RESULT_ID_DECLINE}`)) {
      return route.fulfill({
        contentType: "application/json",
        body: JSON.stringify(DECLINED_BODY),
      });
    }
    if (url.includes(`/eligibility-checks/${RESULT_ID_CHECKOUT}`)) {
      return route.fulfill({
        contentType: "application/json",
        body: JSON.stringify(ACCEPTED_BODY),
      });
    }
    if (url.includes(`/orders/${ORDER_ID_TRACKER}`)) {
      return route.fulfill({
        contentType: "application/json",
        body: JSON.stringify(ORDER_BODY),
      });
    }
    // Generic fallback for anything else the shell/analytics/tracker calls.
    return route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ data: {}, articles: [] }),
    });
  });
}

interface TintOffence {
  tag: string;
  cls: string;
  prop: "color" | "backgroundColor";
  value: string;
}

/** Walks every element inside `scopeSelector` and returns its computed
 * `color` and `background-color` — raw values only; classification
 * (`isBannedTint`) happens back on the Node side so the SAME function the
 * guilt/innocence tests above pin is the one judging the real page. */
async function readComputedTints(
  page: Page,
  scopeSelector: string,
): Promise<TintOffence[]> {
  return page.evaluate((selector) => {
    const root = document.querySelector(selector);
    if (!root) return [];
    const nodes = [root, ...Array.from(root.querySelectorAll("*"))];
    const out: Array<{
      tag: string;
      cls: string;
      prop: "color" | "backgroundColor";
      value: string;
    }> = [];
    for (const el of nodes) {
      const cs = getComputedStyle(el as Element);
      const cls =
        typeof (el as Element).className === "string"
          ? (el as Element).className
          : ((el as Element).getAttribute("class") ?? "");
      out.push({
        tag: (el as Element).tagName,
        cls,
        prop: "color",
        value: cs.color,
      });
      out.push({
        tag: (el as Element).tagName,
        cls,
        prop: "backgroundColor",
        value: cs.backgroundColor,
      });
    }
    return out;
  }, scopeSelector);
}

async function assertNoBannedTint(page: Page): Promise<void> {
  const wrapper = page.locator('[data-garuda-voa="r19"]');
  await expect(wrapper).toBeVisible();
  const reads = await readComputedTints(page, '[data-garuda-voa="r19"]');
  const offences = reads.filter((r) => isBannedTint(parseRgb(r.value)));
  expect(
    offences,
    `banned tint found:\n${offences
      .map(
        (o) =>
          `  <${o.tag.toLowerCase()} class="${o.cls}"> ${o.prop}: ${o.value}`,
      )
      .join("\n")}`,
  ).toEqual([]);
}

test.describe("GARUDA VOA — no banned tint on the six purchase screens (operative-dark)", () => {
  test.beforeEach(async ({ page }) => {
    await mockVoaApi(page);
  });

  test("wizard", async ({ page }) => {
    await page.goto("/visa/voa");
    await assertNoBannedTint(page);
  });

  test("verdict — ACCEPT", async ({ page }) => {
    await page.goto(`/visa/voa/${RESULT_ID_ACCEPT}`);
    await assertNoBannedTint(page);
  });

  test("verdict — DECLINE", async ({ page }) => {
    await page.goto(`/visa/voa/${RESULT_ID_DECLINE}`);
    await assertNoBannedTint(page);
  });

  test("upload", async ({ page }) => {
    await page.goto(`/visa/voa/upload/${RESULT_ID_UPLOAD}`);
    await assertNoBannedTint(page);
  });

  test("checkout", async ({ page }) => {
    await page.goto(`/visa/voa/checkout/${RESULT_ID_CHECKOUT}`);
    await assertNoBannedTint(page);
  });

  test("tracker", async ({ page }) => {
    await page.goto(`/visa/voa/orders/${ORDER_ID_TRACKER}`);
    await assertNoBannedTint(page);
  });
});
