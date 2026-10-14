/**
 * Signed rule-pack stay-policy census (PR-7 follow-up / E33 closing PR).
 *
 * Dynamically loads the highest-sequence `rulepack-prod-NNN.signed.json` on
 * disk, reads `.payload.products` only, and verifies that every product's
 * `stay_policy` + `extension_policy` parses through
 * `parseVisaOracleEvaluateResponse` and `buildEngineOutcome` without throwing
 * and produces a permit-length `duration` if and only if
 * `stay_policy.kind === "FIXED_DAYS"` with `minimum_days === maximum_days` in
 * `{365, 1825}`.
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { describe, expect, it } from "vitest";
import { buildEngineOutcome } from "./engine-adapter";
import { parseVisaOracleEvaluateResponse } from "./engine-response";
import { translate } from "./i18n";
import { TEST_NOW, makeVisaOracleResponse } from "./visa-oracle-test-fixture";

const PACKS_DIR = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../../../../../backend-rag/backend/services/visa_engine/contracts/packs",
);

const SIGNED = /^rulepack-prod-(\d+)\.signed\.json$/;

interface PackStayPolicy {
  kind: string;
  minimum_days: number | null;
  maximum_days: number | null;
}

interface PackExtensionPolicy {
  status: "VERIFIED" | "UNKNOWN";
  reason_code: string | null;
  allowed: boolean;
  maximum_extensions: number;
  days_per_extension: number | null;
}

interface PackProduct {
  product_version_id: string;
  product_code: string;
  pricing_key: { category: string; item_key: string } | null;
  stay_policy: PackStayPolicy;
  extension_policy: PackExtensionPolicy;
}

/** The signed pack with the numerically highest NNN among `names`. */
function highestSignedPack(names: string[]): { file: string; seq: number } {
  let best: { file: string; seq: number } | null = null;
  for (const file of names) {
    const m = SIGNED.exec(file);
    if (!m) continue;
    const seq = Number(m[1]);
    if (best === null || seq > best.seq) best = { file, seq };
  }
  if (best === null) throw new Error("no rulepack-prod-NNN.signed.json found");
  return best;
}

function makePricedResponse(
  code = "E33F",
  amount = 14_000_000,
  pricingKey = { category: "visa", item_key: code },
) {
  const response = makeVisaOracleResponse("SUPPORTED_CANDIDATES");
  const candidate = response.display.candidates[0];
  response.decision.candidates[0].product_code = code;
  candidate.product_code = code;
  candidate.pricing = {
    status: "AVAILABLE",
    reason_code: "PRICE_AVAILABLE",
    evaluated_at: TEST_NOW,
    catalog_last_updated: "2026-08-03",
    catalog_sha256: "b".repeat(64),
    row_sha256: "c".repeat(64),
  };
  response.decision.quotes = [
    {
      quote_id: "55555555-5555-4555-8555-555555555555",
      product_version_id: candidate.product_version_id,
      product_code: code,
      status: "AVAILABLE",
      currency: "IDR",
      amount,
      pricing_key: pricingKey,
      catalog_version: "2026.08",
      catalog_sha256: "b".repeat(64),
      row_sha256: "c".repeat(64),
      quoted_at: TEST_NOW,
      valid_until: "2026-08-10T04:00:00Z",
      reason_code: "PRICE_AVAILABLE",
    },
  ];
  return response;
}

const packNames = fs.readdirSync(PACKS_DIR);
const chosenPack = highestSignedPack(packNames);
const packJson = JSON.parse(
  fs.readFileSync(path.join(PACKS_DIR, chosenPack.file), "utf8"),
) as { payload: { products: PackProduct[] } };
const allProducts = packJson.payload.products;
const productsWithStayPolicy = allProducts.filter(
  (product) => product.stay_policy != null,
);

describe(`signed rule-pack stay_policy census (${chosenPack.file})`, () => {
  const executedProductCodes = new Set<string>();

  it.each(productsWithStayPolicy)(
    "parses and builds outcome for $product_code ($stay_policy.kind $stay_policy.minimum_days..$stay_policy.maximum_days)",
    (product) => {
      executedProductCodes.add(product.product_code);
      const pricingKey = product.pricing_key ?? {
        category: "visa",
        item_key: product.product_code,
      };
      const response = makePricedResponse(
        product.product_code,
        14_000_000,
        pricingKey,
      );
      response.decision.candidates[0].product_version_id =
        product.product_version_id;
      response.display.candidates[0].product_version_id =
        product.product_version_id;
      response.decision.quotes[0].product_version_id =
        product.product_version_id;
      response.display.candidates[0].stay_policy = {
        stay: product.stay_policy,
        extension: product.extension_policy,
      };

      const parsed = parseVisaOracleEvaluateResponse(response);
      const outcome = buildEngineOutcome(parsed, {
        facts: { stay_days: "4000" },
      });
      if (outcome.state !== "SUPPORTED_CANDIDATES") {
        throw new Error(
          `expected SUPPORTED_CANDIDATES for ${product.product_code}`,
        );
      }

      const candidate = outcome.candidates[0];
      expect(candidate.code).toBe(product.product_code);
      expect(candidate.price).toMatchObject({
        status: "AVAILABLE",
        amount: 14_000_000,
      });

      const {
        kind,
        minimum_days: minDays,
        maximum_days: maxDays,
      } = product.stay_policy;
      const expectsPermitLength =
        kind === "FIXED_DAYS" &&
        minDays === maxDays &&
        (maxDays === 365 || maxDays === 1825);

      if (expectsPermitLength) {
        expect(candidate.duration).toBeDefined();
        expect(candidate.duration?.selectedDays).toBe(maxDays);
        const years = maxDays / 365;
        const enLabel = translate("en", "outcome.duration_years", {
          count: years,
        });
        const idLabel = translate("id", "outcome.duration_years", {
          count: years,
        });
        expect(enLabel.trim().length).toBeGreaterThan(0);
        expect(idLabel.trim().length).toBeGreaterThan(0);
        expect(enLabel).not.toBe(idLabel);
        expect(
          candidate.duration?.longerStay?.en.trim().length,
        ).toBeGreaterThan(0);
        expect(
          candidate.duration?.longerStay?.id.trim().length,
        ).toBeGreaterThan(0);
        if (candidate.duration?.renewal) {
          expect(candidate.duration.renewal.en.trim().length).toBeGreaterThan(
            0,
          );
          expect(candidate.duration.renewal.id.trim().length).toBeGreaterThan(
            0,
          );
        }
      } else {
        expect(candidate.duration).toBeUndefined();
      }
    },
  );

  it("selects the highest-sequence signed pack on disk and covers every product", () => {
    const sequences = packNames
      .map((name) => SIGNED.exec(name))
      .filter((m): m is RegExpExecArray => m !== null)
      .map((m) => Number(m[1]));
    expect(sequences.length).toBeGreaterThan(0);
    expect(chosenPack.seq).toBe(Math.max(...sequences));
    expect(chosenPack.file).toBe(
      `rulepack-prod-${String(chosenPack.seq).padStart(3, "0")}.signed.json`,
    );

    expect(allProducts.length).toBeGreaterThanOrEqual(1);
    expect(productsWithStayPolicy.length).toBe(allProducts.length);
    expect(executedProductCodes.size).toBe(productsWithStayPolicy.length);
  });
});
