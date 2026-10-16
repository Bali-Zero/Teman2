/**
 * Signed rule-pack stay-policy census (PR-7 follow-up / E33 closing PR).
 *
 * Dynamically loads every `rulepack-prod-NNN.signed.json` on disk, reads
 * `.payload` only, selects the `PRODUCTION` pack with the highest numeric
 * `payload.sequence`, and verifies that every product's `stay_policy` +
 * `extension_policy` parses through `parseVisaOracleEvaluateResponse` and
 * `buildEngineOutcome` without throwing. Pricing in this census is synthetic
 * (a price is faked for products whose `pricing_key` is `null`).
 *
 * Permit-length `duration` is verified across two branches:
 * - duration-option group: products with `duration_options` produce
 *   `duration.selectedDays` equal to the first option's days and an `options`
 *   list matching the pack's `duration_options` days;
 * - stay-policy-fallback group: products without `duration_options` produce a
 *   permit-length `duration` when `stay_policy.kind === "FIXED_DAYS"` with
 *   `minimum_days === maximum_days` in `{365, 1825}`, and `undefined`
 *   otherwise.
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { describe, expect, it } from "vitest";
import { buildEngineOutcome } from "./engine-adapter";
import { parseVisaOracleEvaluateResponse } from "./engine-response";
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
  duration_options?: {
    days: number;
    pricing_key: { category: string; item_key: string };
  }[];
  stay_policy: PackStayPolicy;
  extension_policy: PackExtensionPolicy;
}

interface PackPayload {
  environment: string;
  sequence: number;
  products: PackProduct[];
}

interface LoadedProductionPack {
  file: string;
  payload: PackPayload;
}

/**
 * Loads every `rulepack-prod-NNN.signed.json` in `names`, reads `.payload`
 * only, and keeps those with `payload.environment === "PRODUCTION"`.
 */
function loadProductionPacks(names: string[]): LoadedProductionPack[] {
  const packs: LoadedProductionPack[] = [];
  for (const file of names) {
    if (!SIGNED.test(file)) continue;
    const raw = JSON.parse(
      fs.readFileSync(path.join(PACKS_DIR, file), "utf8"),
    ) as { payload: PackPayload };
    const { payload } = raw;
    if (
      payload.environment === "PRODUCTION" &&
      typeof payload.sequence === "number"
    ) {
      packs.push({ file, payload });
    }
  }
  return packs;
}

/**
 * Selects the PRODUCTION pack with the highest `payload.sequence` and throws
 * if two files share that maximum.
 */
function selectHighestProductionPack(
  packs: LoadedProductionPack[],
): LoadedProductionPack {
  if (packs.length === 0) {
    throw new Error(
      "no PRODUCTION rulepack-prod-NNN.signed.json found on disk",
    );
  }
  let best = packs[0];
  let maxCount = 1;
  for (let i = 1; i < packs.length; i += 1) {
    const current = packs[i];
    if (current.payload.sequence > best.payload.sequence) {
      best = current;
      maxCount = 1;
    } else if (current.payload.sequence === best.payload.sequence) {
      maxCount += 1;
    }
  }
  if (maxCount > 1) {
    throw new Error(
      `multiple PRODUCTION packs share highest sequence ${best.payload.sequence}`,
    );
  }
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
const productionPacks = loadProductionPacks(packNames);
const chosenPack = selectHighestProductionPack(productionPacks);
const allProducts = chosenPack.payload.products;
const productsWithStayPolicy = allProducts.filter(
  (product) => product.stay_policy != null,
);
const censusTable = productsWithStayPolicy;

describe(`signed rule-pack stay_policy census (${chosenPack.file})`, () => {
  it.each(censusTable)(
    "parses and builds outcome for $product_code ($stay_policy.kind $stay_policy.minimum_days to $stay_policy.maximum_days)",
    (product) => {
      const hasDurationOptions =
        product.duration_options != null && product.duration_options.length > 0;
      const pricingKey = hasDurationOptions
        ? product.duration_options![0].pricing_key
        : (product.pricing_key ?? {
            category: "visa",
            item_key: product.product_code,
          });
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
      if (hasDurationOptions) {
        const firstOption = product.duration_options![0];
        response.display.candidates[0].selected_duration_days =
          firstOption.days;
        response.display.candidates[0].duration_options =
          product.duration_options!.map((option, index) => ({
            days: option.days,
            pricing_key: option.pricing_key,
            amount_idr: null,
            status: "AVAILABLE",
            reason_code: "PRICE_AVAILABLE",
            selected: index === 0,
          }));
      }

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

      if (hasDurationOptions) {
        // Duration-option group: E31-family products with explicit duration_options.
        const firstOption = product.duration_options![0];
        expect(candidate.duration).toBeDefined();
        expect(candidate.duration?.selectedDays).toBe(firstOption.days);
        expect(
          candidate.duration?.options.map((option) => option.days),
        ).toEqual(product.duration_options!.map((option) => option.days));
      } else {
        // Stay-policy-fallback group: products without duration_options.
        const {
          kind,
          minimum_days: minDays,
          maximum_days: maxDays,
        } = product.stay_policy;
        const expectsPermitLength =
          kind === "FIXED_DAYS" &&
          minDays === maxDays &&
          (maxDays === 365 || maxDays === 730 || maxDays === 1825);

        if (expectsPermitLength) {
          expect(candidate.duration).toBeDefined();
          expect(candidate.duration?.selectedDays).toBe(maxDays);
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
      }
    },
  );

  it("selects the highest-sequence signed pack on disk and covers every product", () => {
    const productionSequences = productionPacks.map(
      (pack) => pack.payload.sequence,
    );
    expect(productionSequences.length).toBeGreaterThan(0);
    expect(chosenPack.payload.sequence).toBe(Math.max(...productionSequences));
    const fileMatch = SIGNED.exec(chosenPack.file);
    expect(fileMatch).not.toBeNull();
    expect(Number(fileMatch?.[1])).toBe(chosenPack.payload.sequence);

    expect(allProducts.length).toBeGreaterThanOrEqual(1);
    expect(productsWithStayPolicy.length).toBe(allProducts.length);
    expect(
      new Set(allProducts.map((product) => product.product_code)).size,
    ).toBe(allProducts.length);
    expect(censusTable.length).toBe(allProducts.length);
    expect(censusTable.length).toBe(productsWithStayPolicy.length);
  });
});
