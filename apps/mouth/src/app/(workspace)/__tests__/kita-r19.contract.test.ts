import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * concept-K "SIAP" seam contract (SAETTA-R19K / K1).
 *
 * kita-theme.contract.test.ts pins the --bz-kita-* INDIRECTION (the six alias
 * declarations). This file pins the VALUES behind it: the R19 alphabet —
 * paper, ink, copper, forest, slate, muted — in both themes, and the rules
 * the concept calls laws: no red anywhere on kita, Fraunces as the serif
 * face, nothing a consumer paints with erased to `transparent`, and on-accent
 * ink that clears SC 1.4.3.
 *
 * Guilt and innocence (cicatrix-superscar #3): every detector below is a pure
 * function exercised against a planted violation as well as against the real
 * blocks, so a green result means the detector works, not that it is asleep.
 *
 * Why the literals live in R19 rather than in the assertions: this file is
 * under a token-lint scoped surface, and a contract test that pins VALUES
 * cannot express them as token references without asserting nothing. Hoisting
 * them into one reviewed block keeps the exemption to a single place.
 */
const R19 = {
  canvas: "#f7f4ee", // token-lint-ok: the expected value this contract pins, not a style
  card: "#fffcf7", // token-lint-ok: the expected value this contract pins, not a style
  wash: "#eae3d8", // token-lint-ok: the expected value this contract pins, not a style
  ink: "#1d2c3b", // token-lint-ok: the expected value this contract pins, not a style
  muted: "#58626b", // token-lint-ok: the expected value this contract pins, not a style
  line: "#dad8d1", // token-lint-ok: the expected value this contract pins, not a style
  lineControl: "#767c82", // token-lint-ok: the expected value this contract pins, not a style
  copper: "#a44b36", // token-lint-ok: the expected value this contract pins, not a style
  copperHover: "#8f4130", // token-lint-ok: the expected value this contract pins, not a style
  forest: "#253e33", // token-lint-ok: the expected value this contract pins, not a style
  slate: "#233d52", // token-lint-ok: the expected value this contract pins, not a style
  warning: "#8a5a2b", // token-lint-ok: the expected value this contract pins, not a style
  inkGround: "#121016", // token-lint-ok: the expected value this contract pins, not a style
  cardDark: "#1a1a1f", // token-lint-ok: the expected value this contract pins, not a style
  copperText: "#c46a52", // token-lint-ok: the expected value this contract pins, not a style
  copperHoverDark: "#d07e68", // token-lint-ok: the expected value this contract pins, not a style
} as const;

/** Reds the alphabet forbids, used only to prove the detector is awake. */
const PLANTED_REDS = {
  tailwindDanger: "#b91c1c", // token-lint-ok: planted violation for the guilt case, never rendered
  legacyBzRed: "#d95f5a", // token-lint-ok: planted violation for the guilt case, never rendered
  neonRose: "#f43f5e", // token-lint-ok: planted violation for the guilt case, never rendered
  headerFallback: "#e45c5c", // token-lint-ok: planted violation for the guilt case, never rendered
  legacyNavy: "#060d14", // token-lint-ok: planted violation for the guilt case, never rendered
} as const;

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
 * AND it is not one of the copper steps the R19 alphabet allows. Copper is
 * warm but carries substantial green and blue; the reds this catches are the
 * Tailwind and legacy danger family.
 */
export function findBannedReds(block: string): string[] {
  const ALLOWED = new Set<string>([
    R19.copper,
    R19.copperText,
    R19.copperHover,
    R19.copperHoverDark,
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

/**
 * A token a consumer paints WITH — a border, a ring, a hover fill — must not
 * resolve to `transparent`, or the consumer draws nothing. The glass pair is
 * read as `1px solid`, `ring-1` and `hover:bg-` in five files under
 * apps/mouth/src, so on kita they map onto the R19 line and wash.
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

/** WCAG 2.1 relative-luminance contrast, so the ratios are computed. */
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

describe("kita R19 seam — light", () => {
  const block = themeBlock("operative-light");

  it("paints R19 paper and ink", () => {
    expect(block).toContain(`--bz-kita-canvas: ${R19.canvas};`);
    expect(block).toContain(`--bz-kita-card: ${R19.card};`);
    expect(block).toContain(`--bz-kita-wash: ${R19.wash};`);
    expect(block).toContain(`--tx-primary: ${R19.ink};`);
    expect(block).toContain(`--tx-secondary: ${R19.muted};`);
    expect(block).toContain(`--bz-border: ${R19.line};`);
  });

  it("carries the four meanings: copper, forest, slate, warning", () => {
    expect(block).toContain(`--bz-copper: ${R19.copper};`);
    expect(block).toContain(`--state-success: ${R19.forest};`);
    expect(block).toContain(`--state-info: ${R19.slate};`);
    expect(block).toContain(`--state-warning: ${R19.warning};`);
  });

  it("re-aliases danger to copper and neon-purple to slate", () => {
    expect(block).toContain(`--state-danger: ${R19.copper};`);
    expect(block).toContain(`--bz-red: ${R19.copper};`);
    expect(block).toContain(`--bz-neon-purple: ${R19.slate};`);
  });

  it("gives a control boundary its own line token", () => {
    expect(block).toContain(`--line-control: ${R19.lineControl};`);
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
    expect(block).toContain(`--bz-kita-canvas: ${R19.inkGround};`);
    expect(block).toContain(`--bz-kita-card: ${R19.cardDark};`);
    expect(block).toContain(`--tx-primary: ${R19.canvas};`);
  });

  it("lifts copper for text and keeps danger copper", () => {
    expect(block).toContain(`--bz-copper-text: ${R19.copperText};`);
    expect(block).toContain(`--state-danger: ${R19.copperText};`);
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
    expect(
      findBannedReds(`  --state-danger: ${PLANTED_REDS.tailwindDanger};\n`),
    ).toEqual([PLANTED_REDS.tailwindDanger]);
  });

  it("catches the legacy --bz-red, the neon rose and the header fallback", () => {
    const planted = [
      PLANTED_REDS.legacyBzRed,
      PLANTED_REDS.neonRose,
      PLANTED_REDS.headerFallback,
    ];
    expect(findBannedReds(planted.join(" "))).toEqual(planted);
  });

  it("does not accuse the copper steps (innocence)", () => {
    const innocent = [
      R19.copper,
      R19.copperText,
      R19.copperHover,
      R19.copperHoverDark,
      R19.warning,
      R19.forest,
      R19.slate,
    ];
    expect(findBannedReds(innocent.join(" "))).toEqual([]);
  });
});

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
        `  --bz-glass-rim: ${R19.line};\n  --bz-glass-highlight: var(--bz-kita-wash);\n`,
      ),
    ).toEqual([]);
  });
});

