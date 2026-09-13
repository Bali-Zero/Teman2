// The App Router directory grammar, tested once so three consumers do not each guess.
import { describe, it, expect } from "vitest";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  walkAppRoutes,
  urlRoute,
  isRouteGroup,
  isUnmodelledConvention,
  PAGE_FILES,
} from "../../scripts/lib/app-routes.mjs";

/** A tiny in-memory fs, so the grammar is tested on shapes this repo does not have yet. */
function fakeIo(tree: Record<string, string[]>) {
  const dirs = new Set(Object.keys(tree));
  return {
    fs: {
      readdirSync: (dir: string) =>
        (tree[dir] ?? []).map((name) => ({
          name,
          isDirectory: () => dirs.has(`${dir}/${name}`),
          isSymbolicLink: () => false,
        })),
      existsSync: (p: string) => {
        const dir = p.slice(0, p.lastIndexOf("/"));
        const file = p.slice(p.lastIndexOf("/") + 1);
        return (tree[dir] ?? []).includes(file);
      },
      statSync: () => ({ isDirectory: () => true }),
    },
    path: { join: (...parts: string[]) => parts.join("/") },
  } as never;
}

describe("walkAppRoutes", () => {
  it("descends, and a route group contributes no URL segment", () => {
    const io = fakeIo({
      "/app": ["(group)", "plain"],
      "/app/(group)": ["inside", "page.tsx"],
      "/app/(group)/inside": ["page.tsx"],
      "/app/plain": ["page.tsx", "deep"],
      "/app/plain/deep": ["page.tsx"],
    });
    // "" because this fixture also puts a page.tsx directly in the group — that is the
    // ROOT route, kept in the expectation so both behaviours stay visible together
    // instead of one hiding the other.
    expect(walkAppRoutes("/app", io)).toEqual([
      "",
      "inside",
      "plain",
      "plain/deep",
    ]);
  });

  it("finds a section that has subpages but no index of its own", () => {
    const io = fakeIo({
      "/app": ["analytics"],
      "/app/analytics": ["funnel"],
      "/app/analytics/funnel": ["page.tsx"],
    });
    // The shape that made two separate counts disagree: 17 vs 18.
    expect(walkAppRoutes("/app", io)).toEqual(["analytics/funnel"]);
  });

  it("refuses conventions it does not model rather than inventing a route", () => {
    for (const odd of ["@modal", "(..)photos", "(...)photos"]) {
      const io = fakeIo({ "/app": [odd], [`/app/${odd}`]: ["page.tsx"] });
      expect(() => walkAppRoutes("/app", io)).toThrow(/does not model/);
    }
  });

  it("reports a page at the group level as the ROOT route, not as nothing", () => {
    // `(workspace)/(g)/page.tsx` is served at the workspace root, so it is a route.
    // The first extraction dropped it — `next.length > 0` treated the root as an
    // absence — and the guard that previously owned this walk had carried the case as
    // a special line. A refuter caught the loss on the way out of the guard.
    const io = fakeIo({ "/app": ["(g)"], "/app/(g)": ["page.tsx"] });
    expect(walkAppRoutes("/app", io)).toEqual([""]);
  });

  it("reports a page directly inside the walked directory as the ROOT route", () => {
    const io = fakeIo({ "/app": ["page.tsx", "x"], "/app/x": ["page.tsx"] });
    expect(walkAppRoutes("/app", io)).toEqual(["", "x"]);
  });

  it("knows every page extension Next resolves", () => {
    for (const f of PAGE_FILES) {
      const io = fakeIo({ "/app": ["r"], "/app/r": [f] });
      expect(walkAppRoutes("/app", io), `${f} should make a route`).toEqual([
        "r",
      ]);
    }
  });

  it("classifies group vs unmodelled convention without overlap", () => {
    expect(isRouteGroup("(marketing)")).toBe(true);
    expect(isRouteGroup("(..)photos")).toBe(false);
    expect(isUnmodelledConvention("(..)photos")).toBe(true);
    expect(isUnmodelledConvention("@modal")).toBe(true);
    expect(isUnmodelledConvention("(marketing)")).toBe(false);
  });

  it("strips groups from a path, at any depth", () => {
    expect(urlRoute("(a)/x")).toBe("x");
    expect(urlRoute("x/(a)/y")).toBe("x/y");
    expect(urlRoute("(a)/(b)/z")).toBe("z");
    expect(urlRoute("x/y")).toBe("x/y");
  });

  it("agrees with the real tree it is used on", () => {
    const WS = path.resolve(
      path.dirname(fileURLToPath(import.meta.url)),
      "..",
      "app",
      "(workspace)",
    );
    const routes = walkAppRoutes(WS);
    expect(routes.length).toBeGreaterThan(30);
    expect(routes).toContain("analytics/funnel");
    expect(routes.some((r: string) => r.includes("("))).toBe(false);
  });
});
