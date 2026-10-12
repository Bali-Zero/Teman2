import { describe, expect, it } from "vitest";
import { genderCode } from "./gender";

describe("genderCode — both spellings stored in clients.gender read the same", () => {
  it("OCR spelling", () => {
    expect(genderCode("M")).toBe("M");
    expect(genderCode("F")).toBe("F");
  });

  it("PATCH spelling (ClientUpdate.normalize_gender)", () => {
    expect(genderCode("male")).toBe("M");
    expect(genderCode("female")).toBe("F");
    expect(genderCode(" Female ")).toBe("F");
  });

  it("not set / unknown", () => {
    expect(genderCode(undefined)).toBeNull();
    expect(genderCode(null)).toBeNull();
    expect(genderCode("")).toBeNull();
    expect(genderCode("other")).toBeNull();
  });
});
