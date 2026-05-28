import { describe, expect, it, vi, afterEach } from "vitest";
import { getValidToken, isTokenExpired } from "./token";

function makeJwt(payload: Record<string, unknown>): string {
  const encodedPayload = btoa(JSON.stringify(payload))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");

  return `header.${encodedPayload}.signature`;
}

describe("isTokenExpired", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("treats empty tokens as expired", () => {
    expect(isTokenExpired("")).toBe(true);
  });

  it("uses the exp claim and clock skew to detect expired tokens", () => {
    vi.setSystemTime(new Date("2026-05-23T03:00:00.000Z"));

    const nowSeconds = Math.floor(Date.now() / 1000);
    const token = makeJwt({ exp: nowSeconds + 20 });

    expect(isTokenExpired(token)).toBe(true);
    expect(isTokenExpired(token, 10)).toBe(false);
  });

  it("keeps future tokens valid", () => {
    vi.setSystemTime(new Date("2026-05-23T03:00:00.000Z"));

    const nowSeconds = Math.floor(Date.now() / 1000);
    const token = makeJwt({ exp: nowSeconds + 120 });

    expect(isTokenExpired(token)).toBe(false);
  });

  it("does not reject malformed or non-expiring tokens client-side", () => {
    expect(isTokenExpired("not-a-jwt")).toBe(false);
    expect(isTokenExpired("header.not-json.signature")).toBe(false);
    expect(isTokenExpired(makeJwt({ sub: "internal-token" }))).toBe(false);
    expect(isTokenExpired(makeJwt({ exp: "not-a-number" }))).toBe(false);
  });
});

describe("getValidToken", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns null when storage has no token", () => {
    const storage = {
      getItem: vi.fn(() => null),
      removeItem: vi.fn(),
    };

    expect(getValidToken("auth_token", storage)).toBeNull();
    expect(storage.removeItem).not.toHaveBeenCalled();
  });

  it("removes expired tokens from storage", () => {
    vi.setSystemTime(new Date("2026-05-23T03:00:00.000Z"));

    const nowSeconds = Math.floor(Date.now() / 1000);
    const expiredToken = makeJwt({ exp: nowSeconds - 1 });
    const storage = {
      getItem: vi.fn(() => expiredToken),
      removeItem: vi.fn(),
    };

    expect(getValidToken("auth_token", storage)).toBeNull();
    expect(storage.removeItem).toHaveBeenCalledWith("auth_token");
  });

  it("returns valid tokens without mutating storage", () => {
    vi.setSystemTime(new Date("2026-05-23T03:00:00.000Z"));

    const nowSeconds = Math.floor(Date.now() / 1000);
    const validToken = makeJwt({ exp: nowSeconds + 120 });
    const storage = {
      getItem: vi.fn(() => validToken),
      removeItem: vi.fn(),
    };

    expect(getValidToken("auth_token", storage)).toBe(validToken);
    expect(storage.removeItem).not.toHaveBeenCalled();
  });
});
