import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { UploadFlow } from "./upload/UploadFlow";
import { messageFor, COPY_UNREADABLE_INSTRUCTION } from "./upload/messages";
import VoaEligibilityPage from "./page";
import VoaResultPage from "./[hash]/page";
import { CheckoutFlow } from "./checkout/[resultId]/CheckoutFlow";
import { EXCEPTION_RULE, OrderTracker } from "./orders/OrderTracker";

/**
 * GARUDA VOA DELIBERA (d) / design-A-claude.md §8 guard 2: an error message
 * must clear 4.5:1 against its own background, and it must never be carried
 * by a red-family Tailwind utility. This is the guard for the seven sites
 * lane S3 cured (M1: `text-red-600` at `upload/UploadFlow.tsx:182,215,223`,
 * 4.40:1 on paper — an AA fail; and the four `role="alert"` sites that read
 * `--color-error`, which resolves to copper on this surface — ownership, not
 * an error status).
 *
 * SCOPE, stated so this guard's green is never read as more than it proves
 * (cicatrix family #3 — a guard must declare what it does not see, same
 * discipline as `desk-no-red.guard.test.ts`). This file checks the ERROR-TONE
 * elements this PR touched — one per screen it changed (upload's three
 * states, the wizard's submit failure, the verdict page's magic-link
 * failure, checkout's order failure, the tracker's load failure). It does
 * NOT walk every text node on all six purchase screens; that fuller sweep is
 * a different, larger guard (design-A-claude.md §8 guard 2's full text) that
 * a later lane can build on top of this one's resolver.
 *
 * JSDOM LIMIT, read before trusting a green here. jsdom "applies no
 * stylesheet (no layout engine)" — the exact words `clients-desk.test.tsx`
 * uses for the same limit — so `getComputedStyle()` never resolves a
 * Tailwind utility class (arbitrary-value or not) to a real colour, and
 * never resolves a CSS custom property reference (`var(--x)`) to its
 * cascaded value even when an ancestor declares it. Two consequences follow,
 * both handled below rather than papered over:
 *
 *   1. Contrast math needs a real value, so `resolveColor` below resolves
 *      `var(--x[, fallback])` by hand, against a token table PARSED FROM
 *      `globals.css` itself (never hand-copied), for the
 *      `[data-theme="operative-light"][data-product="my"]` block this
 *      surface is mounted on today (`layout.tsx:54`). This is real WCAG
 *      relative-luminance math (`contrastRatio`), not a string comparison —
 *      pinned against design-A-claude.md's own M1 number below as a
 *      cross-check that the formula is right.
 *   2. A Tailwind class produces NO computed colour in jsdom at all (guilty
 *      or innocent), so `getComputedStyle` alone cannot see a regression
 *      back to `text-red-600` — it would just report the initial value.
 *      Each check below therefore ALSO reads the rendered element's actual
 *      `className` (the DOM the component produced, not the `.tsx` source
 *      text) and bans the red-family utility shape. Reverting the inline
 *      `style={{ color: "var(--tx-pure)" }}` fix back to
 *      `className="text-red-600"` trips THIS half of the guard, which is
 *      the one jsdom can actually see.
 */

const GLOBALS_CSS_PATH = join(__dirname, "..", "..", "globals.css");
const globalsCss = readFileSync(GLOBALS_CSS_PATH, "utf-8");

/** Brace-matched extraction — the block contains a nested `body { ... }` rule. */
function extractBlock(css: string, selector: string): string {
  const selectorStart = css.indexOf(selector);
  if (selectorStart === -1) {
    throw new Error(`selector not found in globals.css: ${selector}`);
  }
  const braceStart = css.indexOf("{", selectorStart);
  let depth = 0;
  let i = braceStart;
  for (; i < css.length; i++) {
    if (css[i] === "{") depth++;
    else if (css[i] === "}") {
      depth--;
      if (depth === 0) break;
    }
  }
  return css.slice(braceStart + 1, i);
}

