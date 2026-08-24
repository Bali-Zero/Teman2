import { readFileSync, readdirSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

const ARTICLE = join(
  __dirname,
  "(blog)",
  "[category]",
  "[slug]",
  "ArticleClient.tsx",
);
const BOOK = join(__dirname, "(book)", "book", "BookPage.tsx");
const SERVICES = join(__dirname, "(blog)", "services", "page.tsx");

// __dirname is apps/mouth/src/app — four levels up is the repo root.
const REPO_ROOT = join(__dirname, "..", "..", "..", "..");
const SEMANTIC_TOKENS = join(
  REPO_ROOT,
  "packages",
  "core",
  "tokens",
  "semantic.css",
);

const OPENING_TAG_RE = /<[A-Za-z][^>]*>/gs;
const WHATSAPP_FILL_RE =
  /(?:bg-\[#25d366\](?:\/\d+)?|bg-\[#22c55e\](?:\/\d+)?|background(?:Color)?\s*:\s*["']?(?:#25d366|#22c55e|var\(--accent-whatsapp\b))/i;
const UNSAFE_INK_RE =
  /(?:\btext-(?:white|slate-(?:50|100|200)|gray-(?:50|100|200)|zinc-(?:50|100|200)|neutral-(?:50|100|200)|stone-(?:50|100|200))(?:\/\d+)?\b|\bcolor\s*:\s*["']?(?:#(?:fff(?:fff)?|[ef][0-9a-f]{5})\b|var\(--text-on-accent\b))/i;

/** Return JSX opening tags that put white/near-white ink on WhatsApp green. */
function unsafeWhatsAppPairs(source: string): string[] {
  return [...source.matchAll(OPENING_TAG_RE)]
    .map(([tag]) => tag)
    .filter((tag) => WHATSAPP_FILL_RE.test(tag) && UNSAFE_INK_RE.test(tag));
}

// ---------------------------------------------------------------------------
// Repo sweep — the actual guard. Pinning three named files (the pre-sweep
// version of this guard) can only ever re-verify surfaces someone already
// fixed; it can never catch the NEXT surface that pairs the WhatsApp fill
// with light ink. Every source file under the two roots that can plausibly
// carry a Tailwind class or inline style is swept instead.
// ---------------------------------------------------------------------------

const SWEEP_ROOTS = [
  join(REPO_ROOT, "apps", "mouth", "src"),
  join(REPO_ROOT, "packages", "core"),
];
const SWEEP_EXCLUDED_DIRS = new Set(["node_modules", ".next", "dist", "build"]);
const SWEEP_EXTENSION_RE = /\.(?:tsx?|jsx|css)$/;
const TEST_FILE_RE = /\.(?:test|spec)\.[^./]+$/;

/**
 * The two deliberately-different cured sites. Both already pair WhatsApp
 * green with dark ink at a safe contrast ratio, but through their OWN local
 * value rather than the shared `--accent-whatsapp-ink` token:
 *  - oracle.css defines a route-scoped `--oracle-whatsapp-fg: #0d3a1f`
 *    (measured ~6.45:1 — this is in fact the origin the shared token cites).
 *  - NavWhatsAppCTA.tsx pairs the fill with a literal `#06301a` (measured
 *    ~7.5:1 per its own inline comment).
 * Neither currently trips the pairing regex (the fill/ink values here don't
 * match WHATSAPP_FILL_RE/UNSAFE_INK_RE in the first place), but they are
 * listed explicitly so the sweep documents the exemption instead of passing
 * on them by regex coincidence.
 */
const SWEEP_ALLOWLIST = new Set([
  join(
    REPO_ROOT,
    "apps",
    "mouth",
    "src",
    "app",
    "(visa-oracle)",
    "visa-oracle",
    "oracle.css",
  ),
  join(
    REPO_ROOT,
    "apps",
    "mouth",
    "src",
    "app",
    "v2",
    "_components",
    "NavWhatsAppCTA.tsx",
  ),
]);

function sweepFiles(dir: string, acc: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (SWEEP_EXCLUDED_DIRS.has(entry.name)) continue;
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      sweepFiles(full, acc);
    } else if (
      SWEEP_EXTENSION_RE.test(entry.name) &&
      !TEST_FILE_RE.test(entry.name)
    ) {
      acc.push(full);
    }
  }
  return acc;
}

const SWEPT_FILES = SWEEP_ROOTS.flatMap((root) => sweepFiles(root)).filter(
  (file) => !SWEEP_ALLOWLIST.has(file),
);

describe("WhatsApp accent ink guard", () => {
  it("GUILT: rejects literal and token WhatsApp fills with light ink", () => {
    const guilty = [
      '<a className="bg-[#25D366] text-white">Chat</a>',
      '<a style={{ background: "var(--accent-whatsapp)", color: "var(--text-on-accent)" }}>Chat</a>',
      '<a style={{ backgroundColor: "#25d366", color: "#f8fafc" }}>Chat</a>',
    ].join("\n");

    expect(unsafeWhatsAppPairs(guilty)).toHaveLength(3);
  });

  it("INNOCENCE: accepts the dark ink token and non-fill green decoration", () => {
    const innocent = [
      '<a className="bg-[#25D366] text-[var(--accent-whatsapp-ink)]">Chat</a>',
      '<a style={{ background: "var(--accent-whatsapp)", color: "var(--accent-whatsapp-ink)" }}>Chat</a>',
      '<span className="text-[#25D366] border-[#25D366]">✓</span>',
      '<span className="text-[#22c55e] border-[#22c55e]">✓</span>',
    ].join("\n");

    expect(unsafeWhatsAppPairs(innocent)).toEqual([]);
  });

  it("the ratified semantic token retains its measured origin", () => {
    const tokens = readFileSync(SEMANTIC_TOKENS, "utf8");

    expect(tokens).toContain("--accent-whatsapp-ink: #0d3a1f;");
    expect(tokens).toContain(
      "~6.45:1 on #25d366; ratified at apps/mouth/src/app/(visa-oracle)/visa-oracle/oracle.css:23-30.",
    );
  });

  it("the article and book WhatsApp CTAs use the ink token", () => {
    for (const file of [ARTICLE, BOOK]) {
      const source = readFileSync(file, "utf8");
      expect(unsafeWhatsAppPairs(source), file).toEqual([]);
      expect(source, file).toContain("text-[var(--accent-whatsapp-ink)]");
    }
  });

  it("only the green-fill services CTA selects the dark ink", () => {
    const source = readFileSync(SERVICES, "utf8");

    expect(source).toContain('accent: "#22c55e",');
    expect(source).toContain('ctaInk: "var(--accent-whatsapp-ink)",');
    expect(source).toContain('color: s.ctaInk ?? "#ffffff",');
  });

  it("the sweep actually visits a realistic number of files (not a silently-empty glob)", () => {
    // The known-good baseline is in the low thousands of .ts/.tsx/.jsx/.css
    // files under apps/mouth/src + packages/core; a handful would mean the
    // roots/extensions are wrong, not that the repo shrank.
    expect(SWEPT_FILES.length).toBeGreaterThan(500);
  });

  it("no surface anywhere under apps/mouth/src or packages/core pairs a WhatsApp-green fill with light ink", () => {
    const offenders: string[] = [];
    for (const file of SWEPT_FILES) {
      const source = readFileSync(file, "utf8");
      const pairs = unsafeWhatsAppPairs(source);
      if (pairs.length > 0) {
        offenders.push(`${relative(REPO_ROOT, file)}: ${pairs.join(" | ")}`);
      }
    }
    expect(
      offenders,
      offenders.length === 0
        ? ""
        : `\nUNSAFE WhatsApp fill+ink pairing found (green fill + light ink in the ` +
            `same opening tag):\n  ${offenders.join("\n  ")}\n` +
            `  Fix: swap the ink to text-[var(--accent-whatsapp-ink)] / ` +
            `color: "var(--accent-whatsapp-ink)".\n`,
    ).toEqual([]);
  });
});
