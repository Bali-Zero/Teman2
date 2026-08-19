import { describe, expect, it } from "vitest";

import {
  addEvidenceSchema,
  createCaseSchema,
  isForbiddenMetadataKey,
  normalizeMetadataKey,
} from "./secondhome.schemas";

describe("createCaseSchema", () => {
  it("accepts a minimal valid deposit-basis case", () => {
    const result = createCaseSchema.safeParse({
      client_id: 42,
      basis: "deposit",
    });
    expect(result.success).toBe(true);
  });

  it("accepts a property-basis case with practice link and owner email (schema stays permissive — the UI disables the property option, the backend enforces the 422)", () => {
    const result = createCaseSchema.safeParse({
      client_id: 42,
      basis: "property",
      practice_id: 7,
      owner_email: "ari@balizero.com",
    });
    expect(result.success).toBe(true);
  });

  it("rejects a non-positive client_id", () => {
    const result = createCaseSchema.safeParse({
      client_id: 0,
      basis: "deposit",
    });
    expect(result.success).toBe(false);
  });

  it("rejects an invalid basis value", () => {
    const result = createCaseSchema.safeParse({
      client_id: 1,
      basis: "cash", // not in the GuaranteeBasis enum
    });
    expect(result.success).toBe(false);
  });

  it("rejects dependent_code without principal_case_id (422 mirror)", () => {
    const result = createCaseSchema.safeParse({
      client_id: 1,
      basis: "deposit",
      dependent_code: "E31B",
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path.join("."));
      expect(paths).toContain("principal_case_id");
    }
  });

  it("rejects principal_case_id without dependent_code (422 mirror)", () => {
    const result = createCaseSchema.safeParse({
      client_id: 1,
      basis: "deposit",
      principal_case_id: "E33-2026-abc123",
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const paths = result.error.issues.map((i) => i.path.join("."));
      expect(paths).toContain("dependent_code");
    }
  });

  it("accepts a dependent case with BOTH dependent_code and principal_case_id", () => {
    const result = createCaseSchema.safeParse({
      client_id: 2,
      basis: "deposit",
      dependent_code: "E31E",
      principal_case_id: "E33-2026-abc123",
    });
    expect(result.success).toBe(true);
  });

  it("rejects an unknown dependent code", () => {
    const result = createCaseSchema.safeParse({
      client_id: 2,
      basis: "deposit",
      dependent_code: "E33S", // not in DEFAULT_DEPENDENT_CODES
      principal_case_id: "E33-2026-abc123",
    });
    expect(result.success).toBe(false);
  });

  it("rejects an invalid owner_email but allows empty string", () => {
    const bad = createCaseSchema.safeParse({
      client_id: 1,
      basis: "deposit",
      owner_email: "not-an-email",
    });
    expect(bad.success).toBe(false);

    const empty = createCaseSchema.safeParse({
      client_id: 1,
      basis: "deposit",
      owner_email: "",
    });
    expect(empty.success).toBe(true);
  });

  it("never carries a note field through to the parsed output (backend dropped it — 2026-08-19 reconciliation)", () => {
    const result = createCaseSchema.safeParse({
      client_id: 1,
      basis: "deposit",
      note: "should be stripped, not validated",
    } as unknown as Parameters<typeof createCaseSchema.safeParse>[0]);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data).not.toHaveProperty("note");
    }
  });
});

describe("no-custody metadata guard (mirrors validate_evidence_metadata)", () => {
  it("normalizes keys by stripping separators and lower-casing", () => {
    expect(normalizeMetadataKey("Account_Number")).toBe("accountnumber");
    expect(normalizeMetadataKey("deposit-amount")).toBe("depositamount");
    expect(normalizeMetadataKey("bank_name")).toBe("bankname");
  });

  it.each([
    "account_number",
    "AccountBalance",
    "deposit_amount",
    "IBAN",
    "swift_code",
    "nomor_rekening",
    "no_rek",
    "saldo",
    "jumlah_setoran",
  ])("flags %s as a forbidden custody-flavoured key", (key) => {
    expect(isForbiddenMetadataKey(key)).toBe(true);
  });

  it.each(["bank_name", "reference_number", "issuing_branch", "document_id"])(
    "allows %s as a legitimate reference-only key",
    (key) => {
      expect(isForbiddenMetadataKey(key)).toBe(false);
    },
  );
});

describe("addEvidenceSchema", () => {
  it("accepts a minimal valid bank-confirmation evidence entry", () => {
    const result = addEvidenceSchema.safeParse({
      kind: "bank_confirmation",
      document_ref: "drive:abc123",
    });
    expect(result.success).toBe(true);
  });

  it("accepts optional fields (issuing_party, dates, note)", () => {
    const result = addEvidenceSchema.safeParse({
      kind: "immigration_filing",
      document_ref: "drive:xyz789",
      issuing_party: "Bank Mandiri",
      issued_on: "2026-08-01",
      filed_on: "2026-08-05",
      note: "Filed at Ngurah Rai immigration office",
    });
    expect(result.success).toBe(true);
  });

  it("rejects an empty document_ref", () => {
    const result = addEvidenceSchema.safeParse({
      kind: "bank_confirmation",
      document_ref: "",
    });
    expect(result.success).toBe(false);
  });

  it("rejects an invalid evidence kind", () => {
    const result = addEvidenceSchema.safeParse({
      kind: "wire_transfer_receipt", // not an EvidenceKind
      document_ref: "drive:abc123",
    });
    expect(result.success).toBe(false);
  });

  it("rejects a malformed issued_on date", () => {
    const result = addEvidenceSchema.safeParse({
      kind: "bank_confirmation",
      document_ref: "drive:abc123",
      issued_on: "01/08/2026",
    });
    expect(result.success).toBe(false);
  });

  it("rejects metadata carrying a custody-flavoured key even though the UI never offers this field", () => {
    const result = addEvidenceSchema.safeParse({
      kind: "bank_confirmation",
      document_ref: "drive:abc123",
      metadata: { account_balance: "130000" },
    });
    expect(result.success).toBe(false);
  });

  it("accepts metadata carrying only reference-style keys", () => {
    const result = addEvidenceSchema.safeParse({
      kind: "bank_confirmation",
      document_ref: "drive:abc123",
      metadata: { bank_name: "Bank Mandiri", reference_number: "REF-001" },
    });
    expect(result.success).toBe(true);
  });
});