function parseTokens(block: string): Record<string, string> {
  const tokens: Record<string, string> = {};
  const re = /(--[a-z0-9-]+)\s*:\s*([^;]+);/gi;
  let m: RegExpExecArray | null;
  while ((m = re.exec(block))) {
    tokens[m[1]] = m[2].trim();
  }
  return tokens;
}

/**
 * The theme block to resolve against is DERIVED from the layout that mounts
 * this surface, never named here.
 *
 * It used to be named here, and the comment that named it said "the surface's
 * actual wrapper today (layout.tsx:54) — not the operative-dark block S1 may
 * flip to later; this guard measures what is LIVE". S1 flipped it.
 * `layout.tsx` has declared `data-theme="operative-dark"` since the DELIBERA
 * fase 2 (a) change, and this file kept resolving every colour against
 * `operative-light` — so a required check computed real WCAG arithmetic on a
 * palette the funnel does not ship, and its green said nothing about the
 * surface. Cicatrix family #2: the check existed, it was armed, and it was
 * measuring a corpse.
 *
 * A constant cannot be kept in sync by intention; it can only be kept in sync
 * by being read from the thing it must match. `mountedSelector` parses the
 * wrapper's own attributes out of `layout.tsx`, so the next flip carries the
 * guard with it and a theme `globals.css` does not declare throws instead of
 * silently resolving to nothing.
 */
const LAYOUT_PATH = join(__dirname, "layout.tsx");
const layoutSrc = readFileSync(LAYOUT_PATH, "utf-8");

/**
 * Comments are stripped first, and the match is anchored on the ELEMENT's own
 * attribute pair rather than on the two attribute names appearing anywhere.
 *
 * Both halves are load-bearing and the first was found by running the guilt
 * mutation rather than by reading: `layout.tsx`'s docblock explains the
 * DELIBERA fase 2 (a) flip and contains the literal string
 * `[data-theme="operative-dark"]` sixteen lines ABOVE the wrapper. A bare
 * `/data-theme="(...)"/ ` therefore read the PROSE, returned the right answer
 * by coincidence, and kept returning it when the wrapper was flipped
 * underneath it — a derivation that cannot fail is not a derivation, it is
 * the hardcoded constant this change exists to remove, wearing a function.
 */
function mountedSelector(src: string): string {
  const code = src
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^[ \t]*\/\/.*$/gm, "");
  const el =
    /<[a-z][a-z0-9]*\s[^>]*?data-theme="([a-z0-9-]+)"[^>]*?data-product="([a-z0-9-]+)"/i.exec(
      code,
    );
  if (!el) {
    throw new Error(
      "layout.tsx declares no data-theme/data-product element — this guard " +
        "cannot know what ground to measure against",
    );
  }
  return `[data-theme="${el[1]}"][data-product="${el[2]}"]`;
}

const SURFACE_SELECTOR = mountedSelector(layoutSrc);
const SURFACE_TOKENS = parseTokens(extractBlock(globalsCss, SURFACE_SELECTOR));

function resolveColor(
  raw: string,
  tokens: Record<string, string>,
  depth = 0,
): string {
  const trimmed = raw.trim();
  const varMatch = trimmed.match(/^var\(\s*(--[a-z0-9-]+)\s*(?:,\s*(.+))?\)$/i);
  if (!varMatch) return trimmed;
  if (depth > 5) {
    throw new Error(`var() resolution too deep for ${raw}`);
  }
  const [, name, fallback] = varMatch;
  const resolved = tokens[name] ?? fallback;
  if (resolved === undefined) {
    throw new Error(`token ${name} not found and no fallback in ${raw}`);
  }
  return resolveColor(resolved, tokens, depth + 1);
}

/** `[r, g, b, alpha]`. Alpha is 1 unless the source says otherwise. */
type Rgba = [number, number, number, number];

