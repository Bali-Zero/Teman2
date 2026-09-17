import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * GARUDA VOA — the cheap first-pass guard from `design-A-claude.md` §8 (guard
 * #3): "scan the six screens' .tsx for a hex/rgb/hsl literal and for a
 * red-family Tailwind utility. Catches M1 and M6 at source, as a cheap first
 * pass only." M6 was `background: "var(--accent-funnel, #ff3344)"` on the
 * primary CTA at the four sites this PR cures (`CheckoutFlow.tsx`,
 * `[hash]/page.tsx` ×2, `OrderTracker.tsx`); M1 is `text-red-600` on the
 * upload screen — a DIFFERENT lane's mandate (the error tone/contrast
 * theme), never touched here.
 *
 * SCANNER: a per-line, comment-aware regex on rendered source — same shape
 * as `desk-no-red.guard.test.ts` (convicts PAINT, never PROSE — cicatrix
 * family #3, guard-over-match). ALLOW-LISTS NOTHING within a bound screen:
 * unlike the desk scanner's `dangerToken`/`copperFillGuard` flags, there is
 * no per-token exemption here — every hex, every rgb()/hsl(), every
 * red-family Tailwind utility convicts.
 *
 * BINDING is a per-screen ratchet, same discipline as the desk scanner's
 * `DESK_PAGES`: "a page joins this list in the PR that restyles it, never
 * before — a baseline that lists a page it cannot hold is a guard that
 * reports green on uncured code." `SCREENS` below marks `bound: true` only
 * for the two screens that are ACTUALLY colour-literal-clean today:
 *   - `wizard` (`page.tsx`) — was already clean; never carried a literal.
 *   - `checkout` (`CheckoutFlow.tsx`) — this PR's fix leaves it clean: the
 *     ONLY literal it ever carried was the M6 red fallback this PR removes.
 * `verdict` and `tracker` are NOT bound yet: this PR cures their CTA's red
 * fallback (proven below, independent of the whole-screen scan), but both
 * screens still carry an UNRELATED literal outside this PR's scope — the
 * WhatsApp hand-off button's `#25D366`/`#0a0a0a` brand pair
 * (`[hash]/page.tsx:240-241`, `OrderTracker.tsx:345-346,389-390`), and
 * `OrderTracker.tsx:227` carries an `rgba(255,255,255,0.96)` fallback
 * unrelated to the action ground. `upload` is `UploadFlow.tsx`, still
 * carrying M1 (`text-red-600`) — a different lane's mandate. Widening the
 * ratchet to cover those four residuals here would be exactly the
 * guard-over-match this file is written to avoid: judging code this PR
 * never touched. Whichever lane cures each residual flips its `bound` flag
 * to `true` in the SAME commit — the ratchet only ever tightens.
 */

const VOA_DIR = (() => {
  const suffix = join("src", "app", "visa", "voa");
  for (const base of [process.cwd(), join(process.cwd(), "apps", "mouth")]) {
    const candidate = join(base, suffix);
    if (existsSync(candidate)) return candidate;
  }
  throw new Error(
    `visa/voa folder not found from ${process.cwd()} — the colour-literal scan cannot run`,
  );
})();

/**
 * The six purchase screens (verdict-ACCEPT and verdict-DECLINE share one
 * file), and whether THIS PR can hold each screen fully colour-literal-clean.
 */
const SCREENS: Array<{ name: string; file: string; bound: boolean }> = [
  { name: "wizard", file: "page.tsx", bound: true },
  {
    name: "verdict (ACCEPT + DECLINE)",
    file: "[hash]/page.tsx",
    bound: false, // residual: WhatsApp #25D366/#0a0a0a pair, out of scope here
  },
  {
    name: "upload",
    file: "upload/UploadFlow.tsx",
    bound: false, // residual: text-red-600 (M1) — a different lane's mandate
  },
  {
    name: "checkout",
    file: "checkout/[resultId]/CheckoutFlow.tsx",
    bound: true,
  },
  {
    name: "tracker",
    file: "orders/OrderTracker.tsx",
    bound: false, // residual: WhatsApp pair + rgba(255,255,255,0.96) marker
  },
];

/**
 * Code lines only — a comment is PROSE. Ported from
 * `desk-no-red.guard.test.ts` (same failure this file guards against: a
 * wrapped block comment must never be convicted for naming a colour in its
 * own explanation).
 */
function codeLines(text: string): Array<{ n: number; text: string }> {
  const out: Array<{ n: number; text: string }> = [];
  let inBlock = false;
  text.split("\n").forEach((line, i) => {
    const t = line.trimStart();
    const opensBlock = /\/\*/.test(line);
    const closesBlock = /\*\//.test(line);
    if (inBlock) {
      if (closesBlock) inBlock = false;
      return;
    }
    if (opensBlock && !closesBlock) {
      inBlock = true;
      return;
    }
    if (
      t.startsWith("//") ||
      t.startsWith("*") ||
      t.startsWith("/*") ||
      t.startsWith("{/*")
    ) {
      return;
    }
    out.push({ n: i + 1, text: line });
  });
  return out;
}

const HEX_RE = /#[0-9a-fA-F]{3,8}\b/;
const RGB_HSL_RE = /\brgba?\(|\bhsla?\(/;
const RED_UTIL_RE =
  /\b(?:bg|text|border|ring|divide|fill|stroke|from|to|via)-(?:red|rose|pink|orange|crimson)-\d/;

/** Exported so its own guilt/innocence is provable, same shape as the desk scanner. */
export function colourLiteralViolation(line: string): string | null {
  if (HEX_RE.test(line)) return "hardcoded hex";
  if (RGB_HSL_RE.test(line)) return "rgb()/hsl() literal";
  if (RED_UTIL_RE.test(line)) return "red Tailwind utility";
  return null;
}

function sourceOf(file: string): string {
  return readFileSync(join(VOA_DIR, file), "utf8");
}

describe("colourLiteralViolation — the scanner itself", () => {
  it("is GUILTY on a hex, an rgb()/hsl() call and a red Tailwind utility", () => {
    expect(colourLiteralViolation('background: "#ff3344",')).toBe(
      "hardcoded hex",
    );
    expect(colourLiteralViolation('color: "rgba(255,255,255,0.96)",')).toBe(
      "rgb()/hsl() literal",
    );
    expect(colourLiteralViolation('className="text-red-600"')).toBe(
      "red Tailwind utility",
    );
  });

  it("is INNOCENT on a token reference", () => {
    expect(
      colourLiteralViolation('style={{ background: "var(--state-success)" }}'),
    ).toBeNull();
  });

  it("codeLines() hides a comment naming a colour, so it never reaches the scanner", () => {
    const lines = codeLines(
      [
        "// was #ff3344, now the token",
        'const x = "var(--state-success)";',
      ].join("\n"),
    );
    expect(lines).toEqual([
      { n: 2, text: 'const x = "var(--state-success)";' },
    ]);
  });
});

describe("this PR's four cured CTA sites carry no colour literal", () => {
  const cases: Array<{ label: string; file: string }> = [
    {
      label: "checkout submit button",
      file: "checkout/[resultId]/CheckoutFlow.tsx",
    },
    {
      label: "verdict Try Visa Match CTA + magic-link resend button",
      file: "[hash]/page.tsx",
    },
    { label: "tracker retry button", file: "orders/OrderTracker.tsx" },
  ];

  for (const { label, file } of cases) {
    it(`${label} (${file}) imports the shared action-ground constant`, () => {
      expect(sourceOf(file)).toContain("VOA_PRIMARY_ACTION_STYLE");
    });

    it(`${label} (${file}) no longer carries the red fallback`, () => {
      expect(sourceOf(file)).not.toMatch(
        /var\(--accent-funnel,\s*#[0-9a-fA-F]{3,8}\)/,
      );
    });
  }
});

describe("no colour literal on the GARUDA VOA purchase screens this PR can hold clean", () => {
  for (const screen of SCREENS) {
    it(`${screen.name} has sources to scan`, () => {
      expect(existsSync(join(VOA_DIR, screen.file))).toBe(true);
    });

    if (!screen.bound) continue;

    it(`${screen.name} carries no colour literal`, () => {
      const offences: string[] = [];
      for (const { n, text } of codeLines(sourceOf(screen.file))) {
        const why = colourLiteralViolation(text);
        if (why) offences.push(`${screen.file}:${n} — ${why}`);
      }
      expect(offences).toEqual([]);
    });
  }

  it("the ratchet lists all six purchase screens even where not yet bound", () => {
    expect(SCREENS.map((s) => s.name)).toEqual([
      "wizard",
      "verdict (ACCEPT + DECLINE)",
      "upload",
      "checkout",
      "tracker",
    ]);
  });
});
