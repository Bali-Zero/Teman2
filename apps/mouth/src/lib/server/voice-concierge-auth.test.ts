import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { canAccessVoiceConciergeHeaders } from "./voice-concierge-auth";

describe("voice concierge auth helper", () => {
  const originalFetch = global.fetch;
  const originalBackendUrl = process.env.VOICE_CONCIERGE_BACKEND_URL;
  const originalNuzantaraApiUrl = process.env.NUZANTARA_API_URL;

  beforeEach(() => {
    vi.restoreAllMocks();
    delete process.env.VOICE_CONCIERGE_BACKEND_URL;
    delete process.env.NUZANTARA_API_URL;
    global.fetch = vi.fn();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    global.fetch = originalFetch;
    restoreEnv("VOICE_CONCIERGE_BACKEND_URL", originalBackendUrl);
    restoreEnv("NUZANTARA_API_URL", originalNuzantaraApiUrl);
  });

  it("bounds the production profile lookup with an abort signal", async () => {
    vi.stubEnv("NODE_ENV", "production");
    process.env.NUZANTARA_API_URL = "https://backend.test/api";
    global.fetch = vi.fn().mockResolvedValue(
      Response.json({
        email: "ops@balizero.com",
        role: "admin",
      }),
    );

    const allowed = await canAccessVoiceConciergeHeaders(
      new Headers({ cookie: "nz_access_token=session-token" }),
    );

    expect(allowed).toBe(true);
    expect(global.fetch).toHaveBeenCalledWith(
      "https://backend.test/api/auth/profile",
      expect.objectContaining({
        method: "GET",
        signal: expect.any(AbortSignal),
      }),
    );
  });
});

function restoreEnv(key: string, value: string | undefined): void {
  if (value === undefined) {
    delete process.env[key];
    return;
  }

  process.env[key] = value;
}
