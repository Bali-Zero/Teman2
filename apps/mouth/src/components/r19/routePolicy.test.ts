import { describe, expect, it } from "vitest";
import { isR19Route } from "./routePolicy";

describe("R19 public presentation boundary", () => {
  it.each([
    "/",
    "/news",
    "/team/",
    "/contact",
    "/services",
    "/services/visa",
    "/services/compliance",
    "/visas",
    "/visas/example",
    "/property/example",
    "/property/eligibility",
    "/tech/example",
    "/taxes/example",
    "/privacy",
    "/terms",
    "/cookies",
    "/about",
    "/careers",
    "/press",
  ])("converts %s", (path) => {
    expect(isR19Route(path)).toBe(true);
  });
  it.each([
    "/property",
    "/property/",
    "/v2",
    "/v2/news",
    "/visa-oracle",
    "/visa/second-home/studio",
    "/visa",
    "/kbli",
    "/taxes/gap",
    "/portal",
    "/login",
    "/unknown",
    "/services/visa/engine",
    "/v2/privacy",
    "/v2/terms",
    "/v2/cookies",
    "/v2/company/about",
    "/v2/company/careers",
    "/v2/company/press",
  ])("preserves %s", (path) => {
    expect(isR19Route(path)).toBe(false);
  });
});
