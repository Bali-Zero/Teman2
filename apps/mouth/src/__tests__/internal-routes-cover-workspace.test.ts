// Every (workspace) page must be an INTERNAL route — derived, not listed.
//
// WHY THIS TEST AND NOT EIGHT MORE ASSERTIONS. /lkpm answered 200 on the public
// domain because it was a workspace page nobody had added to INTERNAL_ROUTES. That
// was fixed by adding /lkpm. Eight more routes then turned out to have exactly the
// same hole, found only because a production sweep happened to probe wider — and
// fixing those by name would leave the NINTH to be found the same way, by accident,
// some months later.
//
// So this test closes the CLASS: it reads the route directories off the filesystem
// and requires each one to be covered. A new workspace page that nobody routes is
// red here, on the commit that adds it, before it is ever deployed.
import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { INTERNAL_ROUTES } from "../proxy";

// Resolved from THIS FILE, not from process.cwd(). A runner invoked from the repo
// root instead of apps/mouth would otherwise throw ENOENT and take the suite with it.
const HERE = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE_DIR = path.resolve(HERE, "..", "app", "(workspace)");

// Next resolves a page from any of these; listed rather than globbed so an unknown
// extension is a visible omission instead of a silent one.
const PAGE_FILES = [
  "page.tsx",
  "page.ts",
  "page.jsx",
  "page.js",
  "page.mjs",
  "page.cjs",
  "page.mdx",
];

/** Fewer than this many workspace routes means the walk broke, not that the app shrank. */
const MIN_EXPECTED_WORKSPACE_ROUTES = 10;

/**
 * Every URL path under (workspace) that renders a page, as the browser sees it.
 *
 * RECURSIVE, and it descends INTO route groups. The first version of this walk read
 * one directory level and required a page.* at that level, which misses two real
 * shapes: a section with subpages but no index (settings/security/page.tsx with no
 * settings/page.tsx), and anything inside a route group — `(workspace)/(portal)/tickets`
 * is served at `/tickets`, so skipping the parenthesised directory loses the route
 * entirely. A refuter found both, and they are the same two mistakes the chunk guard
 * had just been corrected for — written again, in a new file, an hour later.
 */
function workspacePagePaths(
  dir = WORKSPACE_DIR,
  segments: string[] = [],
): string[] {
  const out: string[] = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    // A symlinked directory reports isDirectory() === false, and pages behind it
    // would vanish from the census in silence.
    if (!entry.isDirectory() && !entry.isSymbolicLink()) continue;
    if (
      entry.isSymbolicLink() &&
      !fs.statSync(path.join(dir, entry.name)).isDirectory()
    ) {
      continue;
    }
    const name = entry.name;

    // Parallel-route slots (@modal) and intercepting-route markers ((..)photos,
    // (...)photos) are App Router conventions that are NEITHER plain segments nor
    // route groups. Neither exists here today; they are refused explicitly so the
    // next person gets this sentence instead of a phantom route in a red test.
    if (name.startsWith("@") || /^\(\.{1,3}\)/.test(name)) {
      throw new Error(
        `${name} is a parallel-route slot or intercepting-route marker, which this ` +
          `walk does not model. Teach it the convention before adding one, or the ` +
          `route census will be wrong in a way that looks like a coverage failure.`,
      );
    }

    // A route group organises files and contributes NO URL segment.
    const isGroup = name.startsWith("(") && name.endsWith(")");
    const next = isGroup ? segments : [...segments, name];
    const child = path.join(dir, name);
    if (PAGE_FILES.some((f) => fs.existsSync(path.join(child, f)))) {
      if (next.length > 0) out.push(next.join("/"));
    }
    out.push(...workspacePagePaths(child, next));
  }
  return out;
}

/**
 * The first URL segment of each workspace page — the granularity INTERNAL_ROUTES
 * works at, since the proxy matches `pathname === route || startsWith(route + "/")`.
 * A dynamic first segment cannot be a literal prefix, so it is not a route name.
 */
function workspaceRoutes(): string[] {
  return [
    ...new Set(
      workspacePagePaths()
        .map((p) => p.split("/")[0])
        .filter((seg) => !seg.startsWith("[")),
    ),
  ].sort();
}

/** The real array the proxy uses — imported, not parsed. */
function internalRoutes(): string[] {
  return [...INTERNAL_ROUTES];
}

describe("INTERNAL_ROUTES covers every (workspace) page", () => {
  it("has no workspace page that the public domain would serve", () => {
    const listed = new Set(internalRoutes());
    const uncovered = workspaceRoutes().filter((r) => !listed.has(`/${r}`));
    expect(
      uncovered,
      `these (workspace) pages are not in INTERNAL_ROUTES, so the PUBLIC domain serves ` +
        `them instead of redirecting to the app domain — the /lkpm hole, again: ` +
        `${uncovered.join(", ")}`,
    ).toEqual([]);
  });

  it("derives the routes rather than trusting a hand-written list", () => {
    // Guards the guard: if the derivation silently returned nothing, the test above
    // would pass while checking nothing at all.
    const routes = workspaceRoutes();
    expect(routes.length).toBeGreaterThan(MIN_EXPECTED_WORKSPACE_ROUTES - 1);
    expect(routes).toContain("lkpm");
    expect(routes).toContain("partners");
  });

  it("does NOT sweep up routes that are meant to be public", () => {
    // The innocence half. If this list ever swallowed the marketing site, every
    // public page would 301 to the app domain and the test above would still pass.
    const listed = new Set(internalRoutes());
    for (const publicRoute of ["/team", "/about", "/pricing", "/book", "/v2"]) {
      expect(
        listed.has(publicRoute),
        `${publicRoute} is a public page and must NOT be an internal route`,
      ).toBe(false);
    }
  });
});
