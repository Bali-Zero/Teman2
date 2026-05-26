import { describe, expect, it } from "vitest";

import { normalizePhone, phoneSearchVariants } from "../bridge/phone.js";

describe("normalizePhone — Indonesian numbers", () => {
  it("normalises 0812 local form to canonical E.164 (11-digit national)", () => {
    expect(normalizePhone("0812 3456-7890")).toBe("+6281234567890");
  });

  it("normalises 628xxx without `+` to canonical E.164", () => {
    expect(normalizePhone("6281234567890")).toBe("+6281234567890");
  });

  it("keeps +628xxx canonical after stripping separators", () => {
    expect(normalizePhone("+62 812-3456-7890")).toBe("+6281234567890");
  });

  it("normalises the 00 international-dial prefix", () => {
    expect(normalizePhone("0062 812 3456 7890")).toBe("+6281234567890");
  });

  // (Removed 2026-05-26: regression test enshrined an operator typo,
  // real Adit phone per accounts.json is +628213454725 — 11 digits, not 12.
  // See cicatrix in bridge/phone.ts header.)

  it("preserves all 8 Bali Zero team numbers verbatim", () => {
    const team = [
      "+628213454725", // Adit
      "+628213454727", // Vino
      "+628213454723", // Sahira
      "+6282326357501", // Krisna
      "+628133946856", // Surya
      "+628213454721", // Ari
      "+628213454726", // Damar
      "+62881038467246", // Asya
    ];
    for (const n of team) expect(normalizePhone(n)).toBe(n);
  });
});

describe("normalizePhone — international numbers", () => {
  it("preserves Italian +39 numbers", () => {
    expect(normalizePhone("+393398745516")).toBe("+393398745516");
  });

  it("preserves Australian +61 numbers", () => {
    expect(normalizePhone("+61401877755")).toBe("+61401877755");
  });

  it("preserves Saudi +966 numbers", () => {
    expect(normalizePhone("+966566272811")).toBe("+966566272811");
  });

  it("preserves Irish +353 numbers", () => {
    expect(normalizePhone("+353894477906")).toBe("+353894477906");
  });
});

describe("normalizePhone — fail-safe (no fake country code on garbage)", () => {
  it("rejects WhatsApp LID identifiers (NOT phones) without injecting +62 (regression for the @lid 17-18 digit bug)", () => {
    // Pre-v2: `224112131756075` → `+62224112131756075` (fake 18-digit E.164).
    // Post-v2: libphonenumber rejects → "" (empty, fail-safe).
    expect(normalizePhone("224112131756075")).toBe("");
    expect(normalizePhone("179065826877524")).toBe("");
    expect(normalizePhone("280650426929268")).toBe("");
  });

  it("returns empty string for null / undefined / empty", () => {
    expect(normalizePhone(null)).toBe("");
    expect(normalizePhone(undefined)).toBe("");
    expect(normalizePhone("")).toBe("");
    expect(normalizePhone("   ")).toBe("");
  });

  it("returns empty string for clearly invalid digit strings", () => {
    expect(normalizePhone("abc")).toBe("");
    expect(normalizePhone("1")).toBe("");
  });
});

describe("phoneSearchVariants", () => {
  it("emits canonical, digit-only, and local Indonesia variants for legacy CRM rows", () => {
    expect(phoneSearchVariants("0812 3456 7890")).toEqual([
      "+6281234567890",
      "6281234567890",
      "081234567890",
    ]);
  });

  it("emits only canonical + digit-only for non-Indonesia numbers", () => {
    expect(phoneSearchVariants("+393398745516")).toEqual([
      "+393398745516",
      "393398745516",
    ]);
  });

  it("returns empty array on invalid input", () => {
    expect(phoneSearchVariants("224112131756075")).toEqual([]);
    expect(phoneSearchVariants(null)).toEqual([]);
  });
});
