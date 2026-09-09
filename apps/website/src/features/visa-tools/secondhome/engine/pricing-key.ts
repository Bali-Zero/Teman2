/**
 * Second Home Studio — E33 PricingTool identity, hoisted out of
 * SecondHomeLanding.tsx (Phase B) so the Studio's verdict-page price block
 * resolves the exact same PricingTool row, via the exact same
 * `usePricingData` identity, as the landing page (CLAUDE.md §8 rule 11 —
 * PricingTool only, never hardcoded).
 *
 * Values MUST stay byte-identical to what SecondHomeLanding.tsx used to
 * declare locally — its own page.test.tsx resolves the expected price via
 * these same literal category/key strings independently (it does not
 * import this module), so any drift here that changed the values would
 * fail that test.
 */
import type { Location, Verdict } from "./types";

export const E33_LIVE_PRICE_KEY = "E33 Second Home (5 Years)";
export const E33E_LIVE_PRICE_KEY = "E33E Second Home Senior (5 Years)";
export const E33F_OFFSHORE_LIVE_PRICE_KEY =
  "E33F Second Home Senior (1 Year, Offshore)";
export const E33F_ONSHORE_LIVE_PRICE_KEY =
  "E33F Second Home Senior (1 Year, Altus/Onshore)";
export const E33_LIVE_PRICE_CATEGORY = "kitas_permits";

/** Resolve the exact PricingTool identity for the Studio verdict. */
export function resolveSecondHomePriceKey(
  product: Verdict["product"],
  location: Location | null,
): string | null {
  switch (product) {
    case "E33":
      return E33_LIVE_PRICE_KEY;
    case "E33E":
      return E33E_LIVE_PRICE_KEY;
    case "E33F":
      if (location === "abroad") return E33F_OFFSHORE_LIVE_PRICE_KEY;
      if (location === "in_indonesia") return E33F_ONSHORE_LIVE_PRICE_KEY;
      // Offshore and onshore are distinct products: without location, abstain.
      return null;
    case null:
      return null;
  }
}
