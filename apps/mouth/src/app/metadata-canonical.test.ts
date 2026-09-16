import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

/**
 * Self-canonical guard for public routes (2026-09-14).
 *
 * TRAUMA: the app-root layout declares
 *
 *   alternates: { canonical: appUrl }        // layout.tsx:145, appUrl = origin
 *
 * and Next.js INHERITS `alternates` into every descendant segment that does
 * not override it. So a public page that forgets its own canonical does not
 * ship "no canonical" — it ships `<link rel="canonical" href="https://balizero.com">`,
 * which actively tells Google the page IS the homepage and invites Google to
 * drop it from the index in favour of `/`.
 *
 * That is not hypothetical. #5887 (`267676a`, 2026-09-09) is exactly this bug,
 * one route at a time:
 *
 *   fix(seo): give /kbli-explorer its own canonical instead of the homepage
 *
 * #5887 shipped the cure for ONE route and no guard, so the next forgotten
 * canonical is silent again. A census of `origin/main` on 2026-09-14 found the
 * same shape still live on seven more public routes — `/terms` and `/privacy`
 * among them, both linked from the footer. Fixing routes one incident at a
 * time is how a class of defect survives its own fix.
 *
 * ---
 * WHY A RATCHET AND NOT A BAN. 141 `page.tsx` exist; 106 declare no canonical
 * of their own, and for most of them that is CORRECT:
 *
 *   - `(workspace)/**`, `portal/**`, `login`, `prime/**`  — kita / my / prime,
 *     internal hosts that robots.ts blocks wholesale. Nothing to canonicalise.
 *   - `v2/**` — eight pages, each carrying `robots: { index: false }`. A
 *     noindex page's canonical is moot by definition.
 *   - `/chat` — `robots.ts` DISALLOW carries it; never crawled, never read.
 *
 * A blanket "every page must declare a canonical" would fail on ~100 files on
 * the day it landed and be deleted by the next person. So the guard freezes
 * the offender set as it was MEASURED and fails on the 143rd page, not the
 * 106 that already exist: the list below may only ever get SHORTER.
 *
 * DECLARED LIMIT: static `canonical:` text only. A canonical assembled inside
 * `generateMetadata()` counts as declared (the regex sees it wherever it sits)
 * but its VALUE is not checked — `(book)/book/[chapter]` is the one that does
 * this, and it is in the bare list below for the separate reason that it
 * declares none at all.
 */

const APP_DIR = path.dirname(fileURLToPath(import.meta.url));
const ORIGIN = "https://balizero.com";

/**
 * Route prefixes that are not public balizero.com surface. Measured against
 * robots.ts on 2026-09-14: INTERNAL_HOSTS returns `disallow: "/"` for
 * kita/my/prime/zantara, and DISALLOW carries /chat, /login, /admin and the
 * rest of the workspace on the public host.
 */
const NOT_PUBLIC = [
  "(workspace)/",
  "portal/",
  "(visa-oracle)/",
  "(assessment)/",
  "login/",
  "prime/",
  "chat/", // robots.ts DISALLOW
];

/**
 * Public pages that inherit the homepage canonical TODAY. Measured on
 * origin/main `e029a006be`, 2026-09-14 08:5x WITA, AFTER this PR gives
 * /terms and /privacy their own. `(nuzantara)` is absent because it carries
 * `robots: { index: false }` and leaves by the noindex door, not this one.
 *
 * This list is a debt register, not a permission slip. Each entry is a page
 * whose served canonical is `https://balizero.com`. None is in sitemap.xml and
 * none carries an internal <a href> (measured: 0 occurrences each), which is
 * why they rank below /terms and /privacy in urgency — not why they are fine.
 */
const KNOWN_BARE = [
  "(book)/book/[chapter]/page.tsx",
  "(book)/book/page.tsx",
  "agents/page.tsx",
];

/** `"…"`, `'…'` or a template literal — all three shapes occur in this tree. */
const QUOTED = String.raw`"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|\`(?:[^\`\\]|\\.)*\``;

function walk(dir: string, out: string[] = []): string[] {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walk(p, out);
    else if (/\.tsx?$/.test(e.name) && !/\.test\.tsx?$/.test(e.name))
      out.push(p);
  }
  return out;
}

/** The raw `canonical:` expression a file declares, if any. */
function canonicalExpr(file: string): string | null {
  if (!fs.existsSync(file)) return null;
  const src = fs.readFileSync(file, "utf8");
  const m = new RegExp(
    String.raw`^\s*canonical:\s*(${QUOTED}|[A-Za-z_$][\w$]*)`,
    "m",
  ).exec(src);
  return m ? m[1] : null;
}

/**
 * The file's own chain: itself plus every ancestor layout STRICTLY BELOW the
 * app root. The app-root layout is excluded on purpose — it is the thing whose
 * inheritance this guard exists to catch, so counting it as coverage would
 * make every assertion below vacuously true.
 */
function chainBelowRoot(pageRel: string): string[] {
  const out = [pageRel];
  let dir = path.dirname(pageRel);
  while (dir !== "." && dir !== "") {
    const layout = path.join(dir, "layout.tsx");
    if (fs.existsSync(path.join(APP_DIR, layout))) out.push(layout);
    dir = path.dirname(dir);
  }
  return out;
}

function pages(): string[] {
  return walk(APP_DIR)
    .map((f) => path.relative(APP_DIR, f))
    .filter((rel) => path.basename(rel) === "page.tsx");
}

function isPublic(rel: string): boolean {
  // `@slot` directories are parallel-route interceptions, not addressable URLs.
  return !NOT_PUBLIC.some((p) => rel.startsWith(p)) && !rel.includes("@");
}

