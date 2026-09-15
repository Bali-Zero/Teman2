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
  "surya",
  "damar",
  "asya",
  "angel",
  "veronika",
  "dewaayu",
  "dewa.ayu",
  "candra",
  "subhi",
] as const;

/**
 * Two keys the hand-written map ALSO had, and that the derived map must now NOT
 * answer for. Their portraits were withdrawn from `public/` under the owner's
 * decision D6 (2026-09-15): the files were fetchable by anyone who guessed the URL,
 * and the URL was the person's name. The roster entries keep no `photo`, so these
 * members render the initials fallback on internal surfaces.
 *
 * Kept as a SEPARATE list rather than silently dropped from the one above: the
 * test above exists to catch a derivation that quietly loses a key, and removing
 * these two from it without saying why would be exactly that loss, committed by
 * hand. Here the absence is pinned as the decision it is — so restoring either
 * portrait turns this red and has to be done on purpose.
 */
const KEYS_WITHDRAWN_UNDER_D6 = ["faisha", "sahira"] as const;

describe("workspace roster directory", () => {
  it("still answers for every key the hand-written photo map had", () => {
    const map = teamPhotoMap();
    const missing = KEYS_THE_HANDWRITTEN_MAP_HAD.filter((k) => !map[k]);
    expect(missing).toEqual([]);
  });

  it("no longer answers for the two portraits withdrawn from public/ under D6", () => {
    const map = teamPhotoMap();
    const stillAnswering = KEYS_WITHDRAWN_UNDER_D6.filter((k) => map[k]);
    expect(
      stillAnswering,
      "a portrait withdrawn from public/ under D6 is back in the photo map — " +
        "restoring one is an owner decision, not a tidy-up",
    ).toEqual([]);
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

  /**
   * The invariant the copy above silently depends on.
   *
   * `taxConsultants()` copies with `TAX_CONSULTANTS.map((c) => ({ ...c }))`, and a
   * spread copies one level. That is a TRUE copy only while every field is a
   * primitive — which is the case today, `{ value: string; label: string }`.
   *
   * The test above cannot see the difference: it mutates `label`, a top-level
   * string, so it passes whether the copy is shallow or deep. Add one array or
   * object field — a permissions list, a locale map — and callers would start
   * sharing that reference with the module constant, on the server, with every
   * existing test still green.
   *
   * So the flatness is asserted directly. This is deliberately a test and not a
   * `structuredClone` in the function: the clone would make the copy correct while
   * leaving no trace that the constraint ever existed, so the next person to add a
   * nested field would learn nothing. A red test here fails at the moment that
   * decision is actually being made, and whoever is making it can then choose
   * between deep-copying and keeping the shape flat — with the trade-off in front
   * of them rather than behind them.
   */
  it("keeps every consultant field primitive, which is what makes a spread a copy", () => {
    // An ALLOW-list of primitive `typeof` results, not a deny-list of "object".
    // `typeof fn === "function"`, so a deny-list on "object" alone would wave a
    // method or closure straight through — and a spread copies that reference just
    // as it would an array. A refuter caught exactly that hole in the first draft.
    const PRIMITIVE = new Set([
      "string",
      "number",
      "boolean",
      "bigint",
      "symbol",
      "undefined",
    ]);

    const options = taxConsultants();
    // Without this, an empty table would make the loops below vacuous and the test
    // would pass having asserted nothing — also a refuter's catch.
    expect(options.length).toBeGreaterThan(0);

    let checked = 0;
    for (const option of options) {
      // Reflect.ownKeys, not Object.entries: a spread also copies enumerable
      // SYMBOL-keyed properties, and Object.entries cannot see them — so a
      // symbol-keyed array would have been shared by reference with this test green.
      for (const key of Reflect.ownKeys(option)) {
        const field = String(key);
        const value = (option as unknown as Record<PropertyKey, unknown>)[key];
        checked += 1;
        expect(
          value === null || PRIMITIVE.has(typeof value),
          `${field} is ${typeof value}, not a primitive — a spread no longer copies it`,
        ).toBe(true);
      }
    }
    expect(checked).toBeGreaterThan(0);
  });
});
