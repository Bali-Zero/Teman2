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
  lineControl: "#58626b", // token-lint-ok: the expected value this contract pins, not a style
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

/**
 * Values an earlier revision shipped and the frozen renders overruled. Kept so
 * the test can assert the correction is an improvement, never re-introduced.
 */
const SUPERSEDED = {
  lineControl: "#767c82", // token-lint-ok: the superseded value, asserted to be weaker
} as const;

/** A panel that follows the lifted success step, planted for the guilt case. */
const PLANTED_PANEL_MIX =
  "  --bz-panel: color-mix(in srgb, #253e33 40%, #f7f4ee);"; // token-lint-ok: planted violation for the guilt case, never rendered

/** Reds the alphabet forbids, used only to prove the detector is awake. */
const PLANTED_REDS = {
  tailwindDanger: "#b91c1c", // token-lint-ok: planted violation for the guilt case, never rendered
  legacyBzRed: "#d95f5a", // token-lint-ok: planted violation for the guilt case, never rendered
  neonRose: "#f43f5e", // token-lint-ok: planted violation for the guilt case, never rendered
  headerFallback: "#e45c5c", // token-lint-ok: planted violation for the guilt case, never rendered
  legacyNavy: "#060d14", // token-lint-ok: planted violation for the guilt case, never rendered
} as const;

/**
 * The K1c-bis rail's active-marker/group-label copper — a fifth copper step
 * alongside the four above, allowed here rather than duplicated with its
 * own detector so `findBannedReds` stays the single "is this a red" answer.
 */
const RAIL_RULE = "#ce8571"; // token-lint-ok: the expected value this contract pins, not a style

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
    RAIL_RULE,
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

/**
 * Pure detector: does this block's --bz-panel follow the theme's lifted
 * --state-success instead of holding the one forest value? An absent
 * declaration counts as drift — a panel that is not declared is not pinned.
 */
