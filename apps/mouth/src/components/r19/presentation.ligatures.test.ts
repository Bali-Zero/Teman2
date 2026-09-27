import { describe, expect, it } from "vitest";
import { R19_VARS } from "./presentation";

describe("R19_VARS", () => {
  it("turns common ligatures off so '(c)' never renders as '©'", () => {
    expect(R19_VARS.fontVariantLigatures).toBe("no-common-ligatures");
  });
});
