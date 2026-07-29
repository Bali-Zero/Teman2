import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

/**
 * Brand-suffix guard for page titles (2026-07-28, widened 2026-07-29).
 *
 * TRAUMA: the root layout sets `title.template = "%s | Bali Zero"`, so Next.js
 * appends the brand to a page title on its own. Pages appended it a second time
 * by hand and shipped a stutter to production:
 *
 *   <title>Careers — Bali Zero | Bali Zero</title>
 *   <title>Terms of Service — Bali Zero — Visa | Bali Zero</title>
 *
 * Nobody noticed because each page looks right in isolation — the defect exists
 * only in the COMPOSITION of the page title with a template declared in another
 * file. It costs real estate too: Google renders ~60 characters and the repeat
 * burned twelve of them.
 *
 * ---
 * ROUND 1 (07-28) cured eleven pages and left THREE holes, all measured live:
 *
 *   1. it read `title: "…"` only, so `title: { template, default }` was
 *      invisible. `(book)/layout.tsx` shipped `default: 'Bali Zero — The story'`
 *      → /book served `Bali Zero — The story | Bali Zero`.
 *   2. it matched double-quoted literals only. `privacy/page.tsx` uses single
 *      quotes → /privacy served `Privacy Policy — Bali Zero | Bali Zero`.
 *   3. worst, it asserted as INNOCENCE that a mid-string brand is fine —
 *      naming `"Terms of Service — Bali Zero — Visa"` as the legitimate case.
 *      That is not a hypothetical, it is `visa/terms/page.tsx`, and live it
 *      served `… — Visa | Bali Zero`. A guard's innocence case can excuse a
 *      real defect: the position of the brand never mattered, only whether the
 *      composed title carries it twice.
 *
 * So the rule is on the COMPOSITION, not the shape: a title the template will
 * touch must not contain the brand at all. A page that genuinely needs the
 * brand inside its own title says so with `absolute`, which is exactly what
 * `absolute` is for.
 *
 * ---
 * WHICH titles the template actually touches — measured, not assumed. The root
 * template is consumed by the FIRST descendant title it meets and does not
 * cascade past it:
 *
 *   /privacy             → Privacy Policy — Bali Zero | Bali Zero   (templated)
 *   /assessment          → Assessment | Bali Zero                   (templated)
 *   /assessment/briefing → Briefing — Bali Zero Assessment          (NOT: the
 *       `(assessment)/assessment/layout.tsx` title already consumed it)
 *
 * so a file under an ancestor layout that declares its own title is exempt —
 * flagging it would be an over-match, and `/assessment/briefing` is pinned
 * below as the innocence case that proves the walk is real.
 *
 * DECLARED LIMIT: static `export const metadata` only. A title built inside
 * `generateMetadata()` is invisible here — `(book)/book/[chapter]` is the one
 * that does it, and it is covered by `components/book/book-title.test.ts`.
 * A surface excluded "for later" is a surface covered never.
 */

const APP_DIR = path.dirname(fileURLToPath(import.meta.url));
const BRAND = "Bali Zero";

/** `"…"` or `'…'`, with escapes — both quote styles occur in this tree. */
const QUOTED = String.raw`"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'`;

function unquote(literal: string): string {
  return literal.slice(1, -1).replace(/\\(.)/g, "$1");
}

function tsxFiles(dir: string): string[] {
  const out: string[] = [];
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) out.push(...tsxFiles(p));
    else if (e.name.endsWith(".tsx")) out.push(p);
  }
  return out;
}

type Declared = { title: string; kind: string } | null;

/**
 * The top-level static title a file declares, if any.
 *
 * `title: { absolute: … }` returns null on purpose: `absolute` ignores any
 * ancestor template by definition, so nothing can be appended to it.
 */
