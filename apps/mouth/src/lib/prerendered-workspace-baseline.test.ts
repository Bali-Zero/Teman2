// The prerender baseline, tested by executing it.
//
// The rule it encodes is "an ALREADY-static workspace route is accepted with its
// measurement; a NEWLY static one fails". Both halves matter: without the first the
// build is red today over an exposure nobody in this lane owns, and without the
// second a new payload file lands in silence — which is how /lkpm happened.
import { describe, it, expect } from "vitest";
import {
  unacceptedPrerenderedWorkspaceRoutes,
  staleAcceptedRoutes,
  ACCEPTED_PRERENDERED_WORKSPACE_ROUTES,
} from "../../scripts/lib/prerendered-workspace-baseline.mjs";
import { urlRoute, walkAppRoutes } from "../../scripts/lib/app-routes.mjs";
import path from "node:path";
import { fileURLToPath } from "node:url";

describe("prerendered workspace baseline", () => {
  it("accepts the routes that are already static", () => {
    expect(
      unacceptedPrerenderedWorkspaceRoutes({
        workspaceRoutes: [...ACCEPTED_PRERENDERED_WORKSPACE_ROUTES],
        prerenderedPaths: ACCEPTED_PRERENDERED_WORKSPACE_ROUTES.map(
          (r: string) => `/${r}`,
        ),
      }),
    ).toEqual([]);
  });

  it("fails a NEW workspace route that has become static", () => {
    expect(
      unacceptedPrerenderedWorkspaceRoutes({
        workspaceRoutes: ["clients", "brand-new"],
        prerenderedPaths: ["/clients", "/brand-new"],
      }),
    ).toEqual(["brand-new"]);
  });

  it("says nothing about a new workspace route that stays dynamic", () => {
    expect(
      unacceptedPrerenderedWorkspaceRoutes({
        workspaceRoutes: ["clients", "brand-new"],
        prerenderedPaths: ["/clients"],
      }),
    ).toEqual([]);
  });

  /**
   * The hole a refuter found in the first draft: the walk read one directory level, so
   * a nested route was invisible — and 25 of them were ALREADY prerendered. A shallow
   * enumeration is not a smaller version of this check, it is a different check that
   * happens to pass.
   */
  it("fails a NESTED workspace route that has become static", () => {
    expect(
      unacceptedPrerenderedWorkspaceRoutes({
        workspaceRoutes: ["admin", "admin/test-static"],
        prerenderedPaths: ["/admin", "/admin/test-static"],
      }),
    ).toEqual(["admin/test-static"]);
  });

  it("accepts the nested routes that are already static", () => {
    for (const nested of [
      "hr/payroll",
      "settings/profile",
      "intelligence/news-room",
    ]) {
      expect(
        ACCEPTED_PRERENDERED_WORKSPACE_ROUTES,
        `${nested} is prerendered today and must be in the measured baseline`,
      ).toContain(nested);
    }
  });

  /**
   * A route GROUP — a directory in parentheses — organises files and does not appear
   * in the URL. A seat pointed out that the walk would report `(admin)/settings` while
   * the manifest key is `/settings`, so such a route would be prerendered, unscanned
   * and invisible: the exact class this baseline exists to close. There are no nested
   * groups under (workspace) today; the point is the NEXT change.
   */
  it("sees through route groups, which are not part of the URL", () => {
    expect(urlRoute("(admin)/settings")).toBe("settings");
    expect(urlRoute("hr/(internal)/payroll")).toBe("hr/payroll");
    expect(urlRoute("clients/new")).toBe("clients/new");

    expect(
      unacceptedPrerenderedWorkspaceRoutes({
        workspaceRoutes: ["(admin)/billing"],
        prerenderedPaths: ["/billing"],
        accepted: ["clients"],
      }),
      "a grouped route that is prerendered and unaccepted must be caught",
    ).toEqual(["(admin)/billing"]);

    expect(
      unacceptedPrerenderedWorkspaceRoutes({
        workspaceRoutes: ["(admin)/billing"],
        prerenderedPaths: ["/billing"],
        accepted: ["billing"],
      }),
      "the same route, accepted under its URL form, must pass",
    ).toEqual([]);
  });

  it("ignores prerendered routes that are not workspace routes", () => {
    expect(
      unacceptedPrerenderedWorkspaceRoutes({
        workspaceRoutes: ["clients"],
        prerenderedPaths: ["/clients", "/team", "/pricing"],
      }),
    ).toEqual([]);
  });

  /**
   * The accepted set is EXPOSURE, not design — and this checks it against the REAL
   * tree, which the first version did not: it called the function with an empty route
   * list, got an empty answer, and asserted that. It proved the shape of the call and
   * nothing about the list.
   */
  it("carries only routes that still exist, so the list cannot rot", () => {
    const WS = path.resolve(
      path.dirname(fileURLToPath(import.meta.url)),
      "..",
      "app",
      "(workspace)",
    );
    const real = new Set(walkAppRoutes(WS).map((r: string) => urlRoute(r)));
    const vanished = ACCEPTED_PRERENDERED_WORKSPACE_ROUTES.filter(
      (r: string) => !real.has(r),
    );
    expect(
      vanished,
      `these accepted baseline entries name routes that no longer exist: ${vanished.join(", ")}`,
    ).toEqual([]);
    expect(new Set(ACCEPTED_PRERENDERED_WORKSPACE_ROUTES).size).toBe(
      ACCEPTED_PRERENDERED_WORKSPACE_ROUTES.length,
    );
  });

  it("reports an accepted route that has stopped being prerendered", () => {
    expect(
      staleAcceptedRoutes({
        workspaceRoutes: ["clients", "lkpm"],
        prerenderedPaths: ["/clients"],
        accepted: ["clients", "lkpm"],
      }),
    ).toEqual(["lkpm"]);
    // and says nothing when the accepted route simply no longer exists as a route
    expect(
      staleAcceptedRoutes({
        workspaceRoutes: ["clients"],
        prerenderedPaths: ["/clients"],
        accepted: ["clients", "deleted-section"],
      }),
    ).toEqual([]);
  });
});
