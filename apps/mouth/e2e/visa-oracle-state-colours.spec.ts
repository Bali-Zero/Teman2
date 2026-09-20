import { expect, test, type Page } from "@playwright/test";
import {
  createInterviewSnapshot,
  flowReducer,
  initialFlowState,
  QUESTIONS,
  type FlowState,
} from "../src/app/(visa-oracle)/visa-oracle/_lib/flow";
import type { OracleQuestion } from "../src/app/(visa-oracle)/visa-oracle/_lib/tree";
import { makeVisaOracleResponse } from "../src/app/(visa-oracle)/visa-oracle/_lib/visa-oracle-test-fixture";

/**
 * W-C1e — the four Visa Oracle outcome-state colours, computed BY THE
 * BROWSER instead of modelled by a text parser.
 *
 * The parser-based fence (`oracle-state-tokens.test.ts`, #6820 — STAYS,
 * untouched by this file) was suspended after three gate reds (#6833,
 * #6845, #6855): ~800 lines of hand-rolled CSS selector/specificity model,
 * always one construct behind the language it read as text. This spec
 * instead appends the product's OWN chip markup
 * (`.oracle-verdict-chip[data-state]`, VerdictReveal.tsx:139-140) into a
 * live, unmodified `.oracle-root` and lets a real Chromium resolve the
 * cascade via `getComputedStyle`. Design: kit/DRAFT-SPEC-C1b-1.v2.md §2-3;
 * clauses V1-V13, MANDATE-vo.md "Slice C1e".
 *
 * Reading `--oracle-state-*` off `.oracle-root`/`:root` directly is
 * FORBIDDEN: `getPropertyValue` returns the raw authored text
 * ("#16683f"), never the canonical `rgb(22, 104, 63)` a real chip's
 * computed style resolves to (measured, DRAFT-SPEC-C1b-1.v2.md F18.2) —
 * reading it would silently reintroduce the notation-family bugs
 * (#6820 M4/M5) this instrument exists to remove.
 *
 * forced-colors and print are a DOCUMENTED EXCLUSION, not a seventh/eighth
 * row: there the user agent picks the colours (measured: all four
 * foregrounds collapse to `rgb(0, 0, 0)`), so pinning "they collapse"
 * would assert a browser's behaviour, not the product's. Distinguishing
 * the four states WITHOUT colour under those two contexts is slice C3
 * (semantic labels), not this fence.
 */

const STATES = ["eligible", "likely", "conditional", "likely-not"] as const;
type StateName = (typeof STATES)[number];
type Swatch = { color: string; backgroundColor: string };
type Palette = Record<StateName, Swatch>;

/** V1 — inject the product's own chip class into the live `.oracle-root`
 * (real stylesheet, real cascade, real theme/media state); read only the
 * RENDERED computed style, never a custom property. */
async function readChipPalette(page: Page): Promise<Palette> {
  return page.evaluate((states) => {
    const root = document.querySelector<HTMLElement>(".oracle-root");
    if (!root) throw new Error("state-fence: no .oracle-root in the page");
    const out: Record<string, { color: string; backgroundColor: string }> = {};
    for (const state of states) {
      const chip = document.createElement("span");
      chip.className = "oracle-verdict-chip";
      chip.dataset.state = state;
      chip.dataset.stateFenceProbe = "true";
      root.appendChild(chip);
      const computed = getComputedStyle(chip);
      out[state] = {
        color: computed.color,
        backgroundColor: computed.backgroundColor,
      };
      chip.remove();
    }
    return out;
  }, STATES) as Promise<Palette>;
}

/** V7 — the floor: loud red, never a silent pass, when the chip census or
 * the alpha channel says a "distinct" background is actually invisible.
 * `transparent` computes to `rgba(0, 0, 0, 0)` and `rgba(255,255,255,0)`
 * to a DIFFERENT string (measured, F18.5) — string inequality alone would
 * wave an invisible background through as "distinct". */
