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
export const E33_LIVE_PRICE_KEY = "E33 Second Home (5 Years)";
export const E33_LIVE_PRICE_CATEGORY = "kitas_permits";
