import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, it, expect } from "vitest";

/**
 * The "no red" law of the kita DESK (SAETTA-R19K window K2). It covers the
 * four desk families — `/dashboard`, `/notifications`, `/review`,
 * `/obligations` — one PR at a time; `DESK_PAGES` below says which of them it
 * binds today and why.
 *
 * concept-K v2 §3 and the primitives README say it the same way: kita has four
 * meanings and none of them is red. A dangerous state is carried by a WORD and
 * by copper, forest, slate, warning or muted — never by a red fill, a red hex
 * or a red Tailwind family.
 *
 * WHAT THIS GUARD JUDGES, and why it is an entity and not a substring.
 * Cicatrix family #3 (guard-over-match) is the failure where a guard decides
 * guilt by "does this line contain the string". So this one bans two shapes
 * that can only be a colour, and names its one exemption explicitly:
 *
 *   1. a literal hex anywhere in code — the only way a raw red gets in;
 *   2. a red-family Tailwind utility — `bg-red-600`, `text-rose-500`, …;
 *   3. a read of `--state-danger`, which on kita RESOLVES to copper and so is
 *      not itself red, but which the K2 brief bans on these pages because a
 *      page that reads the danger name will paint red the day it is mounted on
 *      a surface that is not `data-product="kita"`.
 *
 * The exemption is `/notifications`, BY NAME and with its reason:
 * `token-drain.residuals.guard.test.ts` pins that page to `--state-success`,
 * `--state-warning` and `--state-danger` as the proof of the WS2 token drain.
 * Deleting the read to satisfy rule 3 would break that pin, so the two guards
 * are reconciled here rather than one of them being quietly weakened. Rules 1
 * and 2 — the ones that can actually paint red — bind notifications like every
 * other desk page.
 *
 * WHAT THIS GUARD DOES NOT SEE, stated so nobody reads its green as more than
 * it is. It scans the pages' OWN source files. It does not follow an import,
 * so a component a desk page RENDERS but does not own is outside it — on the
 * dashboard that is `SystemPulse` and `ComplianceRadar` from
 * `packages/core/components/`, both of which read `--state-danger` today
 * (`SystemPulse.tsx:28`, `ComplianceRadar.tsx:61`). Neither paints red on
 * kita, where `--state-danger` resolves to copper, and neither is in window
 * K2's writable perimeter — they belong to the packages/core seam. Widening
 * the scan to the whole render tree is the right shape and the wrong window:
 * it would judge code this page never touched, which is exactly the
 * guard-over-match failure this file is written to avoid. Recorded here as a
 * residual for the window that owns those two components.
 */

const DESK_DIR = (() => {
  const suffix = join("src", "app", "(workspace)");
  for (const base of [process.cwd(), join(process.cwd(), "apps", "mouth")]) {
    const candidate = join(base, suffix);
    if (existsSync(candidate)) return candidate;
  }
  throw new Error(
    `(workspace) folder not found from ${process.cwd()} — the no-red scan cannot run`,
  );
})();

/**
 * The desk families this guard binds TODAY, and whether the danger NAME is
 * allowed on each.
 *
 * A page joins this list in the PR that restyles it, never before: a baseline
 * that lists a page it cannot hold is a guard that reports green on uncured
 * code. `/review` joins in K2b and `/obligations` in K2c, each flipping to
 * `dangerToken: false` in the same commit that removes its last danger read —
 * so the ratchet only ever tightens, and it tightens with the content that
 * earns it.
 */
const DESK_PAGES: Array<{ name: string; dir: string; dangerToken: boolean }> = [
  { name: "dashboard", dir: "dashboard", dangerToken: false },
  // See the doc block: pinned by the WS2 residuals drain guard.
  { name: "notifications", dir: "notifications", dangerToken: true },
  { name: "review", dir: "review", dangerToken: false },
];

