import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

/**
 * Canonical guard for statically-submitted sitemap routes (2026-09-08).
 *
 * TRAUMA (SEO_STATE.md §3.1): `/kbli-explorer` is named in `sitemap.ts`,
 * `robots.ts`'s JSON-LD `SearchAction`, and its own `openGraph.url` as a
 * distinct address — but its `layout.tsx` declared no `alternates`, so it
 * inherited the ROOT layout's `alternates.canonical = appUrl`
 * (`app/layout.tsx:130`). Next.js merges `alternates` shallowly per segment:
 * a segment with no `alternates` of its own inherits the parent's whole,
 * so the served page's `<link rel="canonical">` pointed at the homepage —
 * a URL we ask Google to index that asks, in its own HTML, to be folded away.
 *
 * A prior manual audit missed this: a substring test for `canonical:` scored
 * the route "covered" off a prose comment in `page.tsx` that merely mentions
 * the word. This guard reads actual metadata shapes, not comments — see
 * `stripComments` below — and it is the OWN canonical, not an ancestor's,
 * that must be present: inheriting the root's is exactly the defect.
 *
 * DECLARED SCOPE: only the routes `sitemap.ts` submits via its own literal
 * path arrays (`staticPaths`, `servicePaths`, `visaPaths`) plus its two
 * ad-hoc single pushes (`/taxes/gap`, `/kbli/sectors`). Per-item dynamic
 * sitemap entries (blog articles, KBLI codes, KBLI sectors, `[category]`)
 * are excluded on purpose — each is confirmed self-canonical via its own
 * `generateMetadata()` (SEO_STATE.md §1/§2) and a generic per-item probe is
 * a different, larger guard than this PR's concern. A route this file does
 * not scan has SEO canonical status "unknown", not "fine" — same rule as
 * SEO_STATE.md itself.
 */

const APP_DIR = path.dirname(fileURLToPath(import.meta.url));
const SITEMAP_SRC = fs.readFileSync(path.join(APP_DIR, "sitemap.ts"), "utf8");

function stripComments(src: string): string {
  return src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
}

function readSrc(file: string): string | null {
  return fs.existsSync(file)
    ? stripComments(fs.readFileSync(file, "utf8"))
    : null;
}

/** `sitemap.ts`'s own literal path list — the routes actually submitted. */
function literalArray(name: string): string[] {
  const m = new RegExp(`const ${name}[^=]*=\\s*\\[([\\s\\S]*?)\\];`).exec(
    SITEMAP_SRC,
  );
  if (!m) return [];
  return [...m[1].matchAll(/"(\/?[^"]*)"/g)].map((x) => x[1]);
}

// Ad-hoc single `url:` pushes outside the three named arrays — literal, not
// data-driven (contrast `kbli/sectors/${s.id}` a few lines below each, which
// IS data-driven and out of scope per the docblock above).
const AD_HOC_STATIC_PATHS = ["/taxes/gap", "/kbli/sectors"];

const SITEMAP_STATIC_PATHS = [
  ...literalArray("staticPaths"),
  ...literalArray("servicePaths"),
  ...literalArray("visaPaths"),
  ...AD_HOC_STATIC_PATHS,
];

/** True if `src` declares `alternates: { canonical: … }` anywhere at all — a
 * static `export const metadata`, a `generateMetadata()` body, or a
 * delegated builder's own return object. One shared shape covers all three
 * call sites this codebase actually uses (SEO_STATE.md §1: three places a
 * canonical can live). */
function declaresOwnCanonical(src: string): boolean {
  return /alternates:\s*\{[^}]*canonical:/s.test(src);
}

/** Follows a one-hop `return someBuilder(...)` delegation to an imported
 * function and checks THAT module for its own canonical declaration —
 * matches `[category]/[slug]` → `lib/blog/metadata.ts:93 generateArticleMetadata()`. */
