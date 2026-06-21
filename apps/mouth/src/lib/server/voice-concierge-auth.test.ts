import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  canAccessVoiceConciergeHeaders,
  getVoiceConciergeInternalApiKey,
} from "./voice-concierge-auth";

describe("voice concierge auth helper", () => {
  const originalFetch = global.fetch;
  const originalBackendUrl = process.env.VOICE_CONCIERGE_BACKEND_URL;
  const originalNuzantaraApiUrl = process.env.NUZANTARA_API_URL;
  const originalBackendApiKey = process.env.VOICE_CONCIERGE_BACKEND_API_KEY;
  const originalApiKeys = process.env.API_KEYS;

  beforeEach(() => {
    vi.restoreAllMocks();
    delete process.env.VOICE_CONCIERGE_BACKEND_URL;
    delete process.env.NUZANTARA_API_URL;
    delete process.env.VOICE_CONCIERGE_BACKEND_API_KEY;
    delete process.env.API_KEYS;
    global.fetch = vi.fn();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    global.fetch = originalFetch;
    restoreEnv("VOICE_CONCIERGE_BACKEND_URL", originalBackendUrl);
    restoreEnv("NUZANTARA_API_URL", originalNuzantaraApiUrl);
    restoreEnv("VOICE_CONCIERGE_BACKEND_API_KEY", originalBackendApiKey);
    restoreEnv("API_KEYS", originalApiKeys);
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

  it("does not fall back to broad API_KEYS for voice audio endpoints", () => {
    process.env.API_KEYS = "generic-key, second-key";

    expect(getVoiceConciergeInternalApiKey()).toBeUndefined();
  });

  it("uses only the dedicated voice backend API key", () => {
    process.env.API_KEYS = "generic-key, second-key";
    process.env.VOICE_CONCIERGE_BACKEND_API_KEY = "voice-only-key";

    expect(getVoiceConciergeInternalApiKey()).toBe("voice-only-key");
  });
});

function restoreEnv(key: string, value: string | undefined): void {
  if (value === undefined) {
    delete process.env[key];
    return;
  }

  process.env[key] = value;
}
