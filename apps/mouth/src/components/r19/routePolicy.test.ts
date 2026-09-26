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
    "/tech/example",
    "/taxes/example",
  ])("converts %s", (path) => {
    expect(isR19Route(path)).toBe(true);
  });
  it.each([
    "/property",
    "/property/",
    "/property/eligibility",
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
  ])("preserves %s", (path) => {
    expect(isR19Route(path)).toBe(false);
  });
});
