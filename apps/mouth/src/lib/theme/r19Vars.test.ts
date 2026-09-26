import { describe, expect, it } from "vitest";
import { R19_CLASS, R19_DIRECTION_A_VARS } from "./r19Vars";

/**
 * R19 Direction A — contrast law and value grammar, recomputed from the exact
 * values in r19Vars.ts (never a frozen number). Same approach as
 * scripts/tests/test_merah_putih_day_contrast.py: WCAG 2.x relative luminance,
 * text pairs at their floor, interactive boundaries at 3:1, and the decorative
 * lines pinned BELOW 3:1 so promoting one into interactive duty has to edit
 * this file on purpose.
 */

const VARS = R19_DIRECTION_A_VARS as Record<string, string>;

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

function hexOf(token: string): string {
  const value = VARS[token];
  if (!/^#[0-9A-Fa-f]{6}$/.test(value ?? "")) {
    throw new Error(`${token} is not a 6-digit hex: ${String(value)}`);
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

describe("R19 Direction A — value grammar", () => {
  const FONT_ENTRIES = new Set(["--font-serif", "--font-sans"]);
  const HEX = /^#(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$/;
  const KEYWORD = /^[a-z]+$/;
  const LENGTH = /^\d+(?:\.\d+)?px$/;
  const SHADOW = /^(?:\d+(?:px)? ){3,4}#(?:[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$/;
  const FONT_STACK =
    /^var\(--font-r19-(?:serif|sans)\), "[A-Za-z ]+", [A-Za-z ]+, (?:serif|sans-serif)$/;

  it.each(Object.entries(VARS))("%s = %s is a literal", (name, value) => {
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

  it("restates the :root aliases the day set restates (var() resolves at the declaring element)", () => {
    expect(VARS["--color-text-muted"]).toBe(VARS["--text-secondary"]);
    expect(VARS["--color-border-subtle"]).toBe(VARS["--border-subtle"]);
    expect(VARS["--cta-bg"]).toBe(VARS["--cta-primary-bg"]);
    expect(VARS["--footer-text"]).toBe(VARS["--text-tertiary"]);
  });

  it("exports the scope class the stylesheet hooks", () => {
    expect(R19_CLASS).toBe("r19-direction-a");
  });
});
