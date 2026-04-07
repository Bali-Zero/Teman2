// apps/mouth/src/lib/__tests__/gateway.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { getGatewayUrl, getGatewayToken, setGatewayToken, isGatewayConfigured } from "../gateway";

describe("gateway client", () => {
  beforeEach(() => {
    const store = new Map<string, string>();
    vi.stubGlobal("localStorage", {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => store.set(key, value),
      removeItem: (key: string) => store.delete(key),
    });
  });

  it("returns default gateway URL", () => {
    expect(getGatewayUrl()).toBe("https://127.0.0.1:8090");
  });

  it("stores and retrieves gateway token", () => {
    expect(isGatewayConfigured()).toBe(false);
    setGatewayToken("abc123");
    expect(getGatewayToken()).toBe("abc123");
    expect(isGatewayConfigured()).toBe(true);
  });

  it("returns empty string when no token set", () => {
    expect(getGatewayToken()).toBe("");
  });
});