/** Rendered sources only — a test file's fixtures are not the page's paint. */
function sourcesOf(dir: string): string[] {
  const root = join(DESK_DIR, dir);
  const out: string[] = [];
  const walk = (d: string) => {
    for (const entry of readdirSync(d)) {
      const p = join(d, entry);
      if (statSync(p).isDirectory()) {
        if (entry === "__tests__") continue;
        walk(p);
        continue;
      }
      if (!/\.tsx?$/.test(entry)) continue;
      if (/\.test\.tsx?$/.test(entry)) continue;
      out.push(p);
    }
  };
  walk(root);
  return out;
}

function codeLines(file: string): Array<{ n: number; text: string }> {
  return readFileSync(file, "utf8")
    .split("\n")
    .map((text, i) => ({ n: i + 1, text }))
    .filter(({ text }) => {
      const t = text.trimStart();
      if (
        t.startsWith("//") ||
        t.startsWith("*") ||
        t.startsWith("/*") ||
        t.startsWith("{/*")
      ) {
        return false;
      }
      return !text.includes("token-lint-ok:");
    });
}

const HEX_RE = /#[0-9a-fA-F]{3,8}\b/;
const RED_UTIL_RE =
  /\b(?:bg|text|border|ring|divide|fill|stroke|from|to|via)-(?:red|rose|pink|orange|crimson)-\d/;

const COPPER_TOKEN = "(?:--bz-copper-text|--bz-copper|--bz-accent)";
/**
 * Copper is NEVER a fill (globals.css: "Copper = needs you. Never a button
 * fill."). This judges the ENTITY — a copper token used AS a fill — not a
 * bare substring, so each shape requires the token to sit INSIDE the fill
 * declaration itself, not merely somewhere later on a long `className`:
 *   1. the Tailwind arbitrary-value shape, `bg-[...]`, with the token
 *      inside THAT SAME bracket pair (a later `ring-[var(--bz-copper)]` on
 *      the same line, after an unrelated `bg-[var(--bz-card)]`, must not
 *      trip this — that would be guard-over-match, cicatrix family #3);
 *   2. the CSS/JS property shape, `background`/`background-color`/
 *      `backgroundColor`, with the token before the next `;`, `,`, `}` or
 *      end of line — never allowed to bleed into an unrelated later prop.
 * The same token behind `border`/`text`/`ring`/anything else stays
 * innocent either way.
 */
const COPPER_FILL_RE = new RegExp(
  `\\bbg-\\[[^\\]]*${COPPER_TOKEN}[^\\]]*\\]` +
    `|\\b(?:background(?:-color)?|backgroundColor)\\s*:\\s*[^;,\\n}]*?${COPPER_TOKEN}`,
);

/**
 * Per-page ratchet for the copper-fill rule, same shape and reason as
 * `dangerToken` above: a page earns the tightened check in the PR that
 * cures its last copper fill, never before. `review` earns it in K2b
 * (CURE 4). `notifications` has none today but has not been swept either.
 *
 * `dashboard` is exempt for a reason worth reading before flipping it,
 * because the three copper fills it carries are NOT the same thing and
 * only one is a defect (all in `dashboard/PortalChallengeWidget.tsx`):
 *   :274  a PROGRESS BAR filled copper — a real violation. A metric's
 *         magnitude is not "the viewer is the next actor", and this is a
 *         fill in the plain sense the token's own comment forbids.
 *   :578  a 1.5px copper DOT — the pill's pip. concept-K gives the state
 *         pill a copper pip by name; legitimate.
 *   :756  a 3px copper RULE — the masthead's own mark, the same family as
 *         the 96x4 rule the concept opens every page with; legitimate.
 * So this regex, which cannot tell a 3px rule from a progress bar, WILL
 * over-match two innocent marks the day `dashboard` is added. Whoever
 * flips it must either narrow the entity (a copper fill on a box with
 * height, not on a hairline or a pip) or exempt those two lines
 * explicitly. Flipping it as-is would be cicatrix family #3 in the OVER
 * direction, which is the failure this file's own comments warn about.
 */
