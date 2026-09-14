import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * concept-K "SIAP" seam contract (SAETTA-R19K / K1).
 *
 * kita-theme.contract.test.ts pins the --bz-kita-* INDIRECTION (the six alias
 * declarations). This file pins the VALUES behind it: the R19 alphabet —
 * paper, ink, copper, forest, slate, muted — in both themes, and the two
 * rules the concept calls laws: no red anywhere on kita, and Fraunces as the
 * serif face.
 *
 * Guilt and innocence (cicatrix-superscar #3): `findBannedReds` is a pure
 * function tested against a planted #b91c1c as well as against the real
 * blocks, so a green result means the detector works, not that it is asleep.
 */

const globalsCss = readFileSync(
  join(__dirname, "..", "..", "globals.css"),
  "utf8",
);

function themeBlock(theme: string): string {
  const match = globalsCss.match(
    new RegExp(
      `\\[data-theme="${theme}"\\]\\[data-product="kita"\\]\\s*\\{([\\s\\S]*?)\\n\\}`,
    ),
  );
  if (!match) throw new Error(`kita ${theme} block is absent from globals.css`);
  return match[1];
}

/**
 * A hex is "red" when its red channel dominates both others by a wide margin
 * AND it is not one of the two copper steps the R19 alphabet allows. Copper
 * #a44b36 and #c46a52 are warm but carry substantial green and blue; the
 * reds this catches are the Tailwind/legacy danger family (#b91c1c, #dc2626,
 * #d95f5a, #f43f5e, #e45c5c).
 */
export function findBannedReds(block: string): string[] {
  const ALLOWED = new Set([
    "#a44b36", // copper, light
    "#c46a52", // copper text, dark
    "#8f4130", // copper hover, light
    "#d07e68", // copper hover, dark
  ]);
  const found: string[] = [];
  for (const hex of block.match(/#[0-9a-fA-F]{6}\b/g) ?? []) {
    const lower = hex.toLowerCase();
    if (ALLOWED.has(lower)) continue;
    const r = parseInt(lower.slice(1, 3), 16);
    const g = parseInt(lower.slice(3, 5), 16);
    const b = parseInt(lower.slice(5, 7), 16);
    if (r > 120 && r - g > 60 && r - b > 60) found.push(lower);
  }
  return found;
}

describe("kita R19 seam — light", () => {
  const block = themeBlock("operative-light");

  it("paints R19 paper and ink", () => {
    expect(block).toContain("--bz-kita-canvas: #f7f4ee;");
    expect(block).toContain("--bz-kita-card: #fffcf7;");
    expect(block).toContain("--bz-kita-wash: #eae3d8;");
    expect(block).toContain("--tx-primary: #1d2c3b;");
    expect(block).toContain("--tx-secondary: #58626b;");
    expect(block).toContain("--bz-border: #dad8d1;");
  });

  it("carries the four meanings: copper, forest, slate, warning", () => {
    expect(block).toContain("--bz-copper: #a44b36;");
    expect(block).toContain("--state-success: #253e33;");
    expect(block).toContain("--state-info: #233d52;");
    expect(block).toContain("--state-warning: #8a5a2b;");
  });

  it("re-aliases danger to copper and neon-purple to slate", () => {
    expect(block).toContain("--state-danger: #a44b36;");
    expect(block).toContain("--bz-red: #a44b36;");
    expect(block).toContain("--bz-neon-purple: #233d52;");
  });

  it("gives a control boundary its own line token", () => {
    expect(block).toContain("--line-control: #767c82;");
  });

  it("selects Fraunces and Manrope", () => {
    expect(block).toContain(
      '--font-serif: "Fraunces", ui-serif, Georgia, serif;',
    );
    expect(block).toContain(
      '--font-sans: "Manrope", ui-sans-serif, system-ui, sans-serif;',
    );
  });

  it("has no red", () => {
    expect(findBannedReds(block)).toEqual([]);
  });
});

describe("kita R19 seam — dark", () => {
  const block = themeBlock("operative-dark");

  it("exists and paints the ink ground", () => {
    expect(block).toContain("--bz-kita-canvas: #121016;");
    expect(block).toContain("--bz-kita-card: #1a1a1f;");
    expect(block).toContain("--tx-primary: #f7f4ee;");
  });

  it("lifts copper for text and keeps danger copper", () => {
    expect(block).toContain("--bz-copper-text: #c46a52;");
    expect(block).toContain("--state-danger: #c46a52;");
  });

  it("keeps the same six kita aliases as the light block", () => {
    expect(block).toContain("--bz-base: var(--bz-kita-canvas);");
    expect(block).toContain("--background: var(--bz-kita-canvas);");
    expect(block).toContain("--kbli-bg-base: var(--bz-kita-canvas);");
    expect(block).toContain("--bz-card: var(--bz-kita-card);");
    expect(block).toContain("--bz-card-hover: var(--bz-kita-card-hover);");
    expect(block).toContain("--nav-bg: var(--bz-kita-nav);");
  });

  it("has no red", () => {
    expect(findBannedReds(block)).toEqual([]);
  });
});

describe("the no-red detector is awake (guilt)", () => {
  it("catches a planted danger red", () => {
    expect(findBannedReds("  --state-danger: #b91c1c;\n")).toEqual(["#b91c1c"]);
  });

  it("catches the legacy --bz-red and the neon rose", () => {
    expect(findBannedReds("#d95f5a #f43f5e #e45c5c")).toEqual([
      "#d95f5a",
      "#f43f5e",
      "#e45c5c",
    ]);
  });

  it("does not accuse the copper steps (innocence)", () => {
    expect(
      findBannedReds("#a44b36 #c46a52 #8f4130 #d07e68 #8a5a2b #253e33 #233d52"),
    ).toEqual([]);
  });
});

/**
 * WCAG 2.1 relative luminance, so the contrast claims in the globals.css
 * comment are computed rather than asserted. Pure, and exercised below on a
 * pair that is KNOWN to fail, so a green run means the maths is awake.
 */
export function contrast(a: string, b: string): number {
  const lum = (hex: string) => {
    const ch = [1, 3, 5].map((i) => {
      const v = parseInt(hex.slice(i, i + 2), 16) / 255;
      return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2];
  };
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/**
 * A token a consumer paints WITH — a border, a ring, a hover fill — must not
 * resolve to `transparent`, or the consumer draws nothing. `--bz-glass-rim`
 * and `--bz-glass-highlight` are read as `1px solid`, `ring-1` and
 * `hover:bg-` in five places under apps/mouth/src, so on kita they map onto
 * the R19 line and the R19 wash instead of being erased.
 */
export function findErasedPaintTokens(block: string): string[] {
  const PAINTED = [
    "--bz-glass-rim",
    "--bz-glass-highlight",
    "--glass-rim",
    "--glass-highlight",
    "--bz-border",
    "--bz-line",
  ];
  return PAINTED.filter((name) =>
    new RegExp(`${name}:\\s*transparent\\s*;`).test(block),
  );
}

describe("kita R19 seam — tokens a consumer paints with", () => {
  for (const theme of ["operative-light", "operative-dark"]) {
    const block = themeBlock(theme);

    it(`${theme}: the glass pair maps onto the R19 line and wash, not onto nothing`, () => {
      expect(block).toContain("--bz-glass-highlight: var(--bz-kita-wash);");
      expect(block).toContain("--glass-highlight: var(--bz-kita-wash);");
      expect(findErasedPaintTokens(block)).toEqual([]);
    });

    it(`${theme}: --bz-navy-900 is the on-accent ink, not a navy`, () => {
      // Its one consumer, hr/employees/page.tsx:469, paints it ON the copper
      // fill. K4 removes the fill; until then the alias keeps it readable.
      expect(block).toContain("--bz-navy-900: var(--bz-on-warm);");
    });
  }

  it("the erased-paint detector is awake (guilt)", () => {
    expect(
      findErasedPaintTokens("  --glass-highlight: transparent;\n"),
    ).toEqual(["--glass-highlight"]);
    expect(
      findErasedPaintTokens(
        "  --bz-glass-rim: transparent;\n  --bz-border: transparent;\n",
      ),
    ).toEqual(["--bz-glass-rim", "--bz-border"]);
  });

  it("does not accuse a token that actually paints (innocence)", () => {
    expect(
      findErasedPaintTokens(
        "  --bz-glass-rim: #dad8d1;\n  --bz-glass-highlight: var(--bz-kita-wash);\n",
      ),
    ).toEqual([]);
  });
});

describe("kita R19 seam — on-accent ink clears SC 1.4.3", () => {
  it("light: paper on copper", () => {
    // --bz-on-warm #fffcf7 on --bz-accent #a44b36
    expect(contrast("#fffcf7", "#a44b36")).toBeGreaterThanOrEqual(4.5);
  });

  it("dark: ink on lifted copper", () => {
    // --bz-on-warm #121016 on --bz-accent #c46a52
    expect(contrast("#121016", "#c46a52")).toBeGreaterThanOrEqual(4.5);
  });

  it("the ratio the alias cures would have failed (guilt)", () => {
    // packages/core --bz-navy-900 #060d14 on R19 copper: the regression that
    // --bz-navy-900: var(--bz-on-warm) exists to prevent.
    expect(contrast("#060d14", "#a44b36")).toBeLessThan(4.5);
  });

  it("body ink on paper clears SC 1.4.3 with room (innocence)", () => {
    expect(contrast("#1d2c3b", "#f7f4ee")).toBeGreaterThan(12);
    expect(contrast("#58626b", "#f7f4ee")).toBeGreaterThanOrEqual(4.5);
  });
});
