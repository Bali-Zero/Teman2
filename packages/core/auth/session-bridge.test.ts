import { describe, it, expect, beforeEach } from "vitest";
import { getOrCreateSessionId, BZ_SESSION_COOKIE } from "./session-bridge";

describe("session-bridge", () => {
  beforeEach(() => {
    document.cookie = `${BZ_SESSION_COOKIE}=; Max-Age=0; path=/`;
  });

  it("creates a UUID v4 cookie on first call", () => {
    const id = getOrCreateSessionId();
    expect(id).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
    );
    expect(document.cookie).toContain(BZ_SESSION_COOKIE);
  });

  it("reuses existing cookie on subsequent calls", () => {
    const a = getOrCreateSessionId();
    const b = getOrCreateSessionId();
    expect(a).toBe(b);
  });
});