function delegatesCanonical(src: string, fileDir: string): boolean {
  const call = /return\s+(?:await\s+)?(\w+)\(/.exec(src);
  if (!call) return false;
  const imp = new RegExp(
    `import\\s*\\{[^}]*\\b${call[1]}\\b[^}]*\\}\\s*from\\s*["']([^"']+)["']`,
  ).exec(src);
  if (!imp) return false;
  const target = imp[1].startsWith(".")
    ? path.resolve(fileDir, imp[1])
    : path.resolve(APP_DIR, "..", imp[1].replace(/^@\//, ""));
  for (const ext of [".ts", ".tsx"]) {
    const full = readSrc(target + ext);
    if (full && declaresOwnCanonical(full)) return true;
  }
  return false;
}

function fileDeclaresCanonical(file: string): boolean {
  const src = readSrc(file);
  if (!src) return false;
  return (
    declaresOwnCanonical(src) || delegatesCanonical(src, path.dirname(file))
  );
}

/** Own-segment canonical only — an inherited one is the defect, not the fix. */
function isSelfCanonical(routeDir: string): boolean {
  return (
    fileDeclaresCanonical(path.join(routeDir, "page.tsx")) ||
    fileDeclaresCanonical(path.join(routeDir, "layout.tsx"))
  );
}

/** Resolves a URL path to its filesystem route directory, walking route
 * groups (`(name)`, consume no segment) and dynamic segments (`[name]`,
 * consume one) the way Next.js's own router does. Static segments always
 * outrank a dynamic one at the SAME level — two full passes per directory
 * (literal-and-groups, then bracket) enforce that regardless of readdir's
 * alphabetical order, which otherwise hands `/services/visa` to the
 * unrelated `(blog)/[category]/[slug]` route before `(blog)/services/[slug]`
 * ever gets a look. */
function findRouteDir(
  baseDir: string,
  segments: string[],
  allowBracket: boolean,
): string | null {
  const entries = fs
    .readdirSync(baseDir, { withFileTypes: true })
    .filter((e) => e.isDirectory());

  if (segments.length === 0) {
    if (fs.existsSync(path.join(baseDir, "page.tsx"))) return baseDir;
    for (const e of entries.filter((e) => e.name.startsWith("("))) {
      const hit = findRouteDir(
        path.join(baseDir, e.name),
        segments,
        allowBracket,
      );
      if (hit) return hit;
    }
    return null;
  }

  const [seg, ...rest] = segments;
  for (const e of entries.filter(
    (e) => e.name === seg || e.name.startsWith("("),
  )) {
    const nextSegments = e.name === seg ? rest : segments;
    const hit = findRouteDir(
      path.join(baseDir, e.name),
      nextSegments,
      allowBracket,
    );
    if (hit) return hit;
  }
  if (allowBracket) {
    for (const e of entries.filter((e) => /^\[.*\]$/.test(e.name))) {
      const hit = findRouteDir(path.join(baseDir, e.name), rest, allowBracket);
      if (hit) return hit;
    }
  }
  return null;
}

/** Two global passes, not one per-level pass: a literal match anywhere in
 * the tree must win over a dynamic-segment match anywhere else, even when
 * the dynamic candidate sits at a shallower group and would otherwise
 * short-circuit the recursion first (`/visa/match` would resolve into
 * `(blog)/[category]/[slug]` if brackets were allowed from the start). */
function routeDirFor(urlPath: string): string | null {
  const segments = urlPath.split("/").filter(Boolean);
  return (
    findRouteDir(APP_DIR, segments, false) ??
    findRouteDir(APP_DIR, segments, true)
  );
}

describe("canonical coverage of statically-submitted sitemap routes", () => {
  it("finds routes to check (the probe can produce a positive)", () => {
    expect(SITEMAP_STATIC_PATHS.length).toBeGreaterThanOrEqual(15);
  });

  it("resolves every checkable path to a real route directory", () => {
    const unresolved = SITEMAP_STATIC_PATHS.filter(
      (p) => routeDirFor(p) === null && !/\.(txt|xml)$/.test(p),
    );
    // `/llms.txt` etc. are `route.ts` text endpoints, not pages — no
    // canonical link tag applies to them, so they resolve to null on purpose.
    expect(unresolved).toEqual([]);
  });

  it("positive control: /visa is self-canonical", () => {
    const dir = routeDirFor("/visa");
    expect(dir).not.toBeNull();
    expect(isSelfCanonical(dir!)).toBe(true);
  });

  it("regression guard: /kbli-explorer is self-canonical", () => {
    const dir = routeDirFor("/kbli-explorer");
    expect(dir).not.toBeNull();
    expect(isSelfCanonical(dir!)).toBe(true);
  });

  it("dynamic-segment routes resolve through their bracketed directory", () => {
    // /services/[slug] and /visa/second-home/[locale] — literal sitemap
    // paths that only exist on disk as a dynamic segment.
    for (const p of ["/services/visa", "/visa/second-home/it"]) {
      const dir = routeDirFor(p);
      expect(dir).not.toBeNull();
      expect(isSelfCanonical(dir!)).toBe(true);
    }
  });

  it("no statically-submitted sitemap route inherits the root canonical", () => {
    const offenders = SITEMAP_STATIC_PATHS.filter((p) => {
      if (/\.(txt|xml)$/.test(p)) return false;
      const dir = routeDirFor(p);
      return dir !== null && !isSelfCanonical(dir);
    });
    expect(offenders).toEqual([]);
  });
});