function hexToRgb(hex: string): [number, number, number] {
  let h = hex.slice(1);
  if (h.length === 3) {
    h = h
      .split("")
      .map((c) => c + c)
      .join("");
  }
  const num = parseInt(h, 16);
  return [(num >> 16) & 255, (num >> 8) & 255, num & 255];
}

/**
 * Two shapes the operative-dark block uses that the light block never did,
 * and that the previous parser would have read as a different colour rather
 * than failing:
 *
 *  - `color-mix(in srgb, #253e33 40%, #f7f4ee)` — four of this block's state
 *    tokens are declared this way. The old `toRgb` threw on them, so flipping
 *    the selector alone would have turned the guard red on parse rather than
 *    on contrast; worse, a lenient parser would have read the first hex it
 *    found and reported the UNMIXED colour, which is a darker green than the
 *    surface renders.
 *  - `rgba(247, 244, 238, 0.12)` — `--bz-border` and both muted text tokens
 *    carry alpha here. The old parser dropped the alpha channel silently and
 *    would have judged a 12%-opacity hairline as near-white paper. Alpha is
 *    composited over the ground instead, which is what the browser does and
 *    what the eye sees.
 */
function toRgba(color: string): Rgba {
  const trimmed = color.trim();

  const mix = trimmed.match(
    /^color-mix\(\s*in\s+srgb\s*,\s*(#[0-9a-f]{3,8})\s+([\d.]+)%\s*,\s*(#[0-9a-f]{3,8})\s*\)$/i,
  );
  if (mix) {
    const [ar, ag, ab] = hexToRgb(mix[1]);
    const [br, bg, bb] = hexToRgb(mix[3]);
    const w = Number(mix[2]) / 100;
    return [
      ar * w + br * (1 - w),
      ag * w + bg * (1 - w),
      ab * w + bb * (1 - w),
      1,
    ];
  }

  if (/^#([0-9a-f]{6}|[0-9a-f]{3})$/i.test(trimmed)) {
    const [r, g, b] = hexToRgb(trimmed);
    return [r, g, b, 1];
  }

  const rgb = trimmed.match(
    /rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:[,\s/]+([\d.]+))?/i,
  );
  if (rgb) {
    return [
      Number(rgb[1]),
      Number(rgb[2]),
      Number(rgb[3]),
      rgb[4] === undefined ? 1 : Number(rgb[4]),
    ];
  }
  throw new Error(`cannot parse colour: ${color}`);
}

/** Source-over composite of a possibly-translucent colour onto an opaque one. */
function over(
  fg: Rgba,
  ground: [number, number, number],
): [number, number, number] {
  const a = fg[3];
  return [
    fg[0] * a + ground[0] * (1 - a),
    fg[1] * a + ground[1] * (1 - a),
    fg[2] * a + ground[2] * (1 - a),
  ];
}

function toRgb(color: string): [number, number, number] {
  const c = toRgba(color);
  return [c[0], c[1], c[2]];
}

function relativeLuminance([r, g, b]: [number, number, number]): number {
  const lin = (c: number) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

/** WCAG 2.1 contrast ratio, §1.4.3's own formula — verified below (M1 cross-check). */
function contrastRatio(fg: string, bg: string): number {
  // The background is flattened first and then serves as the ground the
  // foreground's own alpha composites onto — the order the browser paints in.
  // Without this a translucent token is judged against the colour it would
  // have if it were opaque, which is not a colour anyone sees.
  const bgRgb = over(toRgba(bg), [255, 255, 255]);
  const l1 = relativeLuminance(over(toRgba(fg), bgRgb));
  const l2 = relativeLuminance(bgRgb);
  const [lighter, darker] = l1 > l2 ? [l1, l2] : [l2, l1];
  return (lighter + 0.05) / (darker + 0.05);
}

const RED_CLASS_RE =
  /\b(?:bg|text|border|ring|divide|fill|stroke|from|to|via)-(?:red|rose|pink|orange|crimson)-\d/;

/** The two checks a jsdom-honest guard can make: real WCAG math on whatever
 * colour is actually reachable, and a DOM-output ban on the one shape jsdom
 * cannot compute (see file header, consequence 2). */
function assertErrorTone(el: Element, tokens: Record<string, string>) {
  const style = (el as HTMLElement).style;
  expect(
    style.color,
    `${el.tagName} has no inline colour to judge — the guard only judges elements it can compute`,
  ).not.toBe("");
  const fg = resolveColor(style.color, tokens);
  expect(fg, "error text must use the ink tone, not copper or red").toBe(
    tokens["--tx-pure"],
  );
  const bg = tokens["--bz-base"];
  expect(contrastRatio(fg, bg)).toBeGreaterThanOrEqual(4.5);
  expect(el.className, `${el.tagName} className`).not.toMatch(RED_CLASS_RE);
}

describe("resolver + contrast math — guilt and innocence (cicatrix #3)", () => {
  /**
   * The regression pin for the drift this file was curing. It asserts the
   * derived selector AGAINST `layout.tsx`'s own declaration rather than
   * against a second literal — a hardcoded expectation here would reintroduce
   * exactly the two-constants-drifting-apart shape that put the guard on the
   * wrong palette in the first place.
   */
  it("resolves against the theme layout.tsx actually mounts", () => {
    expect(layoutSrc).toContain(`data-theme="operative-dark"`);
    expect(SURFACE_SELECTOR).toBe(
      '[data-theme="operative-dark"][data-product="my"]',
    );
  });

  it("GUILTY: the derivation reads the source, it does not return a constant", () => {
    expect(
      mountedSelector('<div data-theme="operative-light" data-product="my">'),
    ).toBe('[data-theme="operative-light"][data-product="my"]');
    expect(() => mountedSelector("<div>no wrapper here</div>")).toThrow(
      /no data-theme/,
    );
  });

  /**
   * The exact shape that made the first version of this cure pass its own
   * guilt mutation: `layout.tsx` names one theme in its docblock and mounts
   * another. The element wins, and a `toThrow` here would not be enough —
   * the wrong ANSWER is the defect, not the absence of one.
   */
  it("GUILTY: prose that names a theme never outranks the element that mounts one", () => {
    const misleading = [
      '/* re-keyed to [data-theme="operative-dark"] in the same PR */',
      '// see the [data-theme="operative-dark"] block',
      'return <div data-theme="operative-light" data-product="my">{x}</div>;',
    ].join("\n");
    expect(mountedSelector(misleading)).toBe(
      '[data-theme="operative-light"][data-product="my"]',
    );
  });

  it("GUILTY: a theme globals.css does not declare throws, it never resolves to nothing", () => {
    expect(() =>
      extractBlock(
        globalsCss,
        '[data-theme="no-such-theme"][data-product="my"]',
      ),
    ).toThrow(/selector not found/);
  });

  it("parses real hex tokens out of globals.css, not a hand-copied guess", () => {
    expect(SURFACE_TOKENS["--tx-pure"]).toBe("#f7f4ee");
    expect(SURFACE_TOKENS["--bz-base"]).toBe("#121016");
    expect(SURFACE_TOKENS["--bz-border"]).toBe("rgba(247, 244, 238, 0.12)");
  });

  /**
   * The two shapes the light block never contained. Both are checked as
   * VALUES, not as "parses without throwing": a lenient parser that returned
   * the first hex of a `color-mix` or dropped an alpha channel would also not
   * throw, and would report a colour the surface does not render.
   */
  it("mixes a color-mix token instead of reading one side of it", () => {
    // 40% #253e33 + 60% #f7f4ee — the unmixed first hex would be (37, 62, 51).
    expect(toRgb(SURFACE_TOKENS["--state-info"])).toEqual([
      0.4 * 0x23 + 0.6 * 0xf7,
      0.4 * 0x3d + 0.6 * 0xf4,
      0.4 * 0x52 + 0.6 * 0xee,
    ]);
    expect(toRgb(SURFACE_TOKENS["--state-success"])[0]).not.toBe(0x25);
  });

  it("composites alpha over the ground instead of dropping it", () => {
    // --bz-border is paper at 12% on near-black. Dropping the alpha would
    // read it as paper itself and call a hairline a 17:1 surface.
    const asPainted = contrastRatio(
      SURFACE_TOKENS["--bz-border"],
      SURFACE_TOKENS["--bz-base"],
    );
    expect(asPainted).toBeLessThan(1.6);
    expect(
      contrastRatio("#f7f4ee", SURFACE_TOKENS["--bz-base"]),
    ).toBeGreaterThan(15);
  });

  it("INNOCENT: the cured tone (paper on ink) clears 4.5:1", () => {
    const fg = resolveColor("var(--tx-pure)", SURFACE_TOKENS);
    const bg = SURFACE_TOKENS["--bz-base"];
    expect(contrastRatio(fg, bg)).toBeGreaterThanOrEqual(4.5);
  });

  /**
   * A FORMULA cross-check, deliberately on paper literals rather than on
   * `--bz-base`: M1's 4.40:1 was measured on the paper ground this surface
   * used to have, and the point of the row is that `contrastRatio` reproduces
   * a number someone else computed independently. Pointing it at whatever the
   * current theme's ground happens to be would turn a formula proof into a
   * theme fact and lose the cross-check.
   */
  it("GUILTY: the ORIGINAL text-red-600 hex (#DC2626) on paper measures 4.40:1 — an AA fail, matching design-A-claude.md M1's own number", () => {
    const ratio = contrastRatio("#DC2626", "#f7f4ee");
    expect(ratio).toBeCloseTo(4.4, 1);
    expect(ratio).toBeLessThan(4.5);
  });

  it("GUILTY: copper (--color-error's resolved value on this surface) is a real colour but the wrong ONE — the guard demands ink specifically, not merely 'passes contrast'", () => {
    const copper = SURFACE_TOKENS["--state-danger"];
    expect(copper).toBe("#c46a52");
    // Copper-on-paper actually clears AA (it is the sanctioned "needs you"
    // tone) — proving a bare contrast check would NOT catch M2's finding
    // that role="alert" read the wrong meaning, only the identity check does.
    expect(
      contrastRatio(copper, SURFACE_TOKENS["--bz-base"]),
    ).toBeGreaterThanOrEqual(4.5);
  });

  it("GUILTY, the DOM-output shape a computed check cannot see any other way: a red Tailwind class in the rendered className", () => {
    const { container } = render(
      <p className="text-sm text-red-600">rendered, not sourced</p>,
    );
    const p = container.querySelector("p")!;
    expect(p.className).toMatch(RED_CLASS_RE);
    // And, matching consequence 2 in the file header: jsdom gives this
    // element NO inline colour at all, so a naive computed-only check would
    // stay silent on it — which is exactly why assertErrorTone also checks
    // className, not color alone.
    expect(p.style.color).toBe("");
  });

  it("INNOCENT: the kita idiom (border/text tokens, not a fill) never trips the red-class ban", () => {
    const { container } = render(
      <p className="text-sm" style={{ color: "var(--tx-pure)" }}>
        fine
      </p>,
    );
    expect(container.querySelector("p")!.className).not.toMatch(RED_CLASS_RE);
  });
});

// ---------------------------------------------------------------------------
// Safe Clock state identities. Lives here rather than in a new file because
// this is the file that already owns the token resolver, the color-mix and
// alpha compositing, and the WCAG arithmetic — a second copy of that maths is
// the drift `voa-copy.guard.test.ts` refuses for its comment stripper, for the
// same reason.
// ---------------------------------------------------------------------------

const VOA_R19_CSS = readFileSync(join(__dirname, "voa-r19.css"), "utf-8");

interface StateRule {
  colour: string;
  widthPx: number;
}

/** Reads the four `.voa-clock--X` rules out of the stylesheet, not a table. */
function stateRule(state: string): StateRule {
  const re = new RegExp(`\\.voa-clock--${state}\\s*\\{([^}]*)\\}`, "i");
  const m = re.exec(VOA_R19_CSS);
  if (!m) throw new Error(`no rule for .voa-clock--${state}`);
  const colour = /border-left-color:\s*([^;]+);/i.exec(m[1]);
  const width = /border-left-width:\s*(\d+)px;/i.exec(m[1]);
  if (!colour || !width) {
    throw new Error(`.voa-clock--${state} must declare colour AND width`);
  }
  return {
    colour: resolveColor(colour[1].trim(), SURFACE_TOKENS),
    widthPx: Number(width[1]),
  };
}

const CLOCK_STATES = ["ample", "soon", "today", "passed"] as const;

describe("Safe Clock — four states, four identities (mandate accent 4)", () => {
  const rules = Object.fromEntries(
    CLOCK_STATES.map((s) => [s, stateRule(s)]),
  ) as Record<(typeof CLOCK_STATES)[number], StateRule>;

  /**
   * The shipped `passed` rule was `--bz-border-hover` at 1.78:1 — an absence
   * presented as the fourth colour. 1.4.11's floor for a non-text indicator
   * is 3:1.
   */
  it.each(CLOCK_STATES)("%s: the rule clears the 3:1 non-text floor", (st) => {
    expect(
      contrastRatio(rules[st].colour, SURFACE_TOKENS["--bz-base"]),
    ).toBeGreaterThanOrEqual(3);
  });

  it("GUILTY: the retired --bz-border-hover would fail that floor", () => {
    expect(
      contrastRatio(
        resolveColor("var(--bz-border-hover)", SURFACE_TOKENS),
        SURFACE_TOKENS["--bz-base"],
      ),
    ).toBeLessThan(2);
  });

  /**
   * The claim this pins is NOT "four different tokens" — the version that
   * shipped had four different tokens and two of them were 1.11:1 apart. Each
   * PAIR must be separable on a real axis: either the rule colours are far
   * enough apart to read as different, or their widths differ.
   */
  it.each(
    CLOCK_STATES.flatMap((a, i) =>
      CLOCK_STATES.slice(i + 1).map((b) => [a, b] as const),
    ),
  )("%s vs %s is separable by colour or by width", (a, b) => {
    const byColour = contrastRatio(rules[a].colour, rules[b].colour);
    const byWidth = rules[a].widthPx !== rules[b].widthPx;
    expect(
      byColour >= 1.5 || byWidth,
      `${a}/${b}: ${byColour.toFixed(2)}:1 apart and both ${rules[a].widthPx}px`,
    ).toBe(true);
  });

  /**
   * Named explicitly rather than left implicit in the loop above: these two
   * are the pair that colour cannot separate, and the design leans on width
   * and on the word for them. If someone equalises the widths "for
   * consistency", this is the row that says why they cannot.
   */
  it("ample vs soon is the pair colour cannot separate — width carries it", () => {
    expect(contrastRatio(rules.ample.colour, rules.soon.colour)).toBeLessThan(
      1.5,
    );
    expect(rules.ample.widthPx).not.toBe(rules.soon.widthPx);
  });
});

// ---------------------------------------------------------------------------
// Tracker exception tones. Same discipline as the Safe Clock table above, on
// the other surface where a customer reads a state: five situations that all
// rendered behind one `1px solid var(--color-border-subtle)` until this table
// existed.
// ---------------------------------------------------------------------------

describe("order tracker — four exception tones, four identities", () => {
  const tones = Object.entries(EXCEPTION_RULE) as [string, string][];

  it("has a tone for every branch the tracker can render", () => {
    expect(tones.map(([k]) => k).sort()).toEqual([
      "closed",
      "needs-you",
      "refused",
      "retry",
    ]);
  });

  it.each(tones)("%s: the rule clears the 3:1 non-text floor", (_k, token) => {
    expect(
      contrastRatio(
        resolveColor(token, SURFACE_TOKENS),
        SURFACE_TOKENS["--bz-base"],
      ),
    ).toBeGreaterThanOrEqual(3);
  });

  /**
   * Distinctness measured on the RESOLVED colours, not on the token spellings.
   * Four different `var()` names that resolve to one value is the trap
   * `--state-danger` / `--bz-copper-text` sets on this theme, and a name-level
   * check walks straight into it.
   */
  it.each(
    tones.flatMap(([ka, a], i) =>
      tones.slice(i + 1).map(([kb, b]) => [ka, kb, a, b] as const),
    ),
  )("%s and %s do not resolve to the same colour", (_ka, _kb, a, b) => {
    expect(resolveColor(a, SURFACE_TOKENS)).not.toBe(
      resolveColor(b, SURFACE_TOKENS),
    );
  });

  it("GUILTY: --state-danger would collide with the needs-you copper", () => {
    expect(resolveColor("var(--state-danger)", SURFACE_TOKENS)).toBe(
      resolveColor(EXCEPTION_RULE["needs-you"], SURFACE_TOKENS),
    );
  });
});

// ---------------------------------------------------------------------------
// The seven real sites, rendered through the actual production components.
// ---------------------------------------------------------------------------

const trackerMocks = vi.hoisted(() => ({
  viewed: vi.fn(),
  wizardStep: vi.fn(),
  wizardAbandoned: vi.fn(),
  formSubmitted: vi.fn(),
  formSubmitFailed: vi.fn(),
  resultViewed: vi.fn(),
  ctaClicked: vi.fn(),
  whatsappHandoff: vi.fn(),
  shareClicked: vi.fn(),
  emailSubscribed: vi.fn(),
}));

vi.mock("@balizero/core", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@balizero/core")>();
  return {
    ...actual,
    useFunnelApp: () => trackerMocks,
  };
});

function jsonResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

const fetchMock = global.fetch as unknown as ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock.mockReset();
  window.localStorage.clear();
  window.sessionStorage.clear();
  vi.clearAllMocks();
});

