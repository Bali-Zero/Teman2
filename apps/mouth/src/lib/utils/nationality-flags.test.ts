import { describe, it, expect } from "vitest";
import { NATIONALITY_FLAGS, getCountryFlag } from "./nationality-flags";

describe("NATIONALITY_FLAGS", () => {
  it("contains expected country entries", () => {
    expect(NATIONALITY_FLAGS["Italian"]).toBe("\u{1F1EE}\u{1F1F9}");
    expect(NATIONALITY_FLAGS["Indonesia"]).toBe("\u{1F1EE}\u{1F1E9}");
    expect(NATIONALITY_FLAGS["USA"]).toBe("\u{1F1FA}\u{1F1F8}");
  });

  it("maps both nationality adjective and country name", () => {
    expect(NATIONALITY_FLAGS["German"]).toBeDefined();
    expect(NATIONALITY_FLAGS["Germany"]).toBeDefined();
    expect(NATIONALITY_FLAGS["German"]).toBe(NATIONALITY_FLAGS["Germany"]);
  });
});

describe("getCountryFlag", () => {
  it("returns null for null/undefined/empty", () => {
    expect(getCountryFlag(null)).toBeNull();
    expect(getCountryFlag(undefined)).toBeNull();
    expect(getCountryFlag("")).toBeNull();
  });

  it("finds exact match", () => {
    expect(getCountryFlag("Italian")).toBe("\u{1F1EE}\u{1F1F9}");
    expect(getCountryFlag("Australia")).toBe("\u{1F1E6}\u{1F1FA}");
  });

  it("finds title-case match", () => {
    // "italian" -> title case "Italian" -> found
    expect(getCountryFlag("italian")).toBe("\u{1F1EE}\u{1F1F9}");
  });

  it("finds case-insensitive match for multi-word keys", () => {
    expect(getCountryFlag("united states")).toBe("\u{1F1FA}\u{1F1F8}");
    expect(getCountryFlag("SOUTH KOREA")).toBe("\u{1F1F0}\u{1F1F7}");
  });

  it("returns null for unknown nationality", () => {
    expect(getCountryFlag("Atlantean")).toBeNull();
    expect(getCountryFlag("Martian")).toBeNull();
  });

  it("handles special entries like British Citizen", () => {
    expect(getCountryFlag("British Citizen")).toBe("\u{1F1EC}\u{1F1E7}");
  });
});
