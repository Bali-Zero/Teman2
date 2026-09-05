import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { backendPatterns } from "./secondhome-backend-patterns";

const source = readFileSync(
  join(
    dirname(fileURLToPath(import.meta.url)),
    "../../../backend-rag/backend/services/visa_check/e33_claim_guard.py",
  ),
  "utf8",
);

describe("Backend E33 vocabulary source reader", () => {
  it.each([
    ["second_home_first_grant_5_10_years", "Second Home 5-10 years"],
    ["idr_2m_fee_error", "E33 IDR 2,000,000"],
    ["e33_permits_local_work", "E33 allows you to work in Indonesia"],
    ["lps_full_coverage", "E33 LPS fully covers the deposit"],
    ["bsi_sharia_equivalence", "E33 BSI qualifies as a state-owned bank"],
    ["split_deposit_accepted", "E33 split the deposit"],
  ])("reads the actual %s pattern", (id, text) => {
    expect(backendPatterns(source).get(id)?.test(text)).toBe(true);
  });

  it("accepts clean text, blank lines and declaration comments", () => {
    for (const pattern of backendPatterns(source).values()) {
      expect(pattern.test("E33 requires individual review.")).toBe(false);
    }
    expect(
      backendPatterns(
        source.replace(
          '        "idr_2m_fee_error",',
          '        # declaration comment\n\n        "idr_2m_fee_error",',
        ),
      ),
    ).toEqual(backendPatterns(source));
  });

  it("reads changed source rather than a copied regex or fingerprint", () => {
    const changed = source.replace(
      'r"\\bIDR\\s*2[.,]?000[.,]?000\\b"',
      'r"\\bREVIEW_SENTINEL\\b"',
    );
    const pattern = backendPatterns(changed).get("idr_2m_fee_error")!;
    expect(pattern.test("REVIEW_SENTINEL")).toBe(true);
    expect(pattern.test("IDR 2,000,000")).toBe(false);
  });

  it("resolves raw concatenation, interpolations and doubled quantifier braces", () => {
    const pattern = backendPatterns(source).get("e33_permits_local_work")!;
    expect(pattern.source).not.toContain("{{");
    expect(pattern.source).not.toContain("{_NEG}");
    expect(pattern.test("Second Home allows you to work in Indonesia")).toBe(
      true,
    );
    expect(pattern.test("E33 does not allow you to work in Indonesia")).toBe(
      false,
    );
  });

  it.each([
    ["empty source", () => ""],
    ["unknown interpolation", (s: string) => s.replace("{_NEG}", "{_UNKNOWN}")],
    ["Python-only escape", (s: string) => s.replace('r"\\bUSD', 'r"\\AUSD')],
    [
      "nonliteral expression",
      (s: string) => s.replace('r"\\bUSD\\s*1[.,]?500\\b"', "load_pattern()"),
    ],
    [
      "duplicate ID",
      (s: string) =>
        s.replace('"idr_2m_fee_error",', '"split_deposit_accepted",'),
    ],
    [
      "changed factory flags",
      (s: string) =>
        s.replace(
          "regex=re.compile(raw, re.IGNORECASE)",
          "regex=re.compile(raw, re.ASCII)",
        ),
    ],
    [
      "reordered factory arguments",
      (s: string) =>
        s.replace("pattern_id: str, raw: str", "raw: str, pattern_id: str"),
    ],
    ["constant reassignment", (s: string) => s + '\n_NEG += r"extra"\n'],
    [
      "registry reassignment",
      (s: string) => s + "\nE33_FORBIDDEN_PATTERNS += ()\n",
    ],
    [
      "unconsumed call",
      (s: string) =>
        s.replace(
          '    _p(\n        "idr_2m_fee_error",',
          '    unknown_call(),\n    _p(\n        "idr_2m_fee_error",',
        ),
    ],
  ])("fails closed on %s", (_label, mutate) => {
    expect(() => backendPatterns(mutate(source))).toThrow(
      "Unsupported backend E33 vocabulary syntax",
    );
  });
});
