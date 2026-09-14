import { navigation, routeTitles } from "./navigation";

/**
 * `/obligations` shipped in the "Work" nav group (#6209) without a
 * routeTitles entry, so getRouteTitle() in (workspace)/layout.tsx and
 * PortalHeader/workspace Header fell through to the generic "Workspace"
 * fallback instead of naming the page. "Work" no longer exists as a group —
 * SAETTA-R19K K1c-bis regrouped `navigation` into six titled sections for
 * the rail (DESK, CLIENT WORK, OPERATIONS, INTELLIGENCE, PEOPLE, SYSTEM) —
 * so this suite is re-pinned onto ALL six visible sections instead of one
 * named group. That is a STRICTLY STRONGER guard than the original: every
 * new item in any visible section, not just "Work", now has to carry a
 * routeTitles entry or this test fails.
 */
const SECTION_TITLES = [
  "DESK",
  "CLIENT WORK",
  "OPERATIONS",
  "INTELLIGENCE",
  "PEOPLE",
  "SYSTEM",
];

const visibleSections = navigation.filter((section) => !section.ownerOnly);

describe("navigation — the six visible rail sections", () => {
  it("finds the six section titles, in order (the probe can produce a positive)", () => {
    expect(visibleSections.map((section) => section.title)).toEqual(
      SECTION_TITLES,
    );
  });

  it("every internal, non-external href in every visible section has a routeTitles entry", () => {
    const missing = visibleSections
      .flatMap((section) => section.items)
      .filter((item) => !item.external)
      .map((item) => item.href)
      .filter((href) => !routeTitles[href]);
    expect(missing).toEqual([]);
  });

  it("/obligations names the page instead of falling back to Workspace", () => {
    expect(routeTitles["/obligations"]).toBe("Obligations");
  });

  it("has exactly 13 visible non-ownerOnly items, because the rail numbers them 01-13", () => {
    const count = visibleSections.reduce(
      (total, section) => total + section.items.length,
      0,
    );
    expect(count).toBe(13);
  });

  it("GUILT: the missing-routeTitle detector fires on a planted href without an entry", () => {
    const planted = visibleSections
      .flatMap((section) => section.items)
      .filter((item) => !item.external)
      .map((item) => item.href)
      .concat("/planted-route-with-no-title")
      .filter((href) => !routeTitles[href]);
    expect(planted).toEqual(["/planted-route-with-no-title"]);
  });
});
