import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
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

  // gate B3, PR #7508 round 3: R19_VARS carries no `--foreground` key at
  // all, so this file must restate it — as a LITERAL synced to
  // `--text-primary`, not a `var()` alias (kbli-theme.css's `.kbli-paper`
  // block, BRIEF-v2 R-1 §3.4, names this exact indirection "the r19Vars.ts
  // alias trap": an alias declared at :root re-resolving to the dark
  // default instead of the paper value it should follow).
  it("--foreground is a literal synced to --text-primary, not a var() alias (gate B3, PR #7508)", () => {
    expect(VARS["--foreground"]).toBe(MAIN["--text-primary"]);
    expect(VARS["--foreground"]).not.toMatch(/var\(/);
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
    // B2 residual (gate PR #7508 round 3): these six used to copy main's
    // values under a different name as a literal — converted to var()
    // references so they can never drift again, same as the block above.
    "--surface-base-solid": "--surface-base",
    "--surface-sunken": "--r19-wash",
    "--surface-deep": "--surface-sunken",
    "--bz-elevated": "--surface-raised",
    "--r19-structure": "--r19-slate",
  };

  // `--r19-focus` is the seventh B2 residual, but its value is a composite
  // shadow string with the alias embedded (`0 0 0 3px var(--accent-funnel)`),
  // not a bare `var(--x)` — ALIAS_TARGETS' exact-string check doesn't fit it,
  // so it gets its own grammar and target-existence assertion.
  const SHADOW_WITH_VAR = /^(?:\d+(?:px)? ){3,4}var\((--[\w-]+)\)$/;

  it("--r19-focus is a shadow with a var() alias, not a copied literal (gate B2, PR #7508)", () => {
    const value = VARS["--r19-focus"];
    const m = SHADOW_WITH_VAR.exec(value);
    expect(
      m,
      `--r19-focus does not match the shadow-with-var() grammar: ${value}`,
    ).not.toBeNull();
    const target = m![1];
    expect(
      VARS[target],
      `alias target ${target} must itself exist`,
    ).toBeDefined();
  });

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
  // `--r19-focus` has its own dedicated composite-shadow-with-var() test
  // above (gate B2 residual round 3) rather than the plain-literal grammar
  // below, which forbids any `var(` occurrence.
  const COMPOSITE_ALIASES = new Set(["--r19-focus"]);
  const OWN_ADDITIONS = Object.entries(VARS).filter(
    ([name]) =>
      !(name in ALIAS_TARGETS) &&
      !(name in MAIN) &&
      !NON_CUSTOM_PROPERTY_KEYS.has(name) &&
      !COMPOSITE_ALIASES.has(name),
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

describe("R19 Direction A — coverage of var(--x) reads on kbli routes (gate B3, PR #7508)", () => {
  // Rebuilds the exact regression class the gate found: a kbli component
  // reading `var(--foreground)` directly, where `--foreground` had quietly
  // stopped being part of the set this wrapper actually supplies. Rather
  // than freezing a snapshot of today's files, this walks the real kbli
  // surface tree plus the shared nav it renders through, so a FUTURE
  // component that starts reading an undefined custom property fails here
  // instead of on a live preview.
  const HERE = path.dirname(fileURLToPath(import.meta.url));
  const SRC_DIR = path.resolve(HERE, "..", "..");

  function collectFiles(dir: string, exts: string[]): string[] {
    const out: string[] = [];
    const stack = [dir];
    while (stack.length > 0) {
      const current = stack.pop()!;
      let entries: fs.Dirent[];
      try {
        entries = fs.readdirSync(current, { withFileTypes: true });
      } catch {
        continue;
      }
      for (const entry of entries) {
        const full = path.join(current, entry.name);
        if (entry.isDirectory()) {
          stack.push(full);
        } else if (exts.some((ext) => entry.name.endsWith(ext))) {
          out.push(full);
        }
      }
    }
    return out;
  }

  const KBLI_SURFACE_FILES = [
    ...collectFiles(path.join(SRC_DIR, "app", "kbli"), [".ts", ".tsx"]),
    ...collectFiles(path.join(SRC_DIR, "components", "kbli"), [".ts", ".tsx"]),
    path.join(SRC_DIR, "app", "v2", "_components", "MobileNav.tsx"),
  ];

  // Tokens legitimately read by kbli components WITHOUT being part of the
  // R19 Direction A set: kbli's own separate `--kbli-*` theme layer
  // (deliberately out of scope, gate rework rounds 1-2) by prefix, plus a
  // short, named list of globals.css base tokens that are supplied
  // app-wide regardless of the r19 wrapper and were NOT among the gate's
  // findings (only bare `--foreground` was cited as broken, never these).
  const KNOWN_EXTERNAL_TOKENS = new Set([
    "--foreground-muted",
    "--foreground-secondary",
    "--border",
    "--border-default",
    "--accent-whatsapp-ink",
    "--public-header-height",
  ]);

  function isKnownExternal(name: string): boolean {
    return name.startsWith("--kbli-") || KNOWN_EXTERNAL_TOKENS.has(name);
  }

  it("scans a non-trivial kbli surface (sanity floor on the file walk itself)", () => {
    expect(KBLI_SURFACE_FILES.length).toBeGreaterThan(10);
  });

  it("every non-external var(--x) read across the kbli surface exists in R19_DIRECTION_A_VARS", () => {
    const VAR_READ = /var\((--[\w-]+)/g;
    const missing: Array<{ name: string; file: string }> = [];
    for (const file of KBLI_SURFACE_FILES) {
      const content = fs.readFileSync(file, "utf8");
      const names = new Set<string>();
      let m: RegExpExecArray | null;
      while ((m = VAR_READ.exec(content))) {
        names.add(m[1]);
      }
      for (const name of names) {
        if (isKnownExternal(name)) continue;
        if (!(name in VARS)) {
          missing.push({ name, file: path.relative(SRC_DIR, file) });
        }
      }
    }
    expect(missing).toEqual([]);
  });
});