function assertFloor(
  palette: Partial<Record<StateName, Swatch>>,
  label: string,
): void {
  const present = STATES.filter((s) => palette[s] !== undefined);
  if (present.length !== STATES.length) {
    throw new Error(
      `${label}: floor — expected ${STATES.length} chip states, found ${present.length} (${present.join(",")})`,
    );
  }
  for (const state of STATES) {
    const bg = palette[state]!.backgroundColor;
    const alpha = bg.match(/rgba?\([^)]*,\s*([\d.]+)\)/)?.[1] ?? "1";
    if (Number(alpha) === 0) {
      throw new Error(
        `${label}: floor — "${state}"'s background is alpha 0 ("${bg}"), not a distinct colour`,
      );
    }
  }
}

/** V3 — distinctness is EXACT inequality, pairwise, both axes. No
 * perceptual threshold: #6820 pins declared-literal distinctness and it
 * stays in force (R-SUSPEND-C1b). */
function assertDistinct(palette: Palette, label: string): void {
  for (let i = 0; i < STATES.length; i++) {
    for (let j = i + 1; j < STATES.length; j++) {
      const a = STATES[i];
      const b = STATES[j];
      if (palette[a].color === palette[b].color) {
        throw new Error(
          `${label}: "${a}" and "${b}" share the same fg colour "${palette[a].color}"`,
        );
      }
      if (palette[a].backgroundColor === palette[b].backgroundColor) {
        throw new Error(
          `${label}: "${a}" and "${b}" share the same bg colour "${palette[a].backgroundColor}"`,
        );
      }
    }
  }
}

/** For the PREDICTED cases (V13): measure whether a guard fired, without
 * letting the guard's own thrown Error fail the test — the case is
 * reported either way, never reshaped until it actually goes red. */
function threw(fn: () => void): boolean {
  try {
    fn();
    return false;
  } catch {
    return true;
  }
}

async function waitHydrated(page: Page): Promise<void> {
  await page.waitForSelector(".oracle-root[data-oracle-theme-ready]");
}

/** Set a context row's two axes without a reload: `emulateMedia`
 * re-evaluates every `@media` block live, and writing the theme attribute
 * directly is exactly what `ThemeToggle.tsx:45` itself does outside
 * React's diff, for the same reason (no flash, no spurious re-render). */
async function setRowContext(
  page: Page,
  media: {
    colorScheme?: "light" | "dark";
    contrast?: "no-preference" | "more";
  },
  theme: "light" | "dark",
): Promise<void> {
  await page.emulateMedia({
    colorScheme: "light",
    contrast: "no-preference",
    ...media,
  });
  await page.evaluate((t) => {
    document
      .querySelector(".oracle-root")
      ?.setAttribute("data-oracle-theme", t);
  }, theme);
}

/** Rows 4/5 (pre-hydration): block the hydration bundle so `ThemeToggle`
 * never mounts and `-ready` never appears; css untouched (§2.4). */
async function blockHydrationBundle(page: Page): Promise<void> {
  await page.route("**/_next/static/chunks/**", (route) => route.abort());
}

// ─── V9's weld: reach the verdict surface exactly as
// e2e/visa-oracle-process.spec.ts:25,102 does — COPIED, never imported
// (Playwright re-registers an imported spec file's tests) — trimmed to
// only what is needed to render one verdict. ───────────────────────────
const RESUME_KEY = "visa-oracle:v2:resume:v1";
const OFFSHORE: Record<string, string> = {
  in_indonesia: "no",
  holds_stay_permit: "no",
};

function answerValue(question: OracleQuestion): string {
  if (question.id === "birth_date") return "1985-04-12";
  if (question.kind === "date") return "2026-12-01";
  if (question.kind === "number") {
    if (question.id === "overstay_days") return "0";
    return String(question.numberInput?.min ?? 0);
  }
  if (question.kind === "country-codes") return "IT";
  if (question.kind === "review-gate") return "none";
  return question.options[0]?.key ?? "unsure";
}

