import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { FORBIDDEN_PATTERNS } from "@/lib/secondhome-studio/claim-patterns";
import {
  decideFact,
  EDITORIAL_HOLDS,
  FACT_GROUP,
  renderedFactStrings,
  shelfFacts,
  tripsClaimGuard,
} from "../room/shelf-facts";
import { E33_FACTS, E33_FACT_REGISTRY_META } from "./e33-facts";

const REGISTRY = resolve(
  __dirname,
  "../../../../../../../../research/secondhome/e33-fact-registry.json",
);

const shown = shelfFacts().flatMap((group) => group.facts);

describe("e33-facts.ts is a verbatim copy of the registry on disk", () => {
  it("every fact, field for field, in registry order", () => {
    const registry = JSON.parse(readFileSync(REGISTRY, "utf-8"));
    expect(E33_FACTS).toEqual(registry.facts);
    expect(E33_FACT_REGISTRY_META.version).toBe(registry.version);
  });

  it("every registry id has a shelf group (a new fact cannot fall through silently)", () => {
    for (const fact of E33_FACTS) {
      expect(FACT_GROUP, fact.id).toHaveProperty(fact.id);
    }
  });
});

describe("the Facts drawer shows only what the claim guard allows", () => {
  it("the forbidden-claims regex, run over every string the drawer renders, finds nothing", () => {
    const strings = shown.flatMap(renderedFactStrings);
    expect(strings.length).toBeGreaterThan(20);
    for (const text of strings) {
      for (const [name, pattern] of Object.entries(FORBIDDEN_PATTERNS)) {
        expect(pattern.test(text), `${name} fired on: ${text}`).toBe(false);
      }
      expect(tripsClaimGuard(text), text).toBe(false);
    }
  });

  it("guilt: the registry DOES carry strings the guard catches, and those facts are withheld", () => {
    const caught = E33_FACTS.filter(
      (fact) =>
        (fact.status === "confirmed" || fact.status === "pending") &&
        renderedFactStrings(fact).some(tripsClaimGuard),
    ).map((fact) => fact.id);
    // Pinned so a registry change that moves this set is a visible diff.
    expect(caught.sort()).toEqual(
      [
        "bsi_sharia_accepted",
        "e33f_requirements",
        "pnbp_5y_amount",
        "pnbp_5y_amount_and_refundability",
        "split_deposit_accepted",
        "usd_deposit_rates_and_lps_cap_confirmation",
      ].sort(),
    );
    for (const id of caught) {
      expect(shown.map((f) => f.id)).not.toContain(id);
    }
  });

  it("only confirmed and pending facts reach the shelf; disputed and unknown never do", () => {
    expect(shown.every((f) => f.status === "confirmed" || f.status === "pending")).toBe(true);
    expect(shown.some((f) => f.status === "confirmed")).toBe(true);
    expect(shown.some((f) => f.status === "pending")).toBe(true);
    for (const fact of E33_FACTS.filter(
      (f) => f.status === "disputed" || f.status === "unknown",
    )) {
      expect(decideFact(fact)).toEqual({ shown: false, reason: "status" });
    }
  });

  it("editorial holds are withheld with their reason", () => {
    for (const id of Object.keys(EDITORIAL_HOLDS)) {
      const fact = E33_FACTS.find((f) => f.id === id);
      expect(fact, id).toBeDefined();
      expect(shown.map((f) => f.id)).not.toContain(id);
    }
  });

  it("within a group, confirmed facts come before open questions", () => {
    for (const { facts } of shelfFacts()) {
      const firstPending = facts.findIndex((f) => f.status === "pending");
      if (firstPending === -1) continue;
      expect(facts.slice(firstPending).every((f) => f.status === "pending")).toBe(true);
    }
  });
});
