import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { GET } from "./route";

function request(headers?: HeadersInit): Request {
  return new Request("http://localhost/api/lab/voice-concierge/status", {
    headers,
  });
}

describe("voice concierge status route", () => {
  const originalFetch = global.fetch;
  const originalBackendApiKey = process.env.VOICE_CONCIERGE_BACKEND_API_KEY;
  const originalApiKeys = process.env.API_KEYS;
  const originalGenericApiKey = process.env.API_KEY;
  const originalVoiceBackendUrl = process.env.VOICE_CONCIERGE_BACKEND_URL;
  const originalNuzantaraApiUrl = process.env.NUZANTARA_API_URL;
  const originalLocalAudio = process.env.VOICE_CONCIERGE_LOCAL_AUDIO;
  const originalLocalAudioEnabled =
    process.env.VOICE_CONCIERGE_LOCAL_AUDIO_ENABLED;
  const originalTtsProfile = process.env.VOICE_CONCIERGE_TTS_PROFILE;
  const originalRealtimeTtsProvider =
    process.env.VOICE_CONCIERGE_REALTIME_TTS_PROVIDER;
  const originalLabEnabled = process.env.VOICE_CONCIERGE_LAB_ENABLED;
  const originalStatusToken = process.env.VOICE_CONCIERGE_STATUS_TOKEN;

  beforeEach(() => {
    vi.restoreAllMocks();
    delete process.env.VOICE_CONCIERGE_BACKEND_API_KEY;
    delete process.env.API_KEYS;
    delete process.env.API_KEY;
    delete process.env.VOICE_CONCIERGE_BACKEND_URL;
    delete process.env.NUZANTARA_API_URL;
    delete process.env.VOICE_CONCIERGE_LOCAL_AUDIO;
    delete process.env.VOICE_CONCIERGE_LOCAL_AUDIO_ENABLED;
    delete process.env.VOICE_CONCIERGE_TTS_PROFILE;
    delete process.env.VOICE_CONCIERGE_REALTIME_TTS_PROVIDER;
    delete process.env.VOICE_CONCIERGE_LAB_ENABLED;
    delete process.env.VOICE_CONCIERGE_STATUS_TOKEN;
    global.fetch = vi.fn();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    global.fetch = originalFetch;
    restoreEnv("VOICE_CONCIERGE_BACKEND_API_KEY", originalBackendApiKey);
    restoreEnv("API_KEYS", originalApiKeys);
    restoreEnv("API_KEY", originalGenericApiKey);
    restoreEnv("VOICE_CONCIERGE_BACKEND_URL", originalVoiceBackendUrl);
    restoreEnv("NUZANTARA_API_URL", originalNuzantaraApiUrl);
    restoreEnv("VOICE_CONCIERGE_LOCAL_AUDIO", originalLocalAudio);
    restoreEnv(
      "VOICE_CONCIERGE_LOCAL_AUDIO_ENABLED",
      originalLocalAudioEnabled,
    );
    restoreEnv("VOICE_CONCIERGE_TTS_PROFILE", originalTtsProfile);
    restoreEnv(
      "VOICE_CONCIERGE_REALTIME_TTS_PROVIDER",
      originalRealtimeTtsProvider,
    );
    restoreEnv("VOICE_CONCIERGE_LAB_ENABLED", originalLabEnabled);
    restoreEnv("VOICE_CONCIERGE_STATUS_TOKEN", originalStatusToken);
  });

  it("returns disabled local audio status without calling the backend by default", async () => {
    const response = await GET(request());

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      browser_speech_provider: "disabled",
      text_concierge_provider: "local-demo",
      tts_profile: {
        active_profile: "high_quality_offline",
        active_provider: "chatterbox-v3",
        quality: "high_quality",
        latency_class: "offline",
        fallback_policy: "fail_closed",
      },
      local_audio: {
        enabled: false,
        ready: false,
        source: "disabled",
        providers: {
          stt: {
            name: "whisper.cpp",
            available: false,
            detail: "local audio disabled",
          },
        },
      },
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("exposes browser realtime TTS as an explicit local-only profile", async () => {
    process.env.VOICE_CONCIERGE_TTS_PROFILE = "browser-realtime";
    process.env.VOICE_CONCIERGE_REALTIME_TTS_PROVIDER =
      "browser-web-speech-local";

    const response = await GET(request());

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      browser_speech_provider: "web-speech-local",
      tts_profile: {
        active_profile: "browser_realtime",
        active_provider: "browser-web-speech-local",
        quality: "realtime",
        latency_class: "interactive",
        fallback_policy: "fail_closed",
        profiles: {
          browser_realtime: {
            available: false,
            detail: "client must confirm a browser localService voice",
            policy: {
              requires_network: false,
              allows_cloud_fallback: false,
              pii_boundary: "local_only",
            },
          },
        },
      },
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("fails closed when local audio is enabled but no internal API key exists", async () => {
    process.env.VOICE_CONCIERGE_LOCAL_AUDIO = "true";

    const response = await GET(request());

    expect(response.status).toBe(503);
    await expect(response.json()).resolves.toMatchObject({
      local_audio: {
        enabled: true,
        ready: false,
        source: "misconfigured",
        error: "internal_api_key_missing",
      },
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("does not use generic API_KEY as a backend credential", async () => {
    process.env.VOICE_CONCIERGE_LOCAL_AUDIO = "true";
    process.env.API_KEY = "generic-key";
    process.env.VOICE_CONCIERGE_BACKEND_URL = "https://backend.test/api";

    const response = await GET(request());

    expect(response.status).toBe(503);
    await expect(response.json()).resolves.toMatchObject({
      local_audio: {
        source: "misconfigured",
        error: "internal_api_key_missing",
      },
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("fails closed when local audio is enabled but no backend URL exists", async () => {
    process.env.VOICE_CONCIERGE_LOCAL_AUDIO = "true";
    process.env.VOICE_CONCIERGE_BACKEND_API_KEY = "test-key";

    const response = await GET(request());

    expect(response.status).toBe(503);
    await expect(response.json()).resolves.toMatchObject({
      local_audio: {
        source: "misconfigured",
        error: "backend_url_missing",
      },
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("forwards local audio status through the server-side backend bridge", async () => {
    process.env.VOICE_CONCIERGE_LOCAL_AUDIO = "true";
    process.env.VOICE_CONCIERGE_BACKEND_API_KEY = "test-key";
    process.env.VOICE_CONCIERGE_BACKEND_URL = "https://backend.test/api";
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          enabled: true,
          ready: false,
          roundtrip_ready: true,
          turn_detection_ready: false,
          providers: {
            stt: {
              name: "whisper.cpp",
              available: true,
              detail: "ready",
              policy: {
                requires_network: false,
                allows_cloud_fallback: false,
                pii_boundary: "local_only",
              },
            },
            vad: {
              name: "silero-vad",
              available: false,
              detail: "adapter not wired",
              policy: {
                requires_network: false,
                allows_cloud_fallback: false,
                pii_boundary: "local_only",
              },
            },
            tts: {
              name: "chatterbox-v3",
              available: false,
              detail: "adapter not wired",
              policy: {
                requires_network: false,
                allows_cloud_fallback: false,
                pii_boundary: "local_only",
              },
            },
          },
          tts_profile: {
            active_profile: "browser_realtime",
            active_provider: "browser-web-speech-local",
            quality: "realtime",
            latency_class: "interactive",
            fallback_policy: "fail_closed",
            profiles: {
              high_quality_offline: {
                profile: "high_quality_offline",
                provider: "chatterbox-v3",
                quality: "high_quality",
                latency_class: "offline",
                available: false,
                detail: "adapter not wired",
                policy: {
                  requires_network: false,
                  allows_cloud_fallback: false,
                  pii_boundary: "local_only",
                },
              },
              browser_realtime: {
                profile: "browser_realtime",
                provider: "browser-web-speech-local",
                quality: "realtime",
                latency_class: "interactive",
                available: false,
                detail: "client must confirm a browser localService voice",
                policy: {
                  requires_network: false,
                  allows_cloud_fallback: false,
                  pii_boundary: "local_only",
                },
              },
            },
          },
          constraints: ["local_only", "no_cloud_audio_fallback"],
        }),
        { status: 200 },
      ),
    );

    const response = await GET(request());

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      local_audio: {
        enabled: true,
        ready: false,
        roundtrip_ready: true,
        turn_detection_ready: false,
        source: "backend",
        providers: {
          stt: { name: "whisper.cpp", available: true, detail: "ready" },
        },
      },
      tts_profile: {
        active_profile: "browser_realtime",
        active_provider: "browser-web-speech-local",
      },
    });
    expect(global.fetch).toHaveBeenCalledWith(
      "https://backend.test/api/voice/local-audio/status",
      expect.objectContaining({
        method: "GET",
        headers: { "X-API-Key": "test-key" },
        signal: expect.any(AbortSignal),
      }),
    );
  });

  it("requires a lab token before probing backend in production", async () => {
    vi.stubEnv("NODE_ENV", "production");
    process.env.VOICE_CONCIERGE_LAB_ENABLED = "true";
    process.env.VOICE_CONCIERGE_LOCAL_AUDIO = "true";
    process.env.VOICE_CONCIERGE_BACKEND_API_KEY = "test-key";
    process.env.VOICE_CONCIERGE_BACKEND_URL = "https://backend.test/api";
    process.env.VOICE_CONCIERGE_STATUS_TOKEN = "status-token";

    const response = await GET(request());

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toMatchObject({
      error: "voice_concierge_status_forbidden",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("requires internal auth in production before returning disabled status", async () => {
    vi.stubEnv("NODE_ENV", "production");
    process.env.VOICE_CONCIERGE_LAB_ENABLED = "true";

    const response = await GET(request());

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toMatchObject({
      error: "voice_concierge_status_forbidden",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("allows a production technical token to read disabled status", async () => {
    vi.stubEnv("NODE_ENV", "production");
    process.env.VOICE_CONCIERGE_LAB_ENABLED = "true";
    process.env.VOICE_CONCIERGE_STATUS_TOKEN = "status-token";

    const response = await GET(
      request({ "x-voice-lab-token": "status-token" }),
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      local_audio: {
        enabled: false,
        ready: false,
        source: "disabled",
      },
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("allows an internal session cookie to probe backend in production", async () => {
    vi.stubEnv("NODE_ENV", "production");
    process.env.VOICE_CONCIERGE_LAB_ENABLED = "true";
    process.env.VOICE_CONCIERGE_LOCAL_AUDIO = "true";
    process.env.VOICE_CONCIERGE_BACKEND_API_KEY = "test-key";
    process.env.VOICE_CONCIERGE_BACKEND_URL = "https://backend.test/api";
    vi.mocked(global.fetch).mockImplementation(async (url) => {
      if (url === "https://backend.test/api/auth/profile") {
        return new Response(
          JSON.stringify({
            id: "staff-1",
            email: "staff@example.com",
            name: "Staff",
            role: "admin",
            language: "en",
          }),
          { status: 200 },
        );
      }

      return new Response(
        JSON.stringify({
          enabled: true,
          ready: true,
          providers: {
            stt: {
              name: "whisper.cpp",
              available: true,
              detail: "ready",
              policy: {
                requires_network: false,
                allows_cloud_fallback: false,
                pii_boundary: "local_only",
              },
            },
            vad: {
              name: "silero-vad",
              available: true,
              detail: "ready",
              policy: {
                requires_network: false,
                allows_cloud_fallback: false,
                pii_boundary: "local_only",
              },
            },
            tts: {
              name: "chatterbox-v3",
              available: true,
              detail: "ready",
              policy: {
                requires_network: false,
                allows_cloud_fallback: false,
                pii_boundary: "local_only",
              },
            },
          },
          constraints: ["local_only", "no_cloud_audio_fallback"],
        }),
        { status: 200 },
      );
    });

    const response = await GET(
      request({ cookie: "nz_access_token=staff-token" }),
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      local_audio: {
        source: "backend",
        ready: true,
      },
    });
    expect(global.fetch).toHaveBeenNthCalledWith(
      1,
      "https://backend.test/api/auth/profile",
      expect.objectContaining({
        method: "GET",
        headers: { Authorization: "Bearer staff-token" },
        redirect: "error",
      }),
    );
    expect(global.fetch).toHaveBeenNthCalledWith(
      2,
      "https://backend.test/api/voice/local-audio/status",
      expect.objectContaining({
        method: "GET",
        headers: { "X-API-Key": "test-key" },
        signal: expect.any(AbortSignal),
      }),
    );
  });

  it("rejects a non-internal session before probing backend in production", async () => {
    vi.stubEnv("NODE_ENV", "production");
    process.env.VOICE_CONCIERGE_LAB_ENABLED = "true";
    process.env.VOICE_CONCIERGE_LOCAL_AUDIO = "true";
    process.env.VOICE_CONCIERGE_BACKEND_API_KEY = "test-key";
    process.env.VOICE_CONCIERGE_BACKEND_URL = "https://backend.test/api";
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "client-1",
          email: "client@example.com",
          name: "Client",
          role: "client",
          language: "en",
        }),
        { status: 200 },
      ),
    );

    const response = await GET(
      request({ cookie: "nz_access_token=client-token" }),
    );

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toMatchObject({
      error: "voice_concierge_status_forbidden",
    });
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(global.fetch).toHaveBeenCalledWith(
      "https://backend.test/api/auth/profile",
      expect.objectContaining({
        headers: { Authorization: "Bearer client-token" },
      }),
    );
  });
});

function restoreEnv(key: string, value: string | undefined): void {
  if (value === undefined) {
    delete process.env[key];
  } else {
    process.env[key] = value;
  }
}
