import { describe, expect, it } from "vitest";
import { R19_CLASS, R19_DIRECTION_A_VARS } from "./r19Vars";
import { R19_VARS } from "@/components/r19/presentation";

/**
 * R19 Direction A — contrast law and value grammar, recomputed from the exact
 * values in r19Vars.ts (never a frozen number). Same approach as
 * scripts/tests/test_merah_putih_day_contrast.py: WCAG 2.x relative luminance,
 * text pairs at their floor, interactive boundaries at 3:1, and the decorative
 * lines pinned BELOW 3:1 so promoting one into interactive duty has to edit
 * this file on purpose.
 *
 * UNIFIED 2026-09-27 (gate B2 on PR #7508): most tokens are now spread
 * straight from `R19_VARS` (main's site-wide R19 shell) rather than
 * restated, and several aliases are deliberate `var(--other-key)`
 * references instead of copied literals — so this file's grammar check and
 * `resolve()` helper below follow one level of `var()` before measuring a
 * contrast pair, and a dedicated block asserts no shared key was quietly
 * given a different value than `R19_VARS` carries.
 */

const VARS = R19_DIRECTION_A_VARS as Record<string, string>;
const MAIN = R19_VARS as Record<string, string>;

function channel(c: number): number {
  const s = c / 255;
  return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
}

