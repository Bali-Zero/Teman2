import { describe, expect, it } from "vitest";

import { isValidClientId } from "@/app/api/portal/invite/route";

/**
 * Guard for CodeQL alert #8318 (js/request-forgery), introduced by PR #3430 and
 * merged to main before it was fixed.
 *
 * `clientId` is interpolated into `${BACKEND_URL}/api/portal/invite/client/${clientId}`
 * while the route forwards the caller's `authorization` and `cookie` headers. If a
 * caller can put path separators or traversal segments into it, `fetch` normalises
 * them away and the proxy becomes an authenticated gateway to any backend route.
 *
 * Per repo convention every guard proves GUILT (it rejects the attack) and
 * INNOCENCE (it does not reject legitimate input).
 */
describe("isValidClientId — GUILT: rejects anything that could redirect the request", () => {
  const attacks: [string, string][] = [
    ["parent traversal", "../../../../admin/secrets"],
    ["single traversal", ".."],
    ["encoded traversal", "%2e%2e%2f"],
    ["leading slash", "/admin"],
    ["embedded slash", "1/../../admin"],
    ["absolute url", "http://evil.example.com/"],
    ["protocol-relative url", "//evil.example.com"],
    ["query smuggling", "1?admin=true"],
    ["fragment smuggling", "1#/admin"],
    ["newline injection", "1\n/admin"],
    ["backslash", "1\\admin"],
    ["semicolon param", "1;a=b"],
    ["at-sign host swap", "1@evil.example.com"],
  ];

  it.each(attacks)("rejects %s", (_label, raw) => {
    expect(isValidClientId(raw)).toBe(false);
  });

  it("rejects null (no clientId supplied)", () => {
    expect(isValidClientId(null)).toBe(false);
  });

  it("rejects the empty string", () => {
    expect(isValidClientId("")).toBe(false);
  });

  it("rejects non-integer shapes the backend could not key on", () => {
    for (const raw of [
      "0",
      "-1",
      "1.5",
      "1e3",
      " 1",
      "1 ",
      "+1",
      "abc",
      "007",
    ]) {
      expect(isValidClientId(raw)).toBe(false);
    }
  });
});

describe("isValidClientId — INNOCENCE: accepts real client ids", () => {
  it("accepts the id shape the backend keys on (positive integer)", () => {
    for (const raw of ["1", "42", "12028", "999999"]) {
      expect(isValidClientId(raw)).toBe(true);
    }
  });

  it("accepts an id at the top of the real table without truncating it", () => {
    // `clients` held 12,028 rows when this guard was written; the guard must not
    // cap legitimate growth, only reject non-integers.
    expect(isValidClientId("123456789012345678")).toBe(true);
  });
});