function walkToVerdict(): FlowState {
  let state = flowReducer(initialFlowState("en"), { type: "ADVANCE" });
  while (Object.keys(state.facts).length < 60) {
    const node = state.history[state.history.length - 1];
    if (node.kind !== "question") break;
    const before = Object.keys(state.facts).length;
    state = flowReducer(state, {
      type: "ANSWER",
      questionId: node.questionId,
      value:
        OFFSHORE[node.questionId] ?? answerValue(QUESTIONS[node.questionId]),
    });
    if (Object.keys(state.facts).length === before) {
      throw new Error(
        `state-fence weld: the reducer refused an answer to ${node.questionId}`,
      );
    }
  }
  const last = state.history[state.history.length - 1];
  return last.kind === "confirmation"
    ? flowReducer(state, { type: "ADVANCE" })
    : state;
}

async function seedVerdict(page: Page): Promise<void> {
  const state = walkToVerdict();
  const savedAt = new Date();
  const snapshot = createInterviewSnapshot(
    { attempt: state.attempt, history: state.history, facts: state.facts },
    savedAt,
  );
  await page.addInitScript(
    ({ key, payload }) => window.sessionStorage.setItem(key, payload),
    {
      key: RESUME_KEY,
      payload: JSON.stringify({
        schemaVersion: 1,
        savedAtIso: savedAt.toISOString(),
        expiresAtIso: new Date(
          savedAt.getTime() + 2 * 60 * 60 * 1_000,
        ).toISOString(),
        snapshot,
      }),
    },
  );
}

