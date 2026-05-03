import { describe, it, expect } from "vitest";
import { sanitizeRedirect } from "./sanitizeRedirect";

describe("sanitizeRedirect", () => {
  it("returns null for undefined", () => {
    expect(sanitizeRedirect(undefined)).toBeNull();
  });
  it("returns null for empty string", () => {
    expect(sanitizeRedirect("")).toBeNull();
  });
  it("blocks protocol-relative //evil.com", () => {
    expect(sanitizeRedirect("//evil.com/steal")).toBeNull();
  });
  it("blocks absolute http://", () => {
    expect(sanitizeRedirect("http://evil.com")).toBeNull();
  });
  it("blocks absolute https://", () => {
    expect(sanitizeRedirect("https://evil.com")).toBeNull();
  });
  it("blocks javascript:", () => {
    expect(sanitizeRedirect("javascript:alert(1)")).toBeNull();
  });
  it("blocks data:", () => {
    expect(sanitizeRedirect("data:text/html,<script>")).toBeNull();
  });
  it("blocks backslash tricks", () => {
    expect(sanitizeRedirect("/portal\\evil")).toBeNull();
  });
  it("blocks relative without leading slash", () => {
    expect(sanitizeRedirect("portal/dashboard")).toBeNull();
  });
  it("blocks non-allowlisted prefix", () => {
    expect(sanitizeRedirect("/admin/console")).toBeNull();
  });
  it("allows /portal/dashboard", () => {
    expect(sanitizeRedirect("/portal/dashboard")).toBe("/portal/dashboard");
  });
  it("allows /portal/ root", () => {
    expect(sanitizeRedirect("/portal/")).toBe("/portal/");
  });
  it("allows /workspace/anything", () => {
    expect(sanitizeRedirect("/workspace/kita")).toBe("/workspace/kita");
  });
  it("blocks path traversal ../", () => {
    expect(sanitizeRedirect("/portal/../admin")).toBeNull();
  });
  it("allows bare /portal (no trailing slash)", () => {
    expect(sanitizeRedirect("/portal")).toBe("/portal");
  });
  it("allows bare /workspace (no trailing slash)", () => {
    expect(sanitizeRedirect("/workspace")).toBe("/workspace");
  });
  it("blocks prefix smuggling /portalsomething", () => {
    expect(sanitizeRedirect("/portalsomething")).toBeNull();
  });
  it("blocks CR/LF injection", () => {
    expect(
      sanitizeRedirect("/portal/foo\r\nLocation: https://evil.com"),
    ).toBeNull();
  });
});
