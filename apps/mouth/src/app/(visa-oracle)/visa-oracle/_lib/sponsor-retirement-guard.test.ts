import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { describe, expect, it } from "vitest";

// R3 (owner decision 2026-10-11): the retirement interview no longer asks
// `sponsor_category`, so `sponsor.type` stays UNKNOWN(NOT_ASKED) on that
// branch. That is only safe while NO rule covering RETIREMENT in the newest
// signed pack reads `sponsor.type`. This file holds that guard on its own so
// the CI observer can run exactly this file and require exactly its tests.

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PACKS_DIR = path.resolve(
  __dirname,
  "../../../../../../backend-rag/backend/services/visa_engine/contracts/packs",
);
const FACT = "sponsor.type";
const RETIREMENT_PRODUCTS = ["E33E", "E33F"];
const KNOWN_SCOPES = new Set(["PRODUCTS", "GLOBAL"]);

type PackRule = {
  rule_id: string;
  scope: string;
  product_version_ids?: string[];
};
type PackProduct = {
  product_code: string;
  product_version_id: string;
  covered_purposes?: string[];
};
type Pack = { sequence: number; rules: PackRule[]; products: PackProduct[] };

/**
 * The signed production pack with the highest N in its FILENAME. The payload
 * must be well-formed and carry `sequence === N`; anything else throws, so a
 * malformed newer pack can never silently leave an older one being scanned.
 */
function newestSignedPack(): Pack {
  const numbers = fs
    .readdirSync(PACKS_DIR)
    .map((name) => /^rulepack-prod-(\d+)\.signed\.json$/.exec(name))
    .filter((match): match is RegExpExecArray => match !== null)
    .map((match) => Number(match[1]));
  if (numbers.length === 0) throw new Error("no signed production pack found");
  const newest = Math.max(...numbers);
  const name = `rulepack-prod-${String(newest).padStart(3, "0")}.signed.json`;
  const envelope = JSON.parse(
    fs.readFileSync(path.join(PACKS_DIR, name), "utf-8"),
  ) as { payload?: Partial<Pack> };
  const payload = envelope.payload;
  if (
    !payload ||
    payload.sequence !== newest ||
    !Array.isArray(payload.rules) ||
    !Array.isArray(payload.products)
  ) {
    throw new Error(
      `${name}: payload is malformed or its sequence is not ${newest}`,
    );
  }
  return payload as Pack;
}

/** True if any string anywhere in the rule (fact refs, required_facts, ...) is the fact. */
function readsSponsorType(node: unknown): boolean {
  if (typeof node === "string") return node === FACT;
  if (Array.isArray(node)) return node.some(readsSponsorType);
  if (node !== null && typeof node === "object") {
    return Object.values(node as Record<string, unknown>).some(
      readsSponsorType,
    );
  }
  return false;
}

describe("sponsor.type x RETIREMENT — the omission is only safe while no rule reads it (R3)", () => {
  it("the retirement products E33E and E33F exist in the newest signed pack and both cover RETIREMENT", () => {
    const pack = newestSignedPack();
    for (const code of RETIREMENT_PRODUCTS) {
      const product = pack.products.find((p) => p.product_code === code);
      expect(
        product,
        `${code} missing from the newest signed pack`,
      ).toBeDefined();
      expect(product?.covered_purposes ?? []).toContain("RETIREMENT");
    }
  });

  it("no rule reading sponsor.type (anywhere in the rule) covers RETIREMENT (the interview no longer asks it)", () => {
    const pack = newestSignedPack();
    const retirementVersionIds = new Set(
      pack.products
        .filter((p) => p.covered_purposes?.includes("RETIREMENT"))
        .map((p) => p.product_version_id),
    );
    for (const code of RETIREMENT_PRODUCTS) {
      const product = pack.products.find((p) => p.product_code === code);
      expect(retirementVersionIds.has(product?.product_version_id ?? "")).toBe(
        true,
      );
    }
    // Fail on shapes this guard does not understand rather than skip them.
    for (const rule of pack.rules) {
      expect(
        KNOWN_SCOPES.has(rule.scope),
        `${rule.rule_id}: unknown scope ${rule.scope}`,
      ).toBe(true);
    }
    const sponsorRules = pack.rules.filter(readsSponsorType);
    // Guard the guard: a pack with no sponsor rule would pass vacuously.
    expect(sponsorRules.length).toBeGreaterThan(0);
    const covering = sponsorRules
      .filter(
        (rule) =>
          rule.scope !== "PRODUCTS" ||
          (rule.product_version_ids ?? []).some((id) =>
            retirementVersionIds.has(id),
          ),
      )
      .map((rule) => rule.rule_id);
    expect(
      covering,
      "a pack rule now reads sponsor.type for RETIREMENT: restore `sponsor_category` to the retirement question list in flow.ts (R3, 2026-10-11) instead of letting the interview dead-end on NEEDS_INPUT",
    ).toEqual([]);
  });

  it("the scan itself bites: a rule that reads sponsor.type in required_facts only is still detected", () => {
    expect(readsSponsorType({ required_facts: ["a", FACT] })).toBe(true);
    expect(readsSponsorType({ when: { all: [{ fact: FACT }] } })).toBe(true);
    expect(readsSponsorType({ when: { fact: "other.fact" } })).toBe(false);
  });
});
