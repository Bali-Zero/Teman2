import { navigation, routeTitles } from "./navigation";

/**
 * `/obligations` shipped in the "Work" nav group (#6209) without a
 * routeTitles entry, so getRouteTitle() in (workspace)/layout.tsx and
 * PortalHeader/workspace Header fell through to the generic "Workspace"
 * fallback instead of naming the page. Pin every "Work" nav href against
 * routeTitles so the next new route can't ship the same gap silently.
 */
describe("routeTitles vs the Work nav group", () => {
  const workItems =
    navigation.find((section) => section.title === "Work")?.items ?? [];

  it("finds the Work group to check (the probe can produce a positive)", () => {
    expect(workItems.length).toBeGreaterThan(0);
  });

  it("every internal Work nav href has a routeTitles entry", () => {
    const missing = workItems
      .filter((item) => !item.external)
      .map((item) => item.href)
      .filter((href) => !routeTitles[href]);
    expect(missing).toEqual([]);
  });

  it("/obligations names the page instead of falling back to Workspace", () => {
    expect(routeTitles["/obligations"]).toBe("Obligations");
  });
});
