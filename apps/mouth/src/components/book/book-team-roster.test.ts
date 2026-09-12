import { describe, it, expect, beforeEach, vi } from "vitest";
import { PUBLIC_ROSTER } from "@/data/team-roster";

// The book derives its team grid at MODULE LOAD, so each case sets
// `extraExcluded` and imports fresh. Empty set → the real filter.
const extraExcluded = new Set<string>();

vi.mock("@/lib/team-public-listing", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/team-public-listing")>();
  return {
    ...actual,
    publicRoster: () =>
      actual.publicRoster().filter((m) => !extraExcluded.has(m.slug)),
  };
});

async function teamMembers() {
  const { TEAM_MEMBERS } = await import("./book-data");
  return TEAM_MEMBERS;
}

beforeEach(() => {
  vi.resetModules();
  extraExcluded.clear();
});

describe("book team grid (/book, /book/team)", () => {
  it("stops publishing the two people the owner excluded", async () => {
    // REGRESSION: this grid derived from PUBLIC_ROSTER, which only reads the
    // roster's publicListed flag — no member carries it, so the book kept showing
    // both of them (measured on the served site before this change).
    const names = (await teamMembers()).map((m) => m.name);
    expect(names).not.toContain("Faisha");
    expect(names).not.toContain("Sahira");
  });

  it("keeps everybody else, with their roster role and photo", async () => {
    const members = await teamMembers();
    expect(members).toHaveLength(PUBLIC_ROSTER.length - 2);

    const expected = PUBLIC_ROSTER.filter(
      (m) => m.slug !== "faisha" && m.slug !== "sahira",
    );
    expect(members.map((m) => m.name)).toEqual(expected.map((m) => m.name));
    expect(members.map((m) => m.role)).toEqual(expected.map((m) => m.role));
    expect(members.map((m) => m.photo)).toEqual(expected.map((m) => m.photo));
    expect(members.map((m) => m.department)).toEqual(
      expected.map((m) => m.dept),
    );
    expect(members.map((m) => m.name)).toContain("Kadek");
    expect(members.map((m) => m.name)).toContain("Rina");
  });

  it("drops a person the filter excludes, whoever it is", async () => {
    // Guilt probe: if this file goes back to reading the roster directly, the
    // filter stops being consulted and this case fails.
    extraExcluded.add("vino");
    const names = (await teamMembers()).map((m) => m.name);

    expect(names).not.toContain("Vino");
    expect(names).toContain("Damar");
  });

  it("leaves the rest of the book content alone", async () => {
    const { CHAPTERS, STATS, CONTACTS } = await import("./book-data");
    expect(CHAPTERS.map((c) => c.id)).toEqual([
      "cover",
      "manifesto",
      "origin",
      "team",
      "services",
      "impact",
      "technology",
      "contact",
    ]);
    expect(STATS.teamSize).toBe(22);
    expect(CONTACTS.email).toBe("info@balizero.com");
  });
});