/**
 * True when the page or a layout below the root opts the route out of the
 * index. A noindex page's canonical is moot — Google never consolidates a URL
 * it was told not to index — so flagging one would be an over-match. `v2/**`
 * is eight such pages and is the reason this function exists.
 */
function isNoindex(rel: string): boolean {
  return chainBelowRoot(rel).some((f) => {
    const p = path.join(APP_DIR, f);
    return (
      fs.existsSync(p) &&
      /robots:\s*\{[^}]*index:\s*false/.test(fs.readFileSync(p, "utf8"))
    );
  });
}

/** True when the page or a layout below the root declares a canonical. */
function selfCanonical(rel: string): boolean {
  return chainBelowRoot(rel).some((f) =>
    Boolean(canonicalExpr(path.join(APP_DIR, f))),
  );
}

function barePublicPages(): string[] {
  return pages()
    .filter((rel) => isPublic(rel) && !isNoindex(rel) && !selfCanonical(rel))
    .sort();
}

describe("public routes vs the inherited homepage canonical", () => {
  it("the probe can produce a positive (it is not scanning nothing)", () => {
    // A scan that reaches no files would make every assertion below pass for
    // the wrong reason — the failure mode that let #5887 sit unnoticed.
    expect(pages().length).toBeGreaterThanOrEqual(120);
    const declaring = walk(APP_DIR).filter((f) => canonicalExpr(f));
    expect(declaring.length).toBeGreaterThanOrEqual(20);
  });

  it("sees the route #5887 actually cured (positive control on the fix)", () => {
    // If a refactor moves or renames this, the guard must notice before it
    // silently starts reporting a clean tree.
    const fixed = path.join(APP_DIR, "kbli-explorer/layout.tsx");
    expect(canonicalExpr(fixed)).toBe("`${baseUrl}/kbli-explorer`");
  });

  it("the app root really does declare a canonical to inherit (the premise)", () => {
    // Everything here rests on the root declaring one. If that ever stops
    // being true the trauma comment above is obsolete and so is the ratchet.
    expect(canonicalExpr(path.join(APP_DIR, "layout.tsx"))).toBe("appUrl");
  });

  it("no NEW public route inherits the homepage canonical (the ratchet)", () => {
    // The list may only shrink. A page added without its own canonical shows
    // up here; the fix is to give it one, not to extend KNOWN_BARE.
    expect(barePublicPages()).toEqual([...KNOWN_BARE].sort());
  });

  it("the two footer-linked legal pages are cured (guilt, #5887's class)", () => {
    // Measured 2026-09-14: /terms carries 2 internal hrefs and /privacy 3 —
    // the same order as /contact. Crawlable, and until this PR both served
    // `canonical: https://balizero.com`.
    for (const rel of ["terms/page.tsx", "privacy/page.tsx"]) {
      const expr = canonicalExpr(path.join(APP_DIR, rel));
      expect(expr).not.toBeNull();
      const route = "/" + path.dirname(rel);
      expect(expr).toBe(`"${ORIGIN}${route}"`);
    }
  });

  it("every static canonical points at its own route, not a sibling's", () => {
    // Copy-paste between neighbouring pages is the other way a canonical goes
    // wrong, and it is invisible in review: /kbli/builder declaring
    // /kbli/decoder looks correct in the diff.
    const wrong: string[] = [];
    for (const rel of pages()) {
      const expr = canonicalExpr(path.join(APP_DIR, rel));
      if (!expr || !/^["']/.test(expr)) continue;
      const value = expr.slice(1, -1);
      const segments = path
        .dirname(rel)
        .split(path.sep)
        .filter((s) => !(s.startsWith("(") && s.endsWith(")")));
      const route = segments.length ? "/" + segments.join("/") : "";
      if (value !== ORIGIN + route)
        wrong.push(`${rel}: ${value} != ${ORIGIN}${route}`);
    }
    expect(wrong).toEqual([]);
  });

  it("leaves the homepage alone (innocence)", () => {
    // The homepage's canonical IS the origin. It is the one file for which the
    // inherited value is the right value, and it says so explicitly.
    expect(canonicalExpr(path.join(APP_DIR, "(marketing)/page.tsx"))).toBe(
      `"${ORIGIN}"`,
    );
  });

  it("leaves noindex and robots-blocked routes alone (innocence)", () => {
    // /v2 is eight pages of deliberate `robots: { index: false }`; a noindex
    // page's canonical is moot. Flagging them would be an over-match, and
    // "fixing" them would imply /v2 is meant to be indexed.
    const v2 = fs.readFileSync(path.join(APP_DIR, "v2/page.tsx"), "utf8");
    expect(v2).toMatch(/robots:\s*\{\s*index:\s*false/);
    expect(isNoindex("v2/page.tsx")).toBe(true);
    expect(barePublicPages()).not.toContain("v2/page.tsx");
    // ...but the exemption is earned by the flag, not by the path: strip the
    // noindex and the ratchet must reclaim the route.
    expect(isPublic("v2/page.tsx")).toBe(true);
    expect(selfCanonical("v2/page.tsx")).toBe(false);
    expect(isPublic("chat/page.tsx")).toBe(false);
  });

  it("keeps the debt register honest (no permanent exemptions)", () => {
    // A name left in KNOWN_BARE after the route gained a canonical would be a
    // dead exemption that quietly re-opens the hole for that path.
    for (const rel of KNOWN_BARE) {
      expect(fs.existsSync(path.join(APP_DIR, rel))).toBe(true);
      expect(selfCanonical(rel)).toBe(false);
    }
  });
});