describe("kita R19 seam — on-accent ink clears SC 1.4.3", () => {
  it("light: paper on copper", () => {
    expect(contrast(R19.card, R19.copper)).toBeGreaterThanOrEqual(4.5);
  });

  it("dark: ink on lifted copper", () => {
    expect(contrast(R19.inkGround, R19.copperText)).toBeGreaterThanOrEqual(4.5);
  });

  it("the ratio the --bz-navy-900 alias cures would have failed (guilt)", () => {
    expect(contrast(PLANTED_REDS.legacyNavy, R19.copper)).toBeLessThan(4.5);
  });

  it("body ink on paper clears SC 1.4.3 with room (innocence)", () => {
    expect(contrast(R19.ink, R19.canvas)).toBeGreaterThan(12);
    expect(contrast(R19.muted, R19.canvas)).toBeGreaterThanOrEqual(4.5);
  });

  it("the control boundary clears SC 1.4.11's 3:1 on paper and on a card", () => {
    expect(contrast(R19.lineControl, R19.canvas)).toBeGreaterThanOrEqual(3);
    expect(contrast(R19.lineControl, R19.card)).toBeGreaterThanOrEqual(3);
  });
});

/**
 * Values the kita seam must NOT redeclare, because redeclaring them lowers a
 * ratio that is already live. Kept as a list so a later window that adds one
 * back has to argue with a test rather than with a comment.
 */
const INHERITED = {
  pureBlack: "#000000", // token-lint-ok: the inherited value this contract protects, not a style
} as const;

/** Names the block declares — a redeclaration is what this detects. */
export function findRedeclared(block: string, names: string[]): string[] {
  return names.filter((name) =>
    new RegExp(`^\\s*${name}\\s*:`, "m").test(block),
  );
}

describe("kita R19 seam — what the block refuses to redeclare", () => {
  for (const theme of ["operative-light", "operative-dark"]) {
    it(`${theme}: leaves --bz-text-pure resolving through packages/core`, () => {
      // clients/page.tsx:806 paints it as the label ON the copper fill of the
      // active "assigned to me" filter. Its inherited value is black, which
      // reads 3.64:1 there; R19 ink would read 2.47:1. Both are under SC
      // 1.4.3 and K3 removes the fill, but the seam must not make it worse.
      expect(findRedeclared(themeBlock(theme), ["--bz-text-pure"])).toEqual([]);
    });
  }

  it("black on copper beats R19 ink on copper, which is why it stays (the reason)", () => {
    expect(contrast(INHERITED.pureBlack, R19.copper)).toBeGreaterThan(
      contrast(R19.ink, R19.copper),
    );
  });

  it("the redeclaration detector is awake (guilt)", () => {
    expect(
      findRedeclared(`  --bz-text-pure: ${R19.ink};\n`, ["--bz-text-pure"]),
    ).toEqual(["--bz-text-pure"]);
  });

  it("does not fire on a mere mention in a comment (innocence)", () => {
    expect(
      findRedeclared(
        "  /* --bz-text-pure is deliberately not redeclared */\n",
        ["--bz-text-pure"],
      ),
    ).toEqual([]);
  });
});
