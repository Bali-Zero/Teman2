import { readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * Guilt and innocence (cicatrix-superscar #3): every detector below is proven
 * against a planted violation AND against a legal read, so a green run means
 * the detector is armed, not asleep. It judges CODE, not prose — comments are
 * stripped first so a doc line naming a forbidden pattern does not self-flag.
 */

const FILES = [
  join(
    __dirname,
    "..",
    "..",
    "app",
    "(blog)",
    "services",
    "[slug]",
    "page.tsx",
  ),
  join(__dirname, "ServicePricing.tsx"),
].map((p) => [p, readFileSync(p, "utf8")] as const);

export function stripComments(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/(^|[^:])\/\/.*$/gm, "$1");
}

/** Remove `var(...)` calls, innermost first, so a hex FALLBACK inside one
 * (the sanctioned `var(--token, #hex)` shape) is never mistaken for a
 * hardcoded literal — only what remains outside any var() is judged. */
function stripVarCalls(src: string): string {
  let prev: string;
  let cur = src;
  do {
    prev = cur;
    cur = cur.replace(/var\([^()]*\)/g, "");
  } while (cur !== prev);
  return cur;
}

// The sitewide WhatsApp CTA brand green (#25D366 / its hover #20BD5A) is a
// third-party brand colour, not an R19-vs-old-design signal — it is exempt
// sitewide and carries its OWN dedicated contrast guard
// (`src/app/whatsapp-ink.guard.test.ts`), which this file's WhatsApp button
// must keep satisfying unchanged.
const WHATSAPP_BRAND_HEX = /^#(?:25d366|20bd5a)$/i;

export function findForbiddenHex(src: string): string[] {
  const stripped = stripVarCalls(src);
  return (stripped.match(/(?<![\w#&])#[0-9a-fA-F]{3,8}(?![\w])/g) ?? [])
    .map((h) => h.toLowerCase())
    .filter((h) => !WHATSAPP_BRAND_HEX.test(h));
}

export function findForbiddenGradient(src: string): string[] {
  const out: string[] = [];
  for (const m of src.matchAll(/\bbg-gradient-\S*/g)) out.push(m[0]);
  for (const m of src.matchAll(/linear-gradient\(/g)) out.push(m[0]);
  return out;
}

const PALETTE =
  "sky|blue|cyan|teal|emerald|green|lime|amber|orange|red|rose|pink|fuchsia|purple|violet|indigo";
const PALETTE_RE = new RegExp(
  `\\b(?:bg|text|border|from|to|via|ring|divide|fill|stroke)-(?:${PALETTE})-\\d{2,3}\\b`,
  "g",
);

export function findForbiddenPaletteColor(src: string): string[] {
  return Array.from(src.matchAll(PALETTE_RE)).map((m) => m[0]);
}

export function findForbiddenMonochrome(src: string): string[] {
  const out: string[] = [];
  for (const m of src.matchAll(/\btext-white\b/g)) out.push(m[0]);
  for (const m of src.matchAll(/\bbg-black\b/g)) out.push(m[0]);
  for (const m of src.matchAll(/\bborder-white\/[\w[\].%-]*/g)) out.push(m[0]);
  for (const m of src.matchAll(/\bbg-white\/[\w[\].%-]*/g)) out.push(m[0]);
  return out;
}

export function findForbiddenHeavyWeight(src: string): string[] {
  const out: string[] = [];
  for (const m of src.matchAll(/\bfont-black\b/g)) out.push(m[0]);
  for (const m of src.matchAll(/\bfont-extrabold\b/g)) out.push(m[0]);
  return out;
}

function allFindings(src: string): string[] {
  const s = stripComments(src);
  return [
    ...findForbiddenHex(s),
    ...findForbiddenGradient(s),
    ...findForbiddenPaletteColor(s),
    ...findForbiddenMonochrome(s),
    ...findForbiddenHeavyWeight(s),
  ];
}

describe("the R19 service-template skin carries none of the pre-R19 paint", () => {
  it.each(FILES)("%s reads no forbidden colour/weight class", (name, src) => {
    expect([name, allFindings(src)]).toEqual([name, []]);
  });

  it("the hex detector is awake (guilt) and spares a var() fallback (innocence)", () => {
    expect(findForbiddenHex('background: "#0a2540"')).toEqual(["#0a2540"]);
    expect(
      findForbiddenHex(
        'color: "var(--rp-accent, var(--accent-funnel-text, #5c8aff))"',
      ),
    ).toEqual([]);
  });

  it("spares the sitewide WhatsApp brand green, guarded elsewhere (innocence)", () => {
    expect(
      findForbiddenHex('className="bg-[#25D366] hover:bg-[#20BD5A]"'),
    ).toEqual([]);
  });

  it("the gradient detector is awake (guilt) and spares a plain background (innocence)", () => {
    expect(
      findForbiddenGradient(
        'className="bg-gradient-to-br from-[#e85c41] to-[#d14832]"',
      ),
    ).toContain("bg-gradient-to-br");
    expect(findForbiddenGradient('background: "var(--r19-surface)"')).toEqual(
      [],
    );
  });

  it("the palette detector is awake (guilt) and spares an R19 var read (innocence)", () => {
    expect(findForbiddenPaletteColor('className="bg-sky-500/20"')).toEqual([
      "bg-sky-500",
    ]);
    expect(
      findForbiddenPaletteColor('className="bg-[var(--r19-wash)]"'),
    ).toEqual([]);
  });

  it("the monochrome detector is awake (guilt) and spares ink/paper reads (innocence)", () => {
    expect(findForbiddenMonochrome('className="text-white"')).toEqual([
      "text-white",
    ]);
    expect(
      findForbiddenMonochrome('style={{ color: "var(--text-primary)" }}'),
    ).toEqual([]);
  });

  it("the heavy-weight detector is awake (guilt) and spares normal weight (innocence)", () => {
    expect(findForbiddenHeavyWeight('className="font-extrabold"')).toEqual([
      "font-extrabold",
    ]);
    expect(findForbiddenHeavyWeight('className="font-medium"')).toEqual([]);
  });

  it("the comment stripper keeps code and drops prose (guilt and innocence)", () => {
    expect(stripComments("// bg-sky-500/20\nconst a = 1;").trim()).toBe(
      "const a = 1;",
    );
    expect(stripComments('const u = "https://x.test/a";')).toContain(
      "https://x.test/a",
    );
  });
});
