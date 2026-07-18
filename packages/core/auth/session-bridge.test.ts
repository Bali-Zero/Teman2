import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  attachToServerSession,
  getOrCreateSessionId,
  BZ_SESSION_COOKIE,
} from "./session-bridge";

describe("session-bridge", () => {
  beforeEach(() => {
    document.cookie = `${BZ_SESSION_COOKIE}=; Max-Age=0; path=/`;
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
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

  it("attaches funnel state to the server session with credentials", async () => {
    document.cookie = `${BZ_SESSION_COOKIE}=existing-session-id; path=/`;

    await attachToServerSession({
      funnel: "visa",
      step_state: { step: 2, answer: "E33G" },
    });

    expect(fetch).toHaveBeenCalledWith("/api/funnel/session/touch", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: "existing-session-id",
        funnel: "visa",
        step_state: { step: 2, answer: "E33G" },
      }),
    });
  });
});
