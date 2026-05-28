import { describe, it, expect } from "vitest";
import { computeAuditHmac, verifyAuditChain } from "@/lib/cockpit-audit";

describe("cockpit-audit", () => {
  const SECRET = "test-hmac-key-32-bytes-long-XXXX";

  it("computeAuditHmac is deterministic", () => {
    const row = {
      action: "cron.run",
      params_json: { label: "com.balizero.test" },
      created_at: "2026-05-17T10:00:00Z",
      result: "success" as const,
    };
    const h1 = computeAuditHmac(SECRET, null, row);
    const h2 = computeAuditHmac(SECRET, null, row);
    expect(h1).toBe(h2);
    expect(h1).toMatch(/^[a-f0-9]{64}$/);
  });

  it("hmac changes if prev_hmac changes", () => {
    const row = {
      action: "a",
      params_json: {},
      created_at: "",
      result: "success" as const,
    };
    expect(computeAuditHmac(SECRET, null, row)).not.toBe(
      computeAuditHmac(SECRET, "abc", row),
    );
  });

  it("verifyAuditChain valid for genesis row", () => {
    const row: any = {
      id: 1n,
      action: "a",
      params_json: {},
      created_at: "2026-05-17T10:00:00Z",
      result: "success",
      prev_hmac: null,
    };
    row.hmac_sha256 = computeAuditHmac(SECRET, null, row);
    expect(verifyAuditChain(SECRET, [row])).toEqual({ valid: true });
  });

  it("verifyAuditChain detects tampered row", () => {
    const r: any = {
      id: 1n,
      action: "a",
      params_json: {},
      created_at: "2026-05-17T10:00:00Z",
      result: "success",
      prev_hmac: null,
    };
    r.hmac_sha256 = computeAuditHmac(SECRET, null, r);
    const tampered = { ...r, action: "b" };
    expect(verifyAuditChain(SECRET, [tampered])).toEqual({
      valid: false,
      tamperedAt: 1n,
    });
  });
});
