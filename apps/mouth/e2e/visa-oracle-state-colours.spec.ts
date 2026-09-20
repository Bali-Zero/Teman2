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
 *
 * OBS-1 cure (kit/CURE-SPEC-c1e-OBS-1.md, after vo-gate-c1e's
 * REWORK-BUILD on #6924): the first version of this file compared
 * `getComputedStyle` SERIALISATIONS with `===`. CSS Color 4 requires
 * `color()`/`oklch()`/`color-mix()`/relative colours to PRESERVE their
 * colour space at computed-value time instead of canonicalising to
 * `rgb()` — so two states painting the IDENTICAL pixel could pass a
 * string comparison. The cure: paint every computed value into a 1x1
 * canvas and compare the ENGINE's own `[r,g,b,a]` byte tuple
 * (`paintColourTuple` below) — the engine normalises, the test only
 * compares bytes. Declared limits of that read-back: it is 8-bit sRGB —
 * two colours closer than one 8-bit step, or two out-of-sRGB-gamut
 * colours that both clamp to the same byte tuple, compare EQUAL and go
 * RED (a loud false red, never a silent pass — and what an 8-bit display
 * shows the visitor is identical anyway, so this is the display's
 * quantisation, not a perceptual threshold; V3's "no perceptual
 * threshold" stands). Canvas stores PREMULTIPLIED pixels, so a
 * semi-transparent value is compared AFTER premultiplication, not as
 * authored (the shipped palette's alphas are measured in the PR body).
 */

const STATES = ["eligible", "likely", "conditional", "likely-not"] as const;
type StateName = (typeof STATES)[number];
type RGBA = [number, number, number, number];
type Swatch = {
  color: string;
  backgroundColor: string;
  colorTuple: RGBA;
  backgroundTuple: RGBA;
};
type Palette = Record<StateName, Swatch>;

/** OBS-1/2/3 cure: paint a computed colour string into a 1x1 canvas and
 * read the ENGINE's own RGBA bytes back — the engine normalises colour
 * spaces, the test only compares the painted bytes it hands back (module
 * docstring above; kit/CURE-SPEC-c1e-OBS-1.md §1). Kept as a standalone,
 * directly-callable function so the canvas guilt test below can exercise
 * it in isolation; `readChipPalette` inlines the identical algorithm into
 * its own single `page.evaluate` call to avoid nine round trips per
 * palette read (perf only — the logic must stay in lock-step with this).
 *
 * Canvas has a silent-pass path (scar #2): assigning an unparseable
 * `fillStyle` is IGNORED and the PREVIOUS fillStyle paints instead —
 * closed by priming with two DIFFERENT sentinels before each attempt. A
 * valid value paints identically regardless of the sentinel; a rejected
 * one leaves each attempt showing its OWN sentinel, so the two reads
 * differ — the loud failure this throws, naming the state, the axis and
 * the raw computed string (never a silent pass).
 */
function paintColourTuple(args: {
  value: string;
  state: string;
  axis: string;
}): RGBA {
  const { value, state, axis } = args;
  const canvas = document.createElement("canvas");
  canvas.width = 1;
  canvas.height = 1;
  const ctx = canvas.getContext("2d", { willReadFrequently: true })!;
  const paint = (sentinel: string): Uint8ClampedArray => {
    ctx.clearRect(0, 0, 1, 1);
    ctx.fillStyle = sentinel;
    ctx.fillStyle = value;
    ctx.fillRect(0, 0, 1, 1);
    return ctx.getImageData(0, 0, 1, 1).data;
  };
  const a = paint("#000000");
  const b = paint("#ffffff");
  if (a[0] !== b[0] || a[1] !== b[1] || a[2] !== b[2] || a[3] !== b[3]) {
    throw new Error(
      `state-fence: ${state} ${axis} — canvas rejected colour "${value}" (sentinel read-backs [${Array.from(a)}] vs [${Array.from(b)}])`,
    );
  }
  return [a[0], a[1], a[2], a[3]];
}

/** V1 — inject the product's own chip class into the live `.oracle-root`
 * (real stylesheet, real cascade, real theme/media state); read only the
 * RENDERED computed style, never a custom property. Returns both the raw
 * computed string (V1's own shape guilt) and the painted `[r,g,b,a]`
 * tuple (V3/V7's comparison — see `paintColourTuple`). */
async function readChipPalette(page: Page): Promise<Palette> {
  return page.evaluate((states) => {
    const root = document.querySelector<HTMLElement>(".oracle-root");
    if (!root) throw new Error("state-fence: no .oracle-root in the page");
    const canvas = document.createElement("canvas");
    canvas.width = 1;
    canvas.height = 1;
    const ctx = canvas.getContext("2d", { willReadFrequently: true })!;
    // Identical algorithm to `paintColourTuple` above, inlined for one
    // round trip instead of nine (perf only — keep both in lock-step).
    function toTuple(
      value: string,
      state: string,
      axis: string,
    ): [number, number, number, number] {
      function paint(sentinel: string): Uint8ClampedArray {
        ctx.clearRect(0, 0, 1, 1);
        ctx.fillStyle = sentinel;
        ctx.fillStyle = value;
        ctx.fillRect(0, 0, 1, 1);
        return ctx.getImageData(0, 0, 1, 1).data;
      }
      const a = paint("#000000");
      const b = paint("#ffffff");
      if (a[0] !== b[0] || a[1] !== b[1] || a[2] !== b[2] || a[3] !== b[3]) {
        throw new Error(
          `state-fence: ${state} ${axis} — canvas rejected colour "${value}" (sentinel read-backs [${Array.from(a)}] vs [${Array.from(b)}])`,
        );
      }
      return [a[0], a[1], a[2], a[3]];
    }
    const out: Record<
      string,
      {
        color: string;
        backgroundColor: string;
        colorTuple: [number, number, number, number];
        backgroundTuple: [number, number, number, number];
      }
    > = {};
    for (const state of states) {
      const chip = document.createElement("span");
      chip.className = "oracle-verdict-chip";
      chip.dataset.state = state;
      chip.dataset.stateFenceProbe = "true";
      root.appendChild(chip);
      const computed = getComputedStyle(chip);
      const color = computed.color;
      const backgroundColor = computed.backgroundColor;
      out[state] = {
        color,
        backgroundColor,
        colorTuple: toTuple(color, state, "fg"),
        backgroundTuple: toTuple(backgroundColor, state, "bg"),
      };
      chip.remove();
    }
    return out;
  }, STATES) as Promise<Palette>;
}

/** V7 — the floor: loud red, never a silent pass, when the chip census or
 * a MEASURED alpha byte says a "distinct" colour is actually invisible.
 * Runs BEFORE distinctness: canvas stores PREMULTIPLIED pixels, so every
 * alpha-0 colour reads back `[0,0,0,0]` regardless of its authored RGB —
 * if distinctness ran first, a lone alpha-0 state could escape detection
 * entirely (nothing else happens to be `[0,0,0,0]` too), so invisibility
 * must be caught here first. Checks BOTH axes (OBS-3: the prior version
 * checked `backgroundColor` only) with a measured byte, never a regex
 * (OBS-2: a hand-rolled regex over a colour value both missed
 * `oklch(… / 0)` and false-fired on any opaque `rgb(r, g, 0)`). */
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
    const swatch = palette[state]!;
    if (swatch.colorTuple[3] === 0) {
      throw new Error(
        `${label}: floor — "${state}"'s foreground is alpha 0 (measured byte; raw "${swatch.color}"), not a distinct colour`,
      );
    }
    if (swatch.backgroundTuple[3] === 0) {
      throw new Error(
        `${label}: floor — "${state}"'s background is alpha 0 (measured byte; raw "${swatch.backgroundColor}"), not a distinct colour`,
      );
    }
  }
}

function tuplesEqual(a: RGBA, b: RGBA): boolean {
  return a[0] === b[0] && a[1] === b[1] && a[2] === b[2] && a[3] === b[3];
}

/** V3 — distinctness is EXACT inequality, pairwise, both axes, compared
 * as PAINTED `[r,g,b,a]` tuples, never serialised strings (module
 * docstring; OBS-1 cure): CSS Color 4 keeps `color()`/`oklch()`/
 * `color-mix()`/relative colours in their own space instead of
 * canonicalising to `rgb()`, so two states painting the identical pixel
 * could pass a string `===` while a byte comparison never can. No
 * perceptual threshold: #6820 pins declared-literal distinctness and it
 * stays in force (R-SUSPEND-C1b). */
function assertDistinct(palette: Palette, label: string): void {
  for (let i = 0; i < STATES.length; i++) {
    for (let j = i + 1; j < STATES.length; j++) {
      const a = STATES[i];
      const b = STATES[j];
      if (tuplesEqual(palette[a].colorTuple, palette[b].colorTuple)) {
        throw new Error(
          `${label}: "${a}" and "${b}" paint the same fg pixel [${palette[a].colorTuple.join(",")}] (raw "${palette[a].color}" vs "${palette[b].color}")`,
        );
      }
      if (tuplesEqual(palette[a].backgroundTuple, palette[b].backgroundTuple)) {
        throw new Error(
          `${label}: "${a}" and "${b}" paint the same bg pixel [${palette[a].backgroundTuple.join(",")}] (raw "${palette[a].backgroundColor}" vs "${palette[b].backgroundColor}")`,
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

/** Same as `threw`, but keeps the message. OBS-7: a guilt test must pin
 * WHICH pair/axis collided, not just that "a" pair did. */
function caught(fn: () => void): string {
  try {
    fn();
    return "";
  } catch (e) {
    return (e as Error).message;
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
  // OBS-8: serial mode is REQUIRED here, not incidental — rows 3-6 and the
  // whole guilt/weld matrix below read the module-scoped `PALETTE_LIGHT`/
  // `PALETTE_DARK` closures that rows 1/2 populate, so file order matters
  // (the config's `fullyParallel` would otherwise race them). The known
  // cost is accepted: a red in one test hides the rest of the matrix in
  // that run; nothing here removes zero-colour-literal comparisons, which
  // is what the shared closures buy.
  test.describe.configure({ mode: "serial" });

  let PALETTE_LIGHT: Palette;
  let PALETTE_DARK: Palette;

  test("row 1 — light, hydrated (defines PALETTE_LIGHT)", async ({ page }) => {
    // OBS-6: pin the default explicitly — `playwright.config.ts` sets
    // neither `colorScheme` nor `contrast` in `use:`, so this row was
    // relying on Playwright's own default.
    await page.emulateMedia({
      colorScheme: "light",
      contrast: "no-preference",
    });
    await page.goto("/visa-oracle");
    await waitHydrated(page);
    await expect(page.locator(".oracle-root")).toHaveAttribute(
      "data-oracle-theme",
      "light",
    );
    PALETTE_LIGHT = await readChipPalette(page);
    assertFloor(PALETTE_LIGHT, "row1"); // floor BEFORE distinctness (V7 doc above).
    assertDistinct(PALETTE_LIGHT, "row1");
    // V1 guilt: the probe's light-row output is rgb(...)-shaped, never #...-shaped.
    for (const state of STATES) {
      expect(PALETTE_LIGHT[state].color, `row1 ${state} fg`).toMatch(/^rgb\(/);
      expect(PALETTE_LIGHT[state].backgroundColor, `row1 ${state} bg`).toMatch(
        /^rgba?\(/,
      );
    }
  });

  test("row 2 — dark, hydrated (defines PALETTE_DARK)", async ({ page }) => {
    // OBS-6: pin the default explicitly (see row 1).
    await page.emulateMedia({
      colorScheme: "light",
      contrast: "no-preference",
    });
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
    assertFloor(PALETTE_DARK, "row2"); // floor BEFORE distinctness.
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
    // OBS-6: pin the default explicitly (see row 1).
    await page.emulateMedia({
      colorScheme: "light",
      contrast: "no-preference",
    });
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

  test("guilt — the canvas normaliser closes its own silent-pass path (scar #2)", async ({
    page,
  }) => {
    await page.goto("/visa-oracle");
    // Direct exercise of `paintColourTuple` in isolation (not through
    // `readChipPalette`): a string the browser's canvas 2D context cannot
    // parse must be a LOUD red naming the state/axis/value, never a
    // silent pass through the previous sentinel.
    await expect(
      page.evaluate(paintColourTuple, {
        value: "not-a-real-colour",
        state: "guilt-probe",
        axis: "fg",
      }),
    ).rejects.toThrow(/canvas rejected colour "not-a-real-colour"/);
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
      expectedMatch: RegExp,
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
        // OBS-7: pin WHICH pair/axis collided, not just "a" pair.
        expect(() => assertDistinct(palette, `S:${row}`)).toThrow(
          expectedMatch,
        );
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

    const ELIGIBLE_LIKELY_FG =
      /"eligible" and "likely" paint the same fg pixel/;

    test("S1 — selector list judged on its first alternative (#6845 H1)", async ({
      page,
    }) => {
      await lightLeakCase(
        page,
        '.oracle-root[data-oracle-theme="dark"],.oracle-root[data-oracle-theme="light"]{--oracle-state-likely:#16683f}',
        ["row1", "row6"],
        ELIGIBLE_LIKELY_FG,
      );
    });

    test("S2 — a valued :not([...=dark]) read as *=dark, negation inverted (#6845 H2)", async ({
      page,
    }) => {
      await lightLeakCase(
        page,
        '.oracle-root:not([data-oracle-theme="dark"]){--oracle-state-likely:#16683f}',
        ["row1", "row6"],
        ELIGIBLE_LIKELY_FG,
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
      // Row 6 — RED: eligible, likely AND conditional all resolve to the
      // same light "eligible" hex under prefers-contrast; assertDistinct
      // reports the FIRST colliding pair it finds in STATES order
      // (eligible/likely, fg) — OBS-7: pin exactly that, not "a" pair.
      await setRowContext(page, { contrast: "more" }, "light");
      const row6 = await readChipPalette(page);
      expect(() => assertDistinct(row6, "S3 row6")).toThrow(ELIGIBLE_LIKELY_FG);
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
        ELIGIBLE_LIKELY_FG,
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
      const row1Message = caught(() => assertDistinct(row1, "S4b row1"));
      await setRowContext(page, { contrast: "more" }, "light");
      const row6 = await readChipPalette(page);
      // Measured, never reshaped (V13) — report what actually happened.
      expect(row1Message, "S4b row1 measured RED as predicted").toMatch(
        ELIGIBLE_LIKELY_FG,
      );
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
      const message = caught(() => assertDistinct(row4, "S5 row4"));
      // OBS-7: pin WHICH pair/axis collided — #4ade80 is block (c)'s own
      // natural "eligible" (PALETTE_DARK), so keying it onto "likely"
      // collides likely with eligible on the fg axis (measured).
      expect(message, "S5 row4 measured RED").toMatch(ELIGIBLE_LIKELY_FG);
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
      const message = caught(() => assertDistinct(palette, "S5b row5"));
      // Measured, never reshaped (V13) — report what actually happened.
      expect(message, "S5b row5 measured RED as predicted").toMatch(
        ELIGIBLE_LIKELY_FG,
      );
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
      const row1Message = caught(() => assertDistinct(row1, "S7 row1"));
      expect(row1Message, "S7 row1 measured RED on the bg axis").toMatch(
        /paint the same bg pixel/,
      );
      // The fg axis alone stays distinct — only the bg axis collided.
      const fgOnly = new Set(STATES.map((s) => row1[s].colorTuple.join(",")));
      expect(fgOnly.size).toBe(STATES.length);
      await setRowContext(page, { contrast: "more" }, "light");
      const row6 = await readChipPalette(page);
      expect(
        caught(() => assertDistinct(row6, "S7 row6")),
        "S7 row6 measured RED on the bg axis",
      ).toMatch(/paint the same bg pixel/);
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
      const hexMessage = caught(() =>
        assertDistinct(rowHex, "S8 row1 hex-case"),
      );
      await hexTag.evaluate((el: HTMLStyleElement) => el.remove());
      await page.addStyleTag({
        content:
          '.oracle-root[data-oracle-theme="light"]{--oracle-state-likely:rgb(22,104,63)}',
      });
      const rowRgb = await readChipPalette(page);
      const rgbMessage = caught(() => assertDistinct(rowRgb, "S8 row1 rgb()"));
      // Measured, never reshaped (V13) — report what actually happened.
      expect(hexMessage, "S8 hex-case measured RED as predicted").toMatch(
        ELIGIBLE_LIKELY_FG,
      );
      expect(rgbMessage, "S8 rgb() measured RED as predicted").toMatch(
        ELIGIBLE_LIKELY_FG,
      );
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
      // Byte inequality alone would NOT catch this either — a fully
      // transparent white and any opaque colour still paint different
      // tuples. This is exactly why the floor exists as its own check.
      expect(() => assertDistinct(palette, "S9 row1")).not.toThrow();
      expect(() => assertFloor(palette, "S9 row1")).toThrow(/alpha 0/);
    });

    test("S10 — OBS-1 witness: the identical colour spelled in a modern colour space collides across every dark context (color-mix vs legacy, CSS Color 4)", async ({
      page,
    }) => {
      // The exact case measured in GATE-C1E-REPORT-6924.md's pixel proof:
      // `color-mix(in srgb, #4ade80 100%, white 0%)` paints IDENTICALLY to
      // `#4ade80` (dark's own "eligible"), so keying it onto "likely" in
      // each of the three dark blocks collides likely/eligible on fg —
      // invisible to the old string-equality instrument, caught here by
      // the painted-byte comparison.
      const css = [
        '.oracle-root[data-oracle-theme="dark"]{--oracle-state-likely:color-mix(in srgb, #4ade80 100%, white 0%)}',
        'html[data-oracle-theme-bootstrap="dark"] .oracle-root[data-oracle-theme="light"]:not([data-oracle-theme-ready]){--oracle-state-likely:color-mix(in srgb, #4ade80 100%, white 0%)}',
        '@media (prefers-color-scheme: dark){html:not([data-oracle-theme-bootstrap]) .oracle-root[data-oracle-theme="light"]:not([data-oracle-theme-ready]){--oracle-state-likely:color-mix(in srgb, #4ade80 100%, white 0%)}}',
      ].join("\n");

      // Row 2 — hydrated dark.
      await page.goto("/visa-oracle");
      await waitHydrated(page);
      await page.addStyleTag({ content: css });
      await setRowContext(page, {}, "dark");
      const row2 = await readChipPalette(page);
      expect(
        caught(() => assertDistinct(row2, "S10 row2")),
        "S10 row2 measured RED",
      ).toMatch(ELIGIBLE_LIKELY_FG);

      // Row 3 — dark, system-dark (same selector, live media switch).
      await setRowContext(page, { colorScheme: "dark" }, "dark");
      const row3 = await readChipPalette(page);
      expect(
        caught(() => assertDistinct(row3, "S10 row3")),
        "S10 row3 measured RED",
      ).toMatch(ELIGIBLE_LIKELY_FG);

      // Row 4 — pre-hydration bootstrap dark.
      await blockHydrationBundle(page);
      await page.addInitScript(() =>
        window.localStorage.setItem("visa-oracle-theme", "dark"),
      );
      await page.goto("/visa-oracle", { waitUntil: "domcontentloaded" });
      await page.addStyleTag({ content: css });
      const row4 = await readChipPalette(page);
      expect(
        caught(() => assertDistinct(row4, "S10 row4")),
        "S10 row4 measured RED",
      ).toMatch(ELIGIBLE_LIKELY_FG);

      // Row 5 — pre-hydration, no bootstrap, system dark.
      await blockHydrationBundle(page);
      await page.emulateMedia({ colorScheme: "dark" });
      await page.goto("/visa-oracle", { waitUntil: "domcontentloaded" });
      await page.evaluate(() =>
        document.documentElement.removeAttribute("data-oracle-theme-bootstrap"),
      );
      await page.addStyleTag({ content: css });
      const row5 = await readChipPalette(page);
      expect(
        caught(() => assertDistinct(row5, "S10 row5")),
        "S10 row5 measured RED",
      ).toMatch(ELIGIBLE_LIKELY_FG);

      // Light family unaffected — none of the three selectors ever match
      // theme="light" outside the pre-hydration guards above. Rows 4/5
      // above left the hydration-bundle route handler attached to this
      // `page`; without removing it this final `goto` would inherit the
      // block and `waitHydrated` would never resolve.
      await page.unroute("**/_next/static/chunks/**");
      await page.goto("/visa-oracle");
      await waitHydrated(page);
      await page.addStyleTag({ content: css });
      await setRowContext(page, {}, "light");
      expect(await readChipPalette(page)).toEqual(PALETTE_LIGHT);
      await setRowContext(page, { contrast: "more" }, "light");
      expect(await readChipPalette(page)).toEqual(PALETTE_LIGHT);
    });

    test("S11 — floor: an alpha-0 FOREGROUND is not a distinct colour (OBS-3)", async ({
      page,
    }) => {
      await page.goto("/visa-oracle");
      await waitHydrated(page);
      await page.addStyleTag({
        content:
          '.oracle-root[data-oracle-theme="light"]{--oracle-state-likely:rgba(0,0,0,0)}',
      });
      await setRowContext(page, {}, "light");
      const palette = await readChipPalette(page);
      expect(() => assertFloor(palette, "S11 row1")).toThrow(/alpha 0/);
    });

    test("S12 — floor: an alpha-0 background written oklch(.. / 0) is not a distinct colour (OBS-2 false negative closed)", async ({
      page,
    }) => {
      await page.goto("/visa-oracle");
      await waitHydrated(page);
      await page.addStyleTag({
        content:
          '.oracle-root[data-oracle-theme="light"]{--oracle-state-likely-bg:oklch(0.7 0.15 150 / 0)}',
      });
      await setRowContext(page, {}, "light");
      const palette = await readChipPalette(page);
      // The old regex (`rgba?\(...\)`) never matched `oklch()` and
      // silently returned the default "1" — measured byte catches it.
      expect(() => assertFloor(palette, "S12 row1")).toThrow(/alpha 0/);
    });

    test("S13 — innocence: an OPAQUE background with a zero BLUE channel is not alpha-0 (OBS-2 false positive closed)", async ({
      page,
    }) => {
      await page.goto("/visa-oracle");
      await waitHydrated(page);
      await page.addStyleTag({
        content:
          '.oracle-root[data-oracle-theme="light"]{--oracle-state-likely-bg:rgb(255,128,0)}',
      });
      await setRowContext(page, {}, "light");
      const palette = await readChipPalette(page);
      // The old regex read "the last numeric run before `)`" — for an
      // OPAQUE rgb() that is the blue channel, so rgb(255,128,0) false-
      // fired "alpha 0". The measured byte reads the real alpha channel.
      expect(() => assertFloor(palette, "S13 row1")).not.toThrow();
    });

    test("S14 — OBS-4: a NON-adjacent pair, eligible <-> likely-not (the legal-adjacent risk this slice exists for)", async ({
      page,
    }) => {
      await lightLeakCase(
        page,
        '.oracle-root[data-oracle-theme="light"]{--oracle-state-likely-not:var(--oracle-state-eligible);--oracle-state-likely-not-bg:var(--oracle-state-eligible-bg)}',
        ["row1", "row6"],
        /"eligible" and "likely-not" paint the same fg pixel/,
      );
    });

    test("S15 — OBS-4: a second NON-adjacent pair, eligible <-> conditional", async ({
      page,
    }) => {
      await lightLeakCase(
        page,
        '.oracle-root[data-oracle-theme="light"]{--oracle-state-conditional:var(--oracle-state-eligible);--oracle-state-conditional-bg:var(--oracle-state-eligible-bg)}',
        ["row1", "row6"],
        /"eligible" and "conditional" paint the same fg pixel/,
      );
    });

    test("S16 — OBS-4: a third NON-adjacent pair, likely <-> likely-not", async ({
      page,
    }) => {
      await lightLeakCase(
        page,
        '.oracle-root[data-oracle-theme="light"]{--oracle-state-likely-not:var(--oracle-state-likely);--oracle-state-likely-not-bg:var(--oracle-state-likely-bg)}',
        ["row1", "row6"],
        /"likely" and "likely-not" paint the same fg pixel/,
      );
    });

    test("floor — a chip census short of four states is a loud red, never silent", () => {
      const dummy: RGBA = [1, 1, 1, 255];
      const partial: Partial<Record<StateName, Swatch>> = {
        eligible: {
          color: "rgb(1,1,1)",
          backgroundColor: "rgba(1,1,1,0.1)",
          colorTuple: dummy,
          backgroundTuple: dummy,
        },
        likely: {
          color: "rgb(2,2,2)",
          backgroundColor: "rgba(2,2,2,0.1)",
          colorTuple: dummy,
          backgroundTuple: dummy,
        },
        conditional: {
          color: "rgb(3,3,3)",
          backgroundColor: "rgba(3,3,3,0.1)",
          colorTuple: dummy,
          backgroundTuple: dummy,
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
