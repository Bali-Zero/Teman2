import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  attachToServerSession,
  getOrCreateSessionId,
  readFirstTouchAttribution,
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

describe("readFirstTouchAttribution — inbound UTM/referrer capture (R4)", () => {
  const originalLocation = window.location;
  const originalReferrer = document.referrer;

  function stubLocation(href: string) {
    Object.defineProperty(window, "location", {
      value: new URL(href),
      writable: true,
      configurable: true,
    });
  }

  function stubReferrer(value: string) {
    Object.defineProperty(document, "referrer", { value, configurable: true });
  }

  beforeEach(() => {
    document.cookie = `${BZ_SESSION_COOKIE}=; Max-Age=0; path=/`;
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
  });

  afterEach(() => {
    Object.defineProperty(window, "location", {
      value: originalLocation,
      writable: true,
      configurable: true,
    });
    Object.defineProperty(document, "referrer", {
      value: originalReferrer,
      configurable: true,
    });
  });

  it("captures utm_* + the referring hostname only, on a genuine first touch", () => {
    stubLocation(
      "https://balizero.com/visa/voa?utm_source=instagram&utm_medium=paid_social&utm_campaign=voa_launch",
    );
    stubReferrer("https://www.instagram.com/reel/xyz?igshid=abc123");

    const attribution = readFirstTouchAttribution();
    expect(attribution).toEqual({
      utm_source: "instagram",
      utm_medium: "paid_social",
      utm_campaign: "voa_launch",
      referrer_host: "www.instagram.com",
    });
    // Law 2 minimization: the referrer's path/query never rides along —
    // only the hostname that sent the visitor.
    expect(JSON.stringify(attribution)).not.toContain("igshid");
    expect(JSON.stringify(attribution)).not.toContain("/reel/xyz");
  });

  it("returns undefined — never an empty object — with no UTM and no cross-site referrer", () => {
    stubLocation("https://balizero.com/visa/voa");
    stubReferrer("");
    expect(readFirstTouchAttribution()).toBeUndefined();
  });

  it("returns undefined once bz_session already exists — not a genuine first touch", () => {
    document.cookie = `${BZ_SESSION_COOKIE}=already-here; path=/`;
    stubLocation("https://balizero.com/visa/voa?utm_source=instagram");
    expect(readFirstTouchAttribution()).toBeUndefined();
  });

  it("attachToServerSession stamps first_touch into step_state on a fresh session", async () => {
    stubLocation(
      "https://balizero.com/visa/voa?utm_source=newsletter&utm_medium=email",
    );
    stubReferrer("");

    await attachToServerSession({ funnel: "visa" });

    const call = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    const body = JSON.parse(call[1].body as string);
    expect(body.step_state.first_touch).toEqual({
      utm_source: "newsletter",
      utm_medium: "email",
    });
  });

  it("never overwrites an already-persisted first_touch on a later touch in the same session", async () => {
    document.cookie = `${BZ_SESSION_COOKIE}=already-here; path=/`;
    stubLocation("https://balizero.com/visa/voa/checkout/abc"); // no UTM on this later page

    await attachToServerSession({
      funnel: "visa",
      step_state: { step: "checkout" },
    });

    const call = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    const body = JSON.parse(call[1].body as string);
    expect(body.step_state).toEqual({ step: "checkout" });
    expect(body.step_state.first_touch).toBeUndefined();
  });
});
