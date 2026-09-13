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
import { walkAppRoutes } from "../../scripts/lib/app-routes.mjs";

// Resolved from THIS FILE, not from process.cwd(). A runner invoked from the repo
// root instead of apps/mouth would otherwise throw ENOENT and take the suite with it.
const HERE = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE_DIR = path.resolve(HERE, "..", "app", "(workspace)");

// Next resolves a page from any of these; listed rather than globbed so an unknown
// extension is a visible omission instead of a silent one.
/** Fewer than this many workspace routes means the walk broke, not that the app shrank. */
const MIN_EXPECTED_WORKSPACE_ROUTES = 10;

/**
 * The first URL segment of each workspace page — the granularity INTERNAL_ROUTES works
 * at, since the proxy matches `pathname === route || startsWith(route + "/")`.
 *
 * The walk itself is IMPORTED. It was a local copy here and a second local copy inside
 * the chunk guard, written an hour apart by the same hand and wrong in the same two
 * ways. One definition now, in scripts/lib/app-routes.mjs, with its own tests.
 */
function workspaceRoutes(): string[] {
  return [
    ...new Set(
      walkAppRoutes(WORKSPACE_DIR)
        .map((p: string) => p.split("/")[0])
        // "" is the ROOT route — a page directly under (workspace), or under a route
        // group directly beneath it. It cannot be expressed as an INTERNAL_ROUTES
        // prefix (that would be "/", the public home), so it is excluded here on
        // purpose rather than by accident. It does not exist today; if one appears, the
        // collision with the marketing home is a bigger question than route coverage
        // and belongs in front of a human, not silently inside this filter.
        .filter((seg: string) => seg !== "" && !seg.startsWith("[")),
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