function relativeLuminance(hex: string): number {
  const h = hex.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function contrastRatio(fg: string, bg: string): number {
  const a = relativeLuminance(fg);
  const b = relativeLuminance(bg);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

const VAR_REF = /^var\((--[\w-]+)\)$/;

/** Follows a `var(--other-key)` alias to its literal, one hop at a time, so
 * a contrast pair can name either an inherited literal or a designated
 * alias interchangeably — the same tolerance the browser cascade gives it. */
function resolve(token: string, seen: Set<string> = new Set()): string {
  if (seen.has(token)) {
    throw new Error(`circular var() reference starting at ${token}`);
  }
  seen.add(token);
  const raw = VARS[token];
  if (raw === undefined) {
    throw new Error(`${token} is not defined in R19_DIRECTION_A_VARS`);
  }
  const m = VAR_REF.exec(raw);
  return m ? resolve(m[1], seen) : raw;
}

function hexOf(token: string): string {
  const value = resolve(token);
  if (!/^#[0-9A-Fa-f]{6}$/.test(value)) {
    throw new Error(`${token} does not resolve to a 6-digit hex: ${value}`);
  }
  return value;
}

type Row = [fg: string, bg: string, floor: number, duty: string];

const TEXT_PAIRS: Row[] = [
  ["--text-primary", "--surface-base", 7, "body ink on paper (AAA)"],
  ["--text-secondary", "--surface-base", 4.5, "muted ink on paper"],
  ["--text-on-accent", "--r19-copper", 4.5, "primary button label"],
  ["--r19-copper", "--surface-base", 4.5, "link text on paper"],
  ["--r19-structure", "--surface-base", 7, "structure on paper (AAA)"],
  ["--text-primary", "--surface-sunken", 7, "ink on wash (AAA)"],
  ["--text-primary", "--surface-raised", 7, "ink on sheet (AAA)"],
  ["--text-secondary", "--surface-raised", 4.5, "muted ink on sheet"],
  ["--r19-copper", "--surface-raised", 4.5, "link text on sheet"],
  [
    "--text-on-accent",
    "--r19-copper-hover",
    4.5,
    "primary button label, hover",
  ],
  ["--r19-ink-muted", "--r19-wash", 4.5, "disabled button label"],
  ["--footer-text", "--footer-bg", 4.5, "footer ink"],
];

const NON_TEXT_PAIRS: Row[] = [
  [
    "--r19-control-border",
    "--surface-base",
    3,
    "field / quiet button edge on paper",
  ],
  ["--r19-control-border", "--surface-raised", 3, "field edge on sheet"],
  ["--r19-structure", "--surface-raised", 3, "selected option edge"],
  ["--r19-copper", "--surface-base", 3, "focus ring"],
  [
    "--nav-icon-color",
    "--nav-icon-bg",
    3,
    "mobile nav toggle icon on kbli's opaque paper nav (gate B1, PR #7508)",
  ],
];

const DECORATIVE_PAIRS: Row[] = [
  [
    "--r19-line",
    "--surface-base",
    3,
    "hairline — never the sole boundary of a control",
  ],
  [
    "--border-strong",
    "--surface-base",
    3,
    "structural rule — controls read --r19-control-border",
  ],
];

function fmt(fg: string, bg: string): string {
  try {
    return contrastRatio(hexOf(fg), hexOf(bg)).toFixed(2);
  } catch {
    return "n/a";
  }
}

describe("R19 Direction A — WCAG contrast", () => {
  it.each(TEXT_PAIRS.map((r) => [...r, fmt(r[0], r[1])] as const))(
    "text %s on %s ≥ %s (%s) = %s:1",
    (fg, bg, floor) => {
      expect(contrastRatio(hexOf(fg), hexOf(bg))).toBeGreaterThanOrEqual(floor);
    },
  );

  it.each(NON_TEXT_PAIRS.map((r) => [...r, fmt(r[0], r[1])] as const))(
    "boundary %s on %s ≥ %s (%s) = %s:1",
    (fg, bg, floor) => {
      expect(contrastRatio(hexOf(fg), hexOf(bg))).toBeGreaterThanOrEqual(floor);
    },
  );

  it.each(DECORATIVE_PAIRS.map((r) => [...r, fmt(r[0], r[1])] as const))(
    "decorative %s on %s < %s (%s) = %s:1",
    (fg, bg, ceiling) => {
      expect(contrastRatio(hexOf(fg), hexOf(bg))).toBeLessThan(ceiling);
    },
  );
});

describe("R19 Direction A — inherits main's R19 shell verbatim", () => {
  it("restates no R19_VARS key at a different value (gate B2, PR #7508)", () => {
    for (const key of Object.keys(MAIN)) {
      expect(VARS[key], `${key} diverges from R19_VARS`).toBe(MAIN[key]);
    }
  });
});

describe("R19 Direction A — value grammar", () => {
  const FONT_ENTRIES = new Set(["--font-serif", "--font-sans"]);
  const HEX = /^#(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$/;
  const KEYWORD = /^[a-z]+$/;
  const LENGTH = /^\d+(?:\.\d+)?px$/;
  const SHADOW = /^(?:\d+(?:px)? ){3,4}#(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$/;
  const FONT_STACK =
    /^"R19 (?:Fraunces|Manrope)", [A-Za-z]+, (?:serif|sans-serif)$/;

  // Tokens that are DELIBERATE `var(--other-key)` aliases rather than
  // literals — the whole point of the 2026-09-27 unification (gate B2): a
  // shared meaning is spelled once, at the key it means, and every alias
  // just points at it, so it can never drift to a different number again.
  const ALIAS_TARGETS: Record<string, string> = {
    "--cta-primary-fg": "--text-on-accent",
    "--color-text-muted": "--text-secondary",
    "--color-border-subtle": "--border-subtle",
    "--footer-text": "--text-secondary",
    "--cta-bg": "--cta-primary-bg",
    "--tx-secondary": "--text-secondary",
    "--bz-accent": "--accent-funnel",
    "--text-link": "--accent-funnel",
    "--r19-ink-muted": "--text-secondary",
    "--nav-icon-color": "--text-primary",
    "--nav-icon-bg": "--surface-raised",
    "--nav-icon-border": "--border-subtle",
  };

  it.each(Object.entries(ALIAS_TARGETS))(
    "%s is a designated var(%s) alias, not a copied literal",
    (name, target) => {
      expect(VARS[name]).toBe(`var(${target})`);
      expect(
        VARS[target],
        `alias target ${target} must itself exist`,
      ).toBeDefined();
    },
  );

  // A key inherited verbatim from R19_VARS (unchanged, per the block above)
  // is main's own contract, not this file's — the literal-grammar check
  // below scopes to this file's OWN additions: a key MAIN does not carry,
  // or one this file deliberately re-declares (there are none of the
  // latter left; the block above enforces that every override is an alias).
  const NON_CUSTOM_PROPERTY_KEYS = new Set(["colorScheme"]);
  const OWN_ADDITIONS = Object.entries(VARS).filter(
    ([name]) =>
      !(name in ALIAS_TARGETS) &&
      !(name in MAIN) &&
      !NON_CUSTOM_PROPERTY_KEYS.has(name),
  );

  it.each(OWN_ADDITIONS)("%s = %s is a literal", (name, value) => {
    expect(name.startsWith("--")).toBe(true);
    expect(value).not.toMatch(/color-mix|rgba?\(|hsla?\(|calc\(/);
    if (FONT_ENTRIES.has(name)) {
      expect(value).toMatch(FONT_STACK);
      return;
    }
    expect(value).not.toMatch(/var\(/);
    expect(
      HEX.test(value) ||
        KEYWORD.test(value) ||
        LENGTH.test(value) ||
        SHADOW.test(value),
    ).toBe(true);
  });

  it("carries no other stray non-custom-property key", () => {
    const stray = Object.keys(VARS).filter(
      (k) => !k.startsWith("--") && !NON_CUSTOM_PROPERTY_KEYS.has(k),
    );
    expect(stray).toEqual([]);
  });

  it("exports the scope class the stylesheet hooks", () => {
    expect(R19_CLASS).toBe("r19-direction-a");
  });
});