export function panelTracksSuccess(block: string): boolean {
  const match = block.match(/--bz-panel:\s*([^;]+);/);
  if (!match) return true;
  const value = match[1].trim();
  return (
    value.includes("var(--state-success)") || value.startsWith("color-mix(")
  );
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
      RAIL_RULE,
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

  it("the control boundary clears SC 1.4.11's 3:1 on paper, on a card and on the wash", () => {
    expect(contrast(R19.lineControl, R19.canvas)).toBeGreaterThanOrEqual(3);
    expect(contrast(R19.lineControl, R19.card)).toBeGreaterThanOrEqual(3);
    expect(contrast(R19.lineControl, R19.wash)).toBeGreaterThanOrEqual(3);
  });

  it("the ruled control boundary also clears text contrast, where the superseded one did not", () => {
    // The renders' value is the muted ink and reads 5.67:1 on paper; the one
    // DISPOSITION.md carried read 3.84:1 and cleared only the 3:1 floor.
    expect(contrast(R19.lineControl, R19.canvas)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(SUPERSEDED.lineControl, R19.canvas)).toBeLessThan(4.5);
    expect(R19.lineControl).not.toBe(SUPERSEDED.lineControl);
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

describe("kita R19 seam — the one forest surface", () => {
  // K1d gives /login its forest panel. It is the only filled forest in kita:
  // everywhere else forest is a WORD or a hairline, because "done" is a
  // meaning and not a wall.
  for (const theme of ["operative-light", "operative-dark"]) {
    it(`${theme}: --bz-panel is the forest and --bz-on-panel the paper`, () => {
      const block = themeBlock(theme);
      expect(block).toContain(`--bz-panel: ${R19.forest};`);
      expect(block).toContain(`--bz-on-panel: ${R19.canvas};`);
    });
  }

  it("does not follow --state-success into the dark (innocence)", () => {
    // The dark block lifts success through a paper mix so "done" stays legible
    // as TEXT. A lifted forest is a pale green wall, not a panel, so the panel
    // keeps the ONE value in both themes.
    expect(themeBlock("operative-dark")).toContain(
      "--state-success: color-mix(",
    );
    expect(panelTracksSuccess(themeBlock("operative-light"))).toBe(false);
    expect(panelTracksSuccess(themeBlock("operative-dark"))).toBe(false);
  });

  it("the panel-drift detector is awake (guilt)", () => {
    // Each of these is a way the panel could come to track the lifted step.
    expect(panelTracksSuccess("  --bz-panel: var(--state-success);")).toBe(
      true,
    );
    expect(panelTracksSuccess(PLANTED_PANEL_MIX)).toBe(true);
    // And a block that declares no panel at all is drift, not innocence.
    expect(panelTracksSuccess("  --bz-base: var(--bz-kita-canvas);")).toBe(
      true,
    );
  });

  it("paper on forest clears SC 1.4.3 with room (innocence)", () => {
    expect(contrast(R19.canvas, R19.forest)).toBeGreaterThanOrEqual(4.5);
  });

  it("ink on forest would have failed, which is why the panel carries paper (guilt)", () => {
    expect(contrast(R19.ink, R19.forest)).toBeLessThan(4.5);
  });
});

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

/**
 * K1c-bis rail tokens (SAETTA-R19K, unit C, "The rail (unit C only)"). The
 * workspace sidebar rail is now a fixed ink surface in BOTH themes — an
 * "invariant rail" — so this block pins the six alias-run declarations
 * verbatim plus the --bz-kita-rail source they read from, and the one
 * deliberate asymmetry between themes: --nav-edge, which repeats the
 * rail's own ink in light (the render has border-right:0 there, so an ink
 * line on an ink rail is invisible anyway) and becomes a paper hairline in
 * dark (the render draws a real edge). --nav-bg / --bz-kita-nav are
 * re-pinned unchanged here too — that pair is the Header.tsx paper
 * background, outside this window's perimeter, and this is the guard a
 * later window should trip if it ever folds it into the rail tokens.
 */
const RAIL_PAPER_ON_INK_COMPOSITE = "#c7c8c7"; // token-lint-ok: fusion/MEASURE.md's composite of paper-78% over the rail ink, not a style

describe("kita R19 rail (K1c-bis) — the seven rail declarations", () => {
  for (const theme of ["operative-light", "operative-dark"]) {
    const block = themeBlock(theme);

    it(`${theme}: pins --bz-kita-rail and --nav-rail-bg`, () => {
      expect(block).toContain(`--bz-kita-rail: ${R19.ink};`);
      expect(block).toContain("--nav-rail-bg: var(--bz-kita-rail);");
    });

    it(`${theme}: pins the rail foreground trio`, () => {
      expect(block).toContain("--nav-fg: #f7f4ee;");
      expect(block).toContain("--nav-fg-muted: rgba(247, 244, 238, 0.78);");
      expect(block).toContain("--nav-active-wash: rgba(247, 244, 238, 0.06);");
    });

    it(`${theme}: pins --nav-rule`, () => {
      expect(block).toContain(`--nav-rule: ${RAIL_RULE};`);
    });

    it(`${theme}: leaves --nav-bg on --bz-kita-nav, unchanged (the Header.tsx guard)`, () => {
      expect(block).toContain("--nav-bg: var(--bz-kita-nav);");
    });
  }

  it("the rail background is the same ink in both themes (the invariant rail)", () => {
    expect(themeBlock("operative-light")).toContain(
      `--bz-kita-rail: ${R19.ink};`,
    );
    expect(themeBlock("operative-dark")).toContain(
      `--bz-kita-rail: ${R19.ink};`,
    );
  });

  it("--nav-edge differs between themes, and only the dark one is a paper alpha", () => {
    expect(themeBlock("operative-light")).toContain(
      "--nav-edge: var(--bz-kita-rail);",
    );
    expect(themeBlock("operative-dark")).toContain(
      "--nav-edge: rgba(247, 244, 238, 0.14);",
    );
    // Innocence: light's --nav-edge is the rail's own ink, not a paper
    // alpha — the asymmetry is real, not a copy-paste of the dark value.
    expect(themeBlock("operative-light")).not.toContain(
      "--nav-edge: rgba(247, 244, 238",
    );
  });

  it("paper-78% composited over the rail ink clears 4.5:1, at the measured composite", () => {
    // fusion/MEASURE.md measured this composite at 8.48:1.
    expect(contrast(RAIL_PAPER_ON_INK_COMPOSITE, R19.ink)).toBeCloseTo(8.48, 1);
    expect(
      contrast(RAIL_PAPER_ON_INK_COMPOSITE, R19.ink),
    ).toBeGreaterThanOrEqual(4.5);
  });

  it("the copper rule on the rail ink clears 4.5:1", () => {
    // fusion/MEASURE.md measured this pair at 4.89:1.
    expect(contrast(RAIL_RULE, R19.ink)).toBeCloseTo(4.89, 1);
    expect(contrast(RAIL_RULE, R19.ink)).toBeGreaterThanOrEqual(4.5);
  });
});

/** Flatten a translucent paint over an opaque ground, so a STATE can be measured. */
export function composite(fg: string, alpha: number, ground: string): string {
  const mix = (i: number) =>
    Math.round(
      alpha * parseInt(fg.slice(i, i + 2), 16) +
        (1 - alpha) * parseInt(ground.slice(i, i + 2), 16),
    )
      .toString(16)
      .padStart(2, "0");
  return "#" + mix(1) + mix(3) + mix(5);
}

/**
 * The rail's STATES, not just its resting surface. An adversarial review of
 * K1c-bis found both defects below on a rail whose resting contrast was
 * already green — a contrast suite that only measures the ground a token
 * sits on when nothing is happening cannot see either of them.
 */
describe("kita R19 rail (K1c-bis) — hover and focus states", () => {
  const ACTIVE_WASH = composite(R19.canvas, 0.06, R19.ink);

  it("the composite helper is awake (guilt and innocence)", () => {
    // Fully opaque returns the paint; fully transparent returns the ground.
    expect(composite(R19.canvas, 1, R19.ink)).toBe(R19.canvas);
    expect(composite(R19.canvas, 0, R19.ink)).toBe(R19.ink);
    // And a 6% paper wash moves the ink measurably without becoming paper.
    expect(ACTIVE_WASH).not.toBe(R19.ink);
    expect(contrast(ACTIVE_WASH, R19.ink)).toBeLessThan(1.2);
  });

  it("the focus ring reads --nav-rule, because --border-focus fails on the rail", () => {
    // --border-focus is the paper-ground copper. SC 1.4.11 asks 3:1 of a
    // focus indicator, and on the ink rail this one does not clear it — that
    // failure is the whole reason AppSidebar's workspace branch overrides the
    // ring colour rather than only its offset.
    expect(contrast(R19.copper, R19.ink)).toBeLessThan(3);
    // The cure, measured: the rail's own copper.
    expect(contrast(RAIL_RULE, R19.ink)).toBeGreaterThanOrEqual(3);
  });

  it("the rail copper does NOT clear 4.5:1 once the hover wash is under it", () => {
    // Which is why the row badge lifts to paper on hover instead of staying
    // copper on a ground that moved. Guilt for that rule, stated as a number.
    expect(contrast(RAIL_RULE, ACTIVE_WASH)).toBeLessThan(4.5);
  });

  it("paper at 100% and at 78% both clear 4.5:1 on the hover wash (the cure)", () => {
    expect(contrast(R19.canvas, ACTIVE_WASH)).toBeGreaterThanOrEqual(4.5);
    expect(
      contrast(RAIL_PAPER_ON_INK_COMPOSITE, ACTIVE_WASH),
    ).toBeGreaterThanOrEqual(4.5);
  });
});