const COPPER_FILL_PAGES = new Set(["review"]);

/** The scanner. Exported so its own guilt and innocence are provable below. */
export function redViolation(
  line: string,
  opts: { dangerToken: boolean; copperFillGuard?: boolean },
): string | null {
  if (HEX_RE.test(line)) return "hardcoded hex";
  if (RED_UTIL_RE.test(line)) return "red Tailwind utility";
  if (!opts.dangerToken && line.includes("--state-danger")) {
    return "reads --state-danger";
  }
  if ((opts.copperFillGuard ?? true) && COPPER_FILL_RE.test(line)) {
    return "copper used as a fill";
  }
  return null;
}

describe("the desk no-red scanner", () => {
  const strict = { dangerToken: false };

  it("is GUILTY on the three shapes that put red back", () => {
    const redHexLine = '  style={{ color: "#b91c1c" }}'; // token-lint-ok: scanner fixture, not a colour use
    expect(redViolation(redHexLine, strict)).toBe("hardcoded hex");
    expect(redViolation('  className="bg-red-600"', strict)).toBe(
      "red Tailwind utility",
    );
    expect(redViolation('  "text-[var(--state-danger)]"', strict)).toBe(
      "reads --state-danger",
    );
  });

  it("is INNOCENT on the kita idiom the concept actually uses", () => {
    for (const line of [
      '  className="text-[var(--bz-copper-text)]"',
      '  className="border-[var(--bz-copper)]"',
      '  className="border-[var(--state-success)]"',
      '  className="text-[var(--state-warning)]"',
      '  className="text-[var(--state-info)]"',
      '  className="text-[var(--tx-secondary)]"',
    ]) {
      expect(redViolation(line, strict), line).toBeNull();
    }
  });

  it("is GUILTY on a copper FILL — copper is never a background", () => {
    // A `style={{ background: ... }}` fill on --bz-accent (kita: === copper).
    expect(
      redViolation('  style={{ background: "var(--bz-accent)" }}', strict),
    ).toBe("copper used as a fill");
    // The Tailwind arbitrary-value shape of the same violation.
    expect(redViolation('  className="bg-[var(--bz-copper)]"', strict)).toBe(
      "copper used as a fill",
    );
    // The ENTITY, not the substring: the same tokens as border/text colours
    // (not a fill) must stay innocent — pinned again here alongside guilt so
    // the two are read together.
    expect(
      redViolation('  className="border-[var(--bz-copper)]"', strict),
    ).toBeNull();
    expect(
      redViolation('  className="text-[var(--bz-copper-text)]"', strict),
    ).toBeNull();
  });

  it("exempts the danger NAME only where a page is pinned to it", () => {
    const line = '  color: "var(--state-danger)",';
    expect(redViolation(line, { dangerToken: false })).toBe(
      "reads --state-danger",
    );
    expect(redViolation(line, { dangerToken: true })).toBeNull();
    // The exemption never reaches the two shapes that can really paint red.
    const redHexLine = '  background: "#ef4444"'; // token-lint-ok: scanner fixture, not a colour use
    expect(redViolation(redHexLine, { dangerToken: true })).toBe(
      "hardcoded hex",
    );
  });
});

describe("no red on the kita desk", () => {
  for (const page of DESK_PAGES) {
    it(`${page.name} has sources to scan`, () => {
      expect(sourcesOf(page.dir).length).toBeGreaterThan(0);
    });

    it(`${page.name} carries no red`, () => {
      const offences: string[] = [];
      for (const file of sourcesOf(page.dir)) {
        for (const { n, text } of codeLines(file)) {
          const why = redViolation(text, {
            dangerToken: page.dangerToken,
            copperFillGuard: COPPER_FILL_PAGES.has(page.name),
          });
          if (why) {
            offences.push(`${file.slice(DESK_DIR.length + 1)}:${n} — ${why}`);
          }
        }
      }
      expect(offences).toEqual([]);
    });
  }
});