describe("upload — three error-tone states (M1's own site)", () => {
  it("client_rejected: oversized file, rejected client-side, no fetch", async () => {
    // A wrong-MIME file (e.g. a PDF) never reaches `selectFile` here:
    // `userEvent.upload` enforces the input's own `accept` attribute the way
    // a real browser's file picker does, so a mismatched type is silently
    // not selected. An oversized JPEG has the RIGHT type and clears that
    // gate, then trips `precheckFile`'s size check — the same
    // `client_rejected` branch, reached the way a real user reaches it.
    render(<UploadFlow resultId="guard-upload-1" />);
    const input = screen.getByLabelText("Upload passport photo");
    const bigFile = new File(
      [new Uint8Array(16 * 1024 * 1024)],
      "passport.jpg",
      { type: "image/jpeg" },
    );
    await userEvent.upload(input, bigFile);

    const alert = await screen.findByRole("alert");
    const p = alert.querySelector("p")!;
    assertErrorTone(p, SURFACE_TOKENS);
  });

  it("unreadable: server returns UNREADABLE_DOCUMENT", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(422, {
        code: "UNREADABLE_DOCUMENT",
        retryable: false,
        message_key: "garuda_voa.error.unreadable_document",
      }),
    );
    render(<UploadFlow resultId="guard-upload-2" />);
    const input = screen.getByLabelText("Upload passport photo");
    const goodFile = new File([new Uint8Array(10)], "passport.jpg", {
      type: "image/jpeg",
    });
    await userEvent.upload(input, goodFile);

    const p = await screen.findByText(COPY_UNREADABLE_INSTRUCTION);
    assertErrorTone(p, SURFACE_TOKENS);
  });

  it("error: a retryable 503 (document store unavailable)", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(503, {
        code: "DOCUMENT_PROCESSING_UNAVAILABLE",
        retryable: true,
        message_key: "garuda_voa.error.document_processing_unavailable",
      }),
    );
    render(<UploadFlow resultId="guard-upload-3" />);
    const input = screen.getByLabelText("Upload passport photo");
    const goodFile = new File([new Uint8Array(10)], "passport.jpg", {
      type: "image/jpeg",
    });
    await userEvent.upload(input, goodFile);

    const p = await screen.findByText(
      messageFor("DOCUMENT_PROCESSING_UNAVAILABLE"),
    );
    assertErrorTone(p, SURFACE_TOKENS);
  });
});

