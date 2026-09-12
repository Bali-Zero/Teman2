import { describe, it, expect } from "vitest";
import { TEAM_ROSTER } from "@/data/team-roster";
import {
  teamPhotoMap,
  taxConsultants,
  TAX_CONSULTANTS,
} from "./roster-directory";

/**
 * The photo map used to be sixteen lines written by hand in a `"use client"` page,
 * which is how staff names ended up in that route's public chunk. It is derived now
 * — and a derivation can silently produce LESS than the table it replaced, which
 * nobody notices because the symptom is a blank avatar on an internal page.
 *
 * So the historical keys are pinned here. This list is what the hand-written map
 * contained at the commit this change replaced it; the derived map must still
 * answer for every one of them.
 */
const KEYS_THE_HANDWRITTEN_MAP_HAD = [
  "adit",
  "krisna",
  "ari",
  "ari.firda",
  "dea",
  "sahira",
  "surya",
  "damar",
  "asya",
  "angel",
  "veronika",
  "faisha",
  "dewaayu",
  "dewa.ayu",
  "candra",
  "subhi",
] as const;

describe("workspace roster directory", () => {
  it("still answers for every key the hand-written photo map had", () => {
    const map = teamPhotoMap();
    const missing = KEYS_THE_HANDWRITTEN_MAP_HAD.filter((k) => !map[k]);
    expect(missing).toEqual([]);
  });

  it("keeps the two email aliases the roster cannot express", () => {
    const map = teamPhotoMap();
    // `slug` and email prefix are not the same thing in this organisation — six
    // roster entries disagree — so these two cannot be derived and are explicit.
    expect(map["ari.firda"]).toBe(map["ari"]);
    expect(map["dewa.ayu"]).toBe(map["dewaayu"]);
  });

  it("derives from the roster, so a portrait has one source of truth", () => {
    const map = teamPhotoMap();
    for (const m of TEAM_ROSTER) {
      if (m.photo) expect(map[m.slug], `${m.slug}`).toBe(m.photo);
      else expect(map[m.slug], `${m.slug} has no portrait`).toBeUndefined();
    }
  });

  it("does NOT derive the tax-consultant values — the backend constrains them", () => {
    // Migration 093 carries a CHECK over exactly these five addresses and the form
    // submits the value verbatim. The ROSTER DISAGREES with two of them, so
    // deriving would have changed what gets written:
    //   roster faysha.tax@…  vs  constraint faisha.tax@…
    //   roster tax@…         vs  constraint veronika.tax@…
    // This test exists to keep someone from "tidying" the list into a derivation.
    expect(TAX_CONSULTANTS.map((c) => c.value)).toEqual([
      "veronika.tax@balizero.com",
      "kadek.tax@balizero.com",
      "dewaayu.tax@balizero.com",
      "angel.tax@balizero.com",
      "faisha.tax@balizero.com",
    ]);
    const rosterEmail = (slug: string) =>
      TEAM_ROSTER.find((m) => m.slug === slug)?.email;
    expect(rosterEmail("faisha")).toBe("faysha.tax@balizero.com");
    expect(rosterEmail("veronika")).toBe("tax@balizero.com");
    // …and those two are NOT what the dropdown submits. The disagreement is real
    // and is reported as a finding, not resolved here.
    expect(TAX_CONSULTANTS.map((c) => c.value)).not.toContain(
      rosterEmail("faisha"),
    );
  });

  it("hands the client a copy, not the module's own array", () => {
    const a = taxConsultants();
    a[0].label = "mutated";
    expect(taxConsultants()[0].label).toBe("Veronika");
  });
});