function declaredTitle(file: string): Declared {
  if (!fs.existsSync(file)) return null;
  const src = fs.readFileSync(file, "utf8");
  const decl = /export const metadata[^=]*=\s*\{/.exec(src);
  if (!decl) return null;
  const tail = src.slice(decl.index + decl[0].length);

  // two-space indent = first level of the metadata object; a nested
  // openGraph/twitter title is indented deeper and is NOT templated by Next.
  const asString =
    new RegExp(String.raw`^ {2}title:\s*(${QUOTED})`, "m").exec(tail) ??
    new RegExp(String.raw`^ {2}title:\s*\n\s+(${QUOTED})`, "m").exec(tail);
  if (asString) return { title: unquote(asString[1]), kind: "title" };

  const asObject = /^ {2}title:\s*\{([\s\S]*?)^ {2}\}/m.exec(tail);
  if (!asObject) return null;
  const body = asObject[1];
  if (/\babsolute:/.test(body)) return null;
  const def = new RegExp(String.raw`\bdefault:\s*(${QUOTED})`).exec(body);
  return def ? { title: unquote(def[1]), kind: "title.default" } : null;
}

/**
 * True when the app-root template still reaches this file — i.e. no layout
 * STRICTLY ABOVE the file's own segment already consumed it.
 *
 * The walk starts at the file's grandparent directory, and that is measured,
 * not stylistic: a layout in the SAME segment does not consume the template for
 * its sibling page — `(blog)/contact/` holds both a layout title and a page
 * title, and live it is the PAGE's title that renders, templated. Starting the
 * walk one level lower would also let a layout exempt itself, which is how the
 * first draft of this function read clean while six offenders sat under it.
 */
function isTemplated(file: string): boolean {
  let dir = path.dirname(path.dirname(file));
  while (dir !== APP_DIR && dir.startsWith(APP_DIR)) {
    if (declaredTitle(path.join(dir, "layout.tsx"))) return false;
    dir = path.dirname(dir);
  }
  return true;
}

/** Every static title the root template will append the brand to. */
function templatedTitles(): { file: string; title: string; kind: string }[] {
  const found: { file: string; title: string; kind: string }[] = [];
  for (const file of tsxFiles(APP_DIR)) {
    const rel = path.relative(APP_DIR, file);
    // The app-root layout's own default is what the template appends TO.
    if (rel === "layout.tsx") continue;
    const d = declaredTitle(file);
    if (!d) continue;
    // A layout's own title is judged against its PARENT chain, not its own.
    if (!isTemplated(file)) continue;
    found.push({ file: rel, title: d.title, kind: d.kind });
  }
  return found;
}

describe("page titles vs the root title template", () => {
  it("finds titles to check (the probe can produce a positive)", () => {
    // An empty scan would make the assertion below vacuously true — the
    // failure mode where a guard passes because it looked at nothing.
    expect(templatedTitles().length).toBeGreaterThanOrEqual(20);
  });

  it("reads BOTH title shapes and BOTH quote styles", () => {
    // Round 1 saw only double-quoted `title: "…"`, and both blind spots shipped
    // a stutter. If a refactor narrows the scan back, pin it here.
    const kinds = new Set(templatedTitles().map((t) => t.kind));
    expect([...kinds].sort()).toEqual(["title", "title.default"]);
    expect(
      declaredTitle(path.join(APP_DIR, "privacy/page.tsx")),
    ).not.toBeNull();
  });

  it("no templated title carries the brand the template already appends", () => {
    const offenders = templatedTitles()
      .filter((t) => t.title.includes(BRAND))
      .map((t) => `${t.file} (${t.kind}): ${t.title}`);
    expect(offenders).toEqual([]);
  });

  it("exempts the shapes no template touches (innocence)", () => {
    const scanned = templatedTitles().map((t) => t.file);

    // 1. the app-root layout's own default — nothing appends to it
    expect(scanned).not.toContain("layout.tsx");

    // 2. `title: { absolute: … }` — opts out of the parent template
    const marketing = path.join(APP_DIR, "(marketing)/page.tsx");
    expect(fs.readFileSync(marketing, "utf8")).toMatch(
      /absolute:\s*["']Bali Zero \|/,
    );
    expect(declaredTitle(marketing)).toBeNull();

    // 3. a page under a layout that already consumed the template. Measured
    //    live: /assessment/briefing renders WITHOUT ` | Bali Zero`, so its
    //    in-title brand is legitimate and flagging it would be an over-match.
    const briefing = "(assessment)/assessment/briefing/page.tsx";
    expect(declaredTitle(path.join(APP_DIR, briefing))?.title).toContain(BRAND);
    expect(scanned).not.toContain(briefing);
  });

  it("still judges a layout by its OWN ancestors, not by itself (guilt)", () => {
    // `(assessment)/assessment/layout.tsx` declares a title, which exempts its
    // CHILDREN — it must not exempt itself, or a layout could carry the brand
    // freely. It is scanned; it just happens to be clean.
    expect(templatedTitles().map((t) => t.file)).toContain(
      "(assessment)/assessment/layout.tsx",
    );
  });

  it("catches every form the codebase actually shipped (guilt)", () => {
    const shipped = [
      "Careers — Bali Zero", // trailing, round 1
      "Login - Bali Zero", // trailing, hyphen
      "Privacy Policy — Bali Zero", // trailing, single-quoted source
      "Terms of Service — Bali Zero — Visa", // MID-string: round 1 excused this
      "Contact · Bali Zero", // mid/interpunct
      "About Bali Zero", // brand inside the phrase
      "Bali Zero — The story", // a `title.default`, brand FIRST
      "Bali Zero", // the whole title is the brand
    ];
    for (const bad of shipped) expect(bad.includes(BRAND)).toBe(true);
  });

  it("a title with no brand at all is left alone (innocence)", () => {
    for (const ok of ["Careers", "Assessment", "The story", "Zoning Check"]) {
      expect(ok.includes(BRAND)).toBe(false);
    }
  });
});
