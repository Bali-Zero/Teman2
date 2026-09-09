import { describe, expect, it } from "vitest";

import {
  E33E_LIVE_PRICE_KEY,
  E33F_OFFSHORE_LIVE_PRICE_KEY,
  E33F_ONSHORE_LIVE_PRICE_KEY,
  E33_LIVE_PRICE_KEY,
  resolveSecondHomePriceKey,
} from "../pricing-key";

describe("resolveSecondHomePriceKey", () => {
  it("resolves base E33 to its 5-year PricingTool row", () => {
    expect(resolveSecondHomePriceKey("E33", "abroad")).toBe(E33_LIVE_PRICE_KEY);
  });

  it("regression: resolves E33E to the senior row, never the base E33 row", () => {
    const key = resolveSecondHomePriceKey("E33E", "in_indonesia");

    expect(key).toBe(E33E_LIVE_PRICE_KEY);
    expect(key).not.toBe(E33_LIVE_PRICE_KEY);
  });

  it("resolves E33F abroad to the offshore row", () => {
    expect(resolveSecondHomePriceKey("E33F", "abroad")).toBe(
      E33F_OFFSHORE_LIVE_PRICE_KEY,
    );
  });

  it("resolves E33F in Indonesia to the Altus/onshore row", () => {
    expect(resolveSecondHomePriceKey("E33F", "in_indonesia")).toBe(
      E33F_ONSHORE_LIVE_PRICE_KEY,
    );
  });

  it("abstains for E33F when location is unknown", () => {
    expect(resolveSecondHomePriceKey("E33F", null)).toBeNull();
  });

  it("abstains when the verdict has no product", () => {
    expect(resolveSecondHomePriceKey(null, "abroad")).toBeNull();
  });
});