test.describe("Visa Oracle v2 state colours — browser-computed fence — page Page", () => {
  test.describe.configure({ mode: "serial" });

  let PALETTE_LIGHT: Palette;
  let PALETTE_DARK: Palette;

  test("row 1 — light, hydrated (defines PALETTE_LIGHT)", async ({ page }) => {
    await page.goto("/visa-oracle");
    await waitHydrated(page);
    await expect(page.locator(".oracle-root")).toHaveAttribute(
      "data-oracle-theme",
      "light",
    );
    PALETTE_LIGHT = await readChipPalette(page);
    assertFloor(PALETTE_LIGHT, "row1");
    assertDistinct(PALETTE_LIGHT, "row1");
    // V1 guilt: the probe's output is rgb(...)-shaped, never #...-shaped.
    for (const state of STATES) {
      expect(PALETTE_LIGHT[state].color, `row1 ${state} fg`).toMatch(/^rgb\(/);
      expect(PALETTE_LIGHT[state].backgroundColor, `row1 ${state} bg`).toMatch(
        /^rgba?\(/,
      );
    }
  });

  test("row 2 — dark, hydrated (defines PALETTE_DARK)", async ({ page }) => {
    await page.addInitScript(() =>
      window.localStorage.setItem("visa-oracle-theme", "dark"),
    );
    await page.goto("/visa-oracle");
    await waitHydrated(page);
    await expect(page.locator(".oracle-root")).toHaveAttribute(
      "data-oracle-theme",
      "dark",
    );
    PALETTE_DARK = await readChipPalette(page);
    assertFloor(PALETTE_DARK, "row2");
    assertDistinct(PALETTE_DARK, "row2");
  });

  test("row 3 — dark, system-dark", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/visa-oracle");
    await waitHydrated(page);
    await expect(page.locator(".oracle-root")).toHaveAttribute(
      "data-oracle-theme",
      "dark",
    );
    expect(
      await page.evaluate(
        () => matchMedia("(prefers-color-scheme: dark)").matches,
      ),
    ).toBe(true);
    const palette = await readChipPalette(page);
    assertFloor(palette, "row3");
    expect(palette).toEqual(PALETTE_DARK);
  });

  test("row 4 — pre-hydration, bootstrap dark", async ({ page }) => {
    await blockHydrationBundle(page);
    await page.addInitScript(() =>
      window.localStorage.setItem("visa-oracle-theme", "dark"),
    );
    await page.goto("/visa-oracle", { waitUntil: "domcontentloaded" });
    await expect(page.locator("html")).toHaveAttribute(
      "data-oracle-theme-bootstrap",
      "dark",
    );
    const root = page.locator(".oracle-root");
    await expect(root).toHaveAttribute("data-oracle-theme", "light");
    expect(await root.getAttribute("data-oracle-theme-ready")).toBeNull();
    const palette = await readChipPalette(page);
    assertFloor(palette, "row4");
    expect(palette).toEqual(PALETTE_DARK);
  });

  test("row 5 — pre-hydration, no bootstrap, system dark", async ({ page }) => {
    await blockHydrationBundle(page);
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/visa-oracle", { waitUntil: "domcontentloaded" });
    // Declared substitution (§2.4): a JS-capable page cannot itself omit
    // the inline bootstrap script's attribute write, so this ONE
    // `page.evaluate` reproduces the no-JS/CSP *cascade state* the
    // product ships for it — not a script-less browser.
    await page.evaluate(() =>
      document.documentElement.removeAttribute("data-oracle-theme-bootstrap"),
    );
    expect(
      await page.evaluate(() =>
        document.documentElement.hasAttribute("data-oracle-theme-bootstrap"),
      ),
    ).toBe(false);
    const root = page.locator(".oracle-root");
    await expect(root).toHaveAttribute("data-oracle-theme", "light");
    expect(await root.getAttribute("data-oracle-theme-ready")).toBeNull();
    expect(
      await page.evaluate(
        () => matchMedia("(prefers-color-scheme: dark)").matches,
      ),
    ).toBe(true);
    const palette = await readChipPalette(page);
    assertFloor(palette, "row5");
    expect(palette).toEqual(PALETTE_DARK);
  });

  test("row 6 — prefers-contrast: more, light (defensive)", async ({
    page,
  }) => {
    await page.emulateMedia({ colorScheme: "light", contrast: "more" });
    await page.goto("/visa-oracle");
    await waitHydrated(page);
    expect(
      await page.evaluate(() => matchMedia("(prefers-contrast: more)").matches),
    ).toBe(true);
    const palette = await readChipPalette(page);
    assertFloor(palette, "row6");
    expect(palette).toEqual(PALETTE_LIGHT);
  });

  test.describe("guilt — hostile CSS injected via addStyleTag (no file mutation, no restore)", () => {
    /** RED at `red` (light-family rows), GREEN — and equal to `PALETTE_DARK`
     * — at row 2 (hydrated dark), for mutations confined to a light-theme
     * selector. One `goto`; `emulateMedia`/the theme attribute switch the
     * context live, no reload. */
    async function lightLeakCase(
      page: Page,
      css: string,
      redRows: Array<"row1" | "row6">,
    ): Promise<void> {
      await page.goto("/visa-oracle");
      await waitHydrated(page);
      await page.addStyleTag({ content: css });
      for (const row of redRows) {
        await setRowContext(
          page,
          row === "row6" ? { contrast: "more" } : {},
          "light",
        );
        const palette = await readChipPalette(page);
        expect(() => assertDistinct(palette, `S:${row}`)).toThrow();
      }
      // Dark sanity: GREEN means "still distinct" (§3), not "byte-identical
      // to baseline" — S1's two-branch selector list also touches the dark
      // attribute value, legitimately changing `likely` there too, but
      // without colliding with any dark sibling (measured).
      await setRowContext(page, {}, "dark");
      const dark = await readChipPalette(page);
      expect(
        threw(() => assertDistinct(dark, "S dark-sanity")),
        "dark row stays distinct",
      ).toBe(false);
    }

    /** Rows 2, 3 (same page, context switch) and rows 4, 5 (fresh
     * pre-hydration navigations) must all stay exactly `PALETTE_DARK` —
     * the dark-family half of S3's/S6's "green in every other row" claim
     * (V2, V8). */
    async function assertDarkFamilyUnaffected(
      page: Page,
      css: string,
    ): Promise<void> {
      await setRowContext(page, {}, "dark");
      expect(await readChipPalette(page)).toEqual(PALETTE_DARK);
      await setRowContext(page, { colorScheme: "dark" }, "dark");
      expect(await readChipPalette(page)).toEqual(PALETTE_DARK);
      await blockHydrationBundle(page);
      await page.addInitScript(() =>
        window.localStorage.setItem("visa-oracle-theme", "dark"),
      );
      await page.goto("/visa-oracle", { waitUntil: "domcontentloaded" });
      await page.addStyleTag({ content: css });
      expect(await readChipPalette(page)).toEqual(PALETTE_DARK);
      await blockHydrationBundle(page);
      await page.emulateMedia({ colorScheme: "dark" });
      await page.goto("/visa-oracle", { waitUntil: "domcontentloaded" });
      await page.evaluate(() =>
        document.documentElement.removeAttribute("data-oracle-theme-bootstrap"),
      );
      await page.addStyleTag({ content: css });
      expect(await readChipPalette(page)).toEqual(PALETTE_DARK);
    }

    test("S1 — selector list judged on its first alternative (#6845 H1)", async ({
      page,
    }) => {
      await lightLeakCase(
        page,
        '.oracle-root[data-oracle-theme="dark"],.oracle-root[data-oracle-theme="light"]{--oracle-state-likely:#16683f}',
        ["row1", "row6"],
      );
    });

    test("S2 — a valued :not([...=dark]) read as *=dark, negation inverted (#6845 H2)", async ({
      page,
    }) => {
      await lightLeakCase(
        page,
        '.oracle-root:not([data-oracle-theme="dark"]){--oracle-state-likely:#16683f}',
        ["row1", "row6"],
      );
    });

    test("S3 — subset override in an un-anchored context (#6820 M6) — full row isolation", async ({
      page,
    }) => {
      const css =
        '@media (prefers-contrast: more){.oracle-root[data-oracle-theme="light"]{--oracle-state-likely:#16683f;--oracle-state-conditional:#16683f}}';
      await page.goto("/visa-oracle");
      await waitHydrated(page);
      await page.addStyleTag({ content: css });
      // Row 6 — RED, three-way collision (likely/conditional/eligible all
      // resolve to the same light "eligible" hex under prefers-contrast).
      await setRowContext(page, { contrast: "more" }, "light");
      const row6 = await readChipPalette(page);
      expect(threw(() => assertDistinct(row6, "S3 row6"))).toBe(true);
      // Row 1 — GREEN: the media condition never matches.
      await setRowContext(page, {}, "light");
      expect(await readChipPalette(page)).toEqual(PALETTE_LIGHT);
      // Rows 2, 3, 4 — GREEN: media never matches, or a higher-specificity
      // ancestor block wins.
      await assertDarkFamilyUnaffected(page, css);
    });

    test("S4 — the @media PRELUDE read as an assertion of dark (#6855 LEAK-1)", async ({
      page,
    }) => {
      await lightLeakCase(
        page,
        '@media not (prefers-color-scheme: dark){.oracle-root[data-oracle-theme="light"]{--oracle-state-likely:#16683f}}',
        ["row1", "row6"],
      );
    });

    test("S4b — PREDICTED: the same medium, a different feature (#6855 LEAK-2)", async ({
      page,
    }) => {
      // Predicted: RED row1, GREEN row6 — `not (prefers-contrast: more)`
      // matches "no-preference" (row1) but not "more" (row6).
      await page.goto("/visa-oracle");
      await waitHydrated(page);
      await page.addStyleTag({
        content:
          '@media not (prefers-contrast: more){.oracle-root[data-oracle-theme="light"]{--oracle-state-likely:#16683f}}',
      });
      await setRowContext(page, {}, "light");
      const row1 = await readChipPalette(page);
      const row1Leaked = threw(() => assertDistinct(row1, "S4b row1"));
      await setRowContext(page, { contrast: "more" }, "light");
      const row6 = await readChipPalette(page);
      // Measured, never reshaped (V13) — report what actually happened.
      expect(row1Leaked, "S4b row1 measured RED as predicted").toBe(true);
      expect(row6, "S4b row6 measured GREEN as predicted").toEqual(
        PALETTE_LIGHT,
      );
    });

    test('S5 — a pre-hydration DARK block keyed "light" (#6833 Q1/D3b)', async ({
      page,
    }) => {
      await blockHydrationBundle(page);
      await page.addInitScript(() =>
        window.localStorage.setItem("visa-oracle-theme", "dark"),
      );
      await page.goto("/visa-oracle", { waitUntil: "domcontentloaded" });
      await expect(page.locator("html")).toHaveAttribute(
        "data-oracle-theme-bootstrap",
        "dark",
      );
      await page.addStyleTag({
        content:
          'html[data-oracle-theme-bootstrap="dark"] .oracle-root[data-oracle-theme="light"]:not([data-oracle-theme-ready]){--oracle-state-likely:#4ade80}',
      });
      const row4 = await readChipPalette(page);
      expect(threw(() => assertDistinct(row4, "S5 row4"))).toBe(true);
    });

    test("S5b — PREDICTED: the same for block (d), row 5's own reach proof", async ({
      page,
    }) => {
      await blockHydrationBundle(page);
      await page.emulateMedia({ colorScheme: "dark" });
      await page.goto("/visa-oracle", { waitUntil: "domcontentloaded" });
      await page.evaluate(() =>
        document.documentElement.removeAttribute("data-oracle-theme-bootstrap"),
      );
      await page.addStyleTag({
        content:
          '@media (prefers-color-scheme: dark){html:not([data-oracle-theme-bootstrap]) .oracle-root[data-oracle-theme="light"]:not([data-oracle-theme-ready]){--oracle-state-likely:#4ade80}}',
      });
      const palette = await readChipPalette(page);
      // Measured, never reshaped (V13) — report what actually happened.
      expect(
        threw(() => assertDistinct(palette, "S5b row5")),
        "S5b row5 measured RED as predicted",
      ).toBe(true);
    });

    test("S6 — innocence: a DARK value dropped into the LIGHT context (#6833 D4)", async ({
      page,
    }) => {
      const css =
        '.oracle-root[data-oracle-theme="light"]{--oracle-state-likely:#4ade80}';
      await page.goto("/visa-oracle");
      await waitHydrated(page);
      await page.addStyleTag({ content: css });
      await setRowContext(page, {}, "light");
      const row1 = await readChipPalette(page);
      expect(threw(() => assertDistinct(row1, "S6 row1"))).toBe(false);
      await setRowContext(page, { contrast: "more" }, "light");
      const row6 = await readChipPalette(page);
      expect(threw(() => assertDistinct(row6, "S6 row6"))).toBe(false);
      await assertDarkFamilyUnaffected(page, css);
    });

    test("S7 — the background axis, invisible to an fg-only reading", async ({
      page,
    }) => {
      await page.goto("/visa-oracle");
      await waitHydrated(page);
      await page.addStyleTag({
        content:
          '.oracle-root[data-oracle-theme="light"]{--oracle-state-likely-bg:rgba(28,122,77,0.1)}',
      });
      await setRowContext(page, {}, "light");
      const row1 = await readChipPalette(page);
      expect(threw(() => assertDistinct(row1, "S7 row1"))).toBe(true);
      // The fg axis alone stays distinct — only the bg axis collided.
      const fgOnly = new Set(STATES.map((s) => row1[s].color));
      expect(fgOnly.size).toBe(STATES.length);
      await setRowContext(page, { contrast: "more" }, "light");
      const row6 = await readChipPalette(page);
      expect(threw(() => assertDistinct(row6, "S7 row6"))).toBe(true);
    });

    test("S8 — PREDICTED: the notation family, hex case and rgb() (#6820 M4/M5)", async ({
      page,
    }) => {
      await page.goto("/visa-oracle");
      await waitHydrated(page);
      const hexTag = await page.addStyleTag({
        content:
          '.oracle-root[data-oracle-theme="light"]{--oracle-state-likely:#16683F}',
      });
      await setRowContext(page, {}, "light");
      const rowHex = await readChipPalette(page);
      const hexCollided = threw(() =>
        assertDistinct(rowHex, "S8 row1 hex-case"),
      );
      await hexTag.evaluate((el) => el.remove());
      await page.addStyleTag({
        content:
          '.oracle-root[data-oracle-theme="light"]{--oracle-state-likely:rgb(22,104,63)}',
      });
      const rowRgb = await readChipPalette(page);
      const rgbCollided = threw(() => assertDistinct(rowRgb, "S8 row1 rgb()"));
      // Measured, never reshaped (V13) — report what actually happened.
      expect(hexCollided, "S8 hex-case measured RED as predicted").toBe(true);
      expect(rgbCollided, "S8 rgb() measured RED as predicted").toBe(true);
    });

    test("S9 — the floor: an invisible background is not a distinct one", async ({
      page,
    }) => {
      await page.goto("/visa-oracle");
      await waitHydrated(page);
      await page.addStyleTag({
        content:
          '.oracle-root[data-oracle-theme="light"]{--oracle-state-likely-bg:rgba(255,255,255,0)}',
      });
      await setRowContext(page, {}, "light");
      const palette = await readChipPalette(page);
      // String inequality alone would pass this — proving why the floor exists.
      expect(() => assertDistinct(palette, "S9 row1")).not.toThrow();
      expect(() => assertFloor(palette, "S9 row1")).toThrow(/alpha 0/);
    });

    test("floor — a chip census short of four states is a loud red, never silent", () => {
      const partial: Partial<Record<StateName, Swatch>> = {
        eligible: { color: "rgb(1,1,1)", backgroundColor: "rgba(1,1,1,0.1)" },
        likely: { color: "rgb(2,2,2)", backgroundColor: "rgba(2,2,2,0.1)" },
        conditional: {
          color: "rgb(3,3,3)",
          backgroundColor: "rgba(3,3,3,0.1)",
        },
      };
      expect(() => assertFloor(partial, "floor-missing")).toThrow(/found 3/);
    });
  });

  test("V9 — the probe is welded to the product by rendering one real verdict", async ({
    page,
  }) => {
    await seedVerdict(page);
    await page.route("**/api/visa-oracle/evaluate**", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(makeVisaOracleResponse()),
      }),
    );
    await page.goto("/visa-oracle");
    const chip = page.locator(".oracle-verdict-chip");
    await expect(chip).toBeVisible();
    const realState = await chip.getAttribute("data-state");
    expect(realState, "the real verdict renders a data-state").not.toBeNull();
    const real = await page.evaluate(() => {
      const el = document.querySelector(".oracle-verdict-chip");
      if (!el) throw new Error("state-fence weld: no rendered chip found");
      const computed = getComputedStyle(el);
      return {
        color: computed.color,
        backgroundColor: computed.backgroundColor,
      };
    });
    // Not one of the four CSS-styled literals: `legal.status` is hardcoded
    // to "SUPPORTED" at engine-adapter.ts:1523, so a real verdict's
    // data-state is always "supported" — CSS only styles
    // eligible/likely/conditional/likely-not (oracle.css:1037-1052). The
    // weld below still holds: it proves our injection technique computes
    // IDENTICALLY to the product's own render for whatever state is
    // actually reachable, which is what V9 welds — not that "supported"
    // happens to be one of the four palette entries.
    const synthetic = await page.evaluate((state) => {
      const root = document.querySelector<HTMLElement>(".oracle-root");
      if (!root) throw new Error("state-fence weld: no .oracle-root");
      const probe = document.createElement("span");
      probe.className = "oracle-verdict-chip";
      probe.dataset.state = state as string;
      root.appendChild(probe);
      const computed = getComputedStyle(probe);
      const out = {
        color: computed.color,
        backgroundColor: computed.backgroundColor,
      };
      probe.remove();
      return out;
    }, realState);
    expect(
      synthetic,
      `synthetic probe for real data-state="${realState}"`,
    ).toEqual(real);
  });
});