describe("wizard — eligibility-check submit failure (page.tsx:541)", () => {
  it("network failure renders the WhatsApp-fallback alert in ink, not copper", async () => {
    fetchMock.mockRejectedValue(new Error("network down"));
    render(<VoaEligibilityPage />);

    fireEvent.click(
      screen.getByRole("button", { name: /Get a new Visa on Arrival/ }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Tourism" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.change(screen.getByLabelText("Nationality"), {
      target: { value: "ITA" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.change(screen.getByLabelText("Entry date"), {
      target: { value: "2026-09-01" },
    });
    fireEvent.change(screen.getByLabelText("Passport expiry date"), {
      target: { value: "2027-09-01" },
    });
    fireEvent.click(
      screen.getByLabelText("Storage and deletion notice acknowledgement"),
    );
    fireEvent.click(screen.getByRole("button", { name: "See result" }));

    const alert = await waitFor(() => screen.getByRole("alert"));
    assertErrorTone(alert, SURFACE_TOKENS);
  });
});

describe("verdict — magic-link resend failure ([hash]/page.tsx:404)", () => {
  it("a failed resend renders the alert in ink, not copper", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        verdict: "ACCEPT",
        reason_codes: [],
        price_idr: 790000,
      }),
    });
    fetchMock.mockResolvedValueOnce({ status: 500 });
    render(<VoaResultPage params={Promise.resolve({ hash: "guard-hash" })} />);
    await waitFor(() =>
      expect(screen.getByTestId("bz-stamp")).toBeInTheDocument(),
    );

    const user = userEvent.setup();
    await user.type(
      screen.getByLabelText(/continue by email/i),
      "customer@example.com",
    );
    await user.click(screen.getByRole("button", { name: /email me a link/i }));

    const alert = await screen.findByRole("alert");
    assertErrorTone(alert, SURFACE_TOKENS);
  });
});

describe("checkout — order-creation failure (CheckoutFlow.tsx:201)", () => {
  it("a failed order submit renders the alert in ink, not copper", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(500, {}));
    const user = userEvent.setup();
    render(<CheckoutFlow resultId="guard-checkout-1" paymentsLive={true} />);

    await user.type(
      screen.getByLabelText(/full name \(as in passport\)/i),
      "Jane Doe",
    );
    await user.type(screen.getByLabelText(/^passport number$/i), "X1234567");
    await user.type(screen.getByLabelText(/email/i), "customer@example.com");
    await user.type(screen.getByLabelText(/phone/i), "+6281234567890");
    await user.click(
      screen.getByRole("button", { name: /continue to payment/i }),
    );

    const alert = await screen.findByRole("alert");
    assertErrorTone(alert, SURFACE_TOKENS);
  });
});

describe("tracker — order load failure (OrderTracker.tsx:49)", () => {
  it("a failed order fetch renders the alert in ink, not copper", async () => {
    fetchMock.mockResolvedValue(jsonResponse(500, {}));
    render(<OrderTracker orderId="guard-order-1" />);

    const alert = await screen.findByRole("alert");
    assertErrorTone(alert, SURFACE_TOKENS);
  });
});
