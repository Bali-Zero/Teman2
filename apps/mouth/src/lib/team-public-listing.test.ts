import { describe, it, expect } from "vitest";
import { TEAM_ROSTER, PUBLIC_ROSTER, rosterBySlug } from "@/data/team-roster";
import {
  PUBLIC_EXCLUDED_SLUGS,
  isPubliclyListed,
  isPublicSlug,
  publicEntries,
  publicRoster,
} from "./team-public-listing";

describe("team public listing filter", () => {
  it("pins every excluded slug to a real roster slug", () => {
    // The tripwire for the failure mode that makes this whole module a silent
    // no-op: a slug that matches nobody (a rename, or the `faysha` spelling that
    // the email prefix uses) would exclude nothing and every other test here
    // would still pass.
    const rosterSlugs = new Set(TEAM_ROSTER.map((m) => m.slug));
    for (const slug of PUBLIC_EXCLUDED_SLUGS) {
      expect(rosterSlugs.has(slug), `${slug} is not a roster slug`).toBe(true);
      expect(rosterBySlug(slug)).toBeDefined();
    }
  });

  it("drops exactly the excluded people from the public roster", () => {
    const names = publicRoster().map((m) => m.name);
    expect(names).not.toContain("Faisha");
    expect(names).not.toContain("Sahira");
    expect(publicRoster()).toHaveLength(PUBLIC_ROSTER.length - 2);
    // everyone else survives, in roster order
    expect(names).toEqual(
      PUBLIC_ROSTER.filter(
        (m) => m.slug !== "faisha" && m.slug !== "sahira",
      ).map((m) => m.name),
    );
    expect(names).toContain("Kadek");
    expect(names).toContain("Rina");
  });

  it("leaves the internal record intact", () => {
    // The roster is the internal SSOT: the excluded people are still resolvable
    // by slug, with their real name, role and photo.
    expect(rosterBySlug("sahira")?.name).toBe("Sahira");
    expect(rosterBySlug("faisha")?.name).toBe("Faisha");
    expect(rosterBySlug("faisha")?.role).toBe("Tax Care");
    expect(TEAM_ROSTER).toHaveLength(20);
  });

  it("honours publicListed:false as well as the excluded slugs", () => {
    expect(isPubliclyListed({ slug: "adit" })).toBe(true);
    expect(isPubliclyListed({ slug: "sahira" })).toBe(false);
    expect(isPubliclyListed({ slug: "faisha" })).toBe(false);
    // a member the roster itself hides, whichever slug it carries
    expect(isPubliclyListed({ slug: "adit", publicListed: false })).toBe(false);
  });

  it("keeps an entry that has no slug", () => {
    // The /team page renders a person who is not in the roster (the Zero entry)
    // through nameOverride; a slug-keyed filter must not drop it.
    const entries = [
      { slug: "zainal" },
      { nameOverride: "Zero" },
      { slug: "sahira" },
    ];
    expect(publicEntries(entries)).toEqual([
      { slug: "zainal" },
      { nameOverride: "Zero" },
    ]);
  });

  it("drops a slug-less entry that names an excluded person", () => {
    // The hole this closes: an editorial entry is free-form, so a hand-written
    // one could re-publish an excluded person by spelling their NAME instead of
    // their slug — and a slug-keyed filter would wave it through. The names are
    // derived from the roster, so they cannot drift from the slugs above.
    const entries = [
      { nameOverride: "Zero" },
      { nameOverride: "Faisha" },
      { nameOverride: "  sahira  " },
      { nameOverride: "faisha" },
      { slug: "kadek" },
    ];
    expect(publicEntries(entries)).toEqual([
      { nameOverride: "Zero" },
      { slug: "kadek" },
    ]);
  });

  it("drops an entry whose nameOverride names an excluded person EVEN WITH an allowed slug", () => {
    // The short-circuit hole: `{ slug: "kadek", nameOverride: "Faisha" }` carries a
    // slug that is perfectly allowed, and a consumer renders the override — so a
    // slug-first filter would publish the excluded person under a clean slug.
    const entries = [
      { slug: "kadek", nameOverride: "Faisha" },
      { slug: "angel", nameOverride: "Angel" },
      { slug: "asya" },
    ];
    expect(publicEntries(entries)).toEqual([
      { slug: "angel", nameOverride: "Angel" },
      { slug: "asya" },
    ]);
  });

  it("matches slugs and names regardless of case, padding or unicode width", () => {
    expect(isPublicSlug("Faisha")).toBe(false);
    expect(isPublicSlug("SAHIRA")).toBe(false);
    expect(isPublicSlug("  faisha  ")).toBe(false);
    expect(isPublicSlug("\uFF26\uFF41\uFF49\uFF53\uFF48\uFF41")).toBe(false); // fullwidth "Faisha"
    expect(isPubliclyListed({ slug: "FAISHA" })).toBe(false);
    expect(
      publicEntries([{ nameOverride: "\uFF33\uFF41\uFF48\uFF49\uFF52\uFF41" }]), // fullwidth "Sahira"
    ).toEqual([]);
    // and the people who stay, stay
    expect(isPublicSlug("Kadek")).toBe(true);
    expect(isPublicSlug("RINA")).toBe(true);
  });

  it("keeps an unknown slug (not a roster person, not this module's decision)", () => {
    expect(isPublicSlug("someone-not-in-the-roster")).toBe(true);
  });

  it("preserves order and identity of the entries it keeps", () => {
    const entries = [
      { slug: "angel", tag: 1 },
      { slug: "faisha", tag: 2 },
      { slug: "kadek", tag: 3 },
    ];
    expect(publicEntries(entries).map((e) => e.tag)).toEqual([1, 3]);
  });
});
