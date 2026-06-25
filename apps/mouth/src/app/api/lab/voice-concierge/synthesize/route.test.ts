import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { POST } from "./route";

function synthesizeRequest(body?: unknown, headers?: HeadersInit): Request {
  return new Request("http://localhost/api/lab/voice-concierge/synthesize", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(headers ?? {}),
    },
    body: JSON.stringify(body ?? { text: "Hello from the concierge" }),
  });
}

function configuredHeaders(token?: string): HeadersInit {
  return token ? { "x-voice-lab-token": token } : {};
}

describe("voice concierge synthesize route", () => {
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
  const originalLabEnabled = process.env.VOICE_CONCIERGE_LAB_ENABLED;
  const originalStatusToken = process.env.VOICE_CONCIERGE_STATUS_TOKEN;
  const originalSynthesizeToken = process.env.VOICE_CONCIERGE_SYNTHESIZE_TOKEN;
  const originalTtsMaxChars = process.env.VOICE_CONCIERGE_TTS_MAX_CHARS;
  const originalTtsAudioMaxBytes =
    process.env.VOICE_CONCIERGE_TTS_AUDIO_MAX_BYTES;
  const originalSynthesizeTimeoutMs =
    process.env.VOICE_CONCIERGE_SYNTHESIZE_TIMEOUT_MS;

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
    delete process.env.VOICE_CONCIERGE_LAB_ENABLED;
    delete process.env.VOICE_CONCIERGE_STATUS_TOKEN;
    delete process.env.VOICE_CONCIERGE_SYNTHESIZE_TOKEN;
    delete process.env.VOICE_CONCIERGE_TTS_MAX_CHARS;
    delete process.env.VOICE_CONCIERGE_TTS_AUDIO_MAX_BYTES;
    delete process.env.VOICE_CONCIERGE_SYNTHESIZE_TIMEOUT_MS;
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
    restoreEnv("VOICE_CONCIERGE_LAB_ENABLED", originalLabEnabled);
    restoreEnv("VOICE_CONCIERGE_STATUS_TOKEN", originalStatusToken);
    restoreEnv("VOICE_CONCIERGE_SYNTHESIZE_TOKEN", originalSynthesizeToken);
    restoreEnv("VOICE_CONCIERGE_TTS_MAX_CHARS", originalTtsMaxChars);
    restoreEnv("VOICE_CONCIERGE_TTS_AUDIO_MAX_BYTES", originalTtsAudioMaxBytes);
    restoreEnv(
      "VOICE_CONCIERGE_SYNTHESIZE_TIMEOUT_MS",
      originalSynthesizeTimeoutMs,
    );
  });

  it("fails closed without calling the backend when local audio is disabled", async () => {
    const response = await POST(synthesizeRequest());

    expect(response.status).toBe(503);
    await expect(response.json()).resolves.toEqual({
      error: "local_audio_disabled",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("fails closed when no internal backend API key exists", async () => {
    process.env.VOICE_CONCIERGE_LOCAL_AUDIO = "true";
    process.env.VOICE_CONCIERGE_BACKEND_URL = "https://backend.test/api";

    const response = await POST(synthesizeRequest());

    expect(response.status).toBe(503);
    await expect(response.json()).resolves.toEqual({
      error: "internal_api_key_missing",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("does not use generic API_KEY as a backend credential", async () => {
    process.env.VOICE_CONCIERGE_LOCAL_AUDIO = "true";
    process.env.API_KEY = "generic-key";
    process.env.VOICE_CONCIERGE_BACKEND_URL = "https://backend.test/api";

    const response = await POST(synthesizeRequest());

    expect(response.status).toBe(503);
    await expect(response.json()).resolves.toEqual({
      error: "internal_api_key_missing",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("requires a synthesize token before calling the backend in production", async () => {
    vi.stubEnv("NODE_ENV", "production");
    process.env.VOICE_CONCIERGE_LAB_ENABLED = "true";
    process.env.VOICE_CONCIERGE_LOCAL_AUDIO = "true";
    process.env.VOICE_CONCIERGE_BACKEND_API_KEY = "test-key";
    process.env.VOICE_CONCIERGE_BACKEND_URL = "https://backend.test/api";
    process.env.VOICE_CONCIERGE_SYNTHESIZE_TOKEN = "synth-token";

    const response = await POST(synthesizeRequest());

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toEqual({
      error: "voice_concierge_synthesize_forbidden",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("fails closed without backend calls when browser realtime TTS is active", async () => {
    process.env.VOICE_CONCIERGE_LOCAL_AUDIO = "true";
    process.env.VOICE_CONCIERGE_BACKEND_API_KEY = "test-key";
    process.env.VOICE_CONCIERGE_BACKEND_URL = "https://backend.test/api";
    process.env.VOICE_CONCIERGE_TTS_PROFILE = "browser_realtime";

    const response = await POST(synthesizeRequest({ text: "Hello" }));

    expect(response.status).toBe(503);
    await expect(response.json()).resolves.toEqual({
      error: "backend_tts_disabled_for_realtime_profile",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("requires internal auth in production before returning local-audio disabled", async () => {
    vi.stubEnv("NODE_ENV", "production");
    process.env.VOICE_CONCIERGE_LAB_ENABLED = "true";

    const response = await POST(synthesizeRequest());

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toEqual({
      error: "voice_concierge_synthesize_forbidden",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("allows a production technical token to reach local-audio disabled", async () => {
    vi.stubEnv("NODE_ENV", "production");
    process.env.VOICE_CONCIERGE_LAB_ENABLED = "true";
    process.env.VOICE_CONCIERGE_SYNTHESIZE_TOKEN = "synth-token";

    const response = await POST(
      synthesizeRequest(undefined, configuredHeaders("synth-token")),
    );

    expect(response.status).toBe(503);
    await expect(response.json()).resolves.toEqual({
      error: "local_audio_disabled",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("does not accept the read-only status token for production synthesis", async () => {
    vi.stubEnv("NODE_ENV", "production");
    process.env.VOICE_CONCIERGE_LAB_ENABLED = "true";
    process.env.VOICE_CONCIERGE_LOCAL_AUDIO = "true";
    process.env.VOICE_CONCIERGE_BACKEND_API_KEY = "test-key";
    process.env.VOICE_CONCIERGE_BACKEND_URL = "https://backend.test/api";
    process.env.VOICE_CONCIERGE_STATUS_TOKEN = "status-token";

    const response = await POST(
      synthesizeRequest(undefined, configuredHeaders("status-token")),
    );

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toEqual({
      error: "voice_concierge_synthesize_forbidden",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("rejects empty text before forwarding", async () => {
    process.env.VOICE_CONCIERGE_LOCAL_AUDIO = "true";
    process.env.VOICE_CONCIERGE_BACKEND_API_KEY = "test-key";
    process.env.VOICE_CONCIERGE_BACKEND_URL = "https://backend.test/api";

    const response = await POST(synthesizeRequest({ text: "   " }));

    expect(response.status).toBe(422);
    await expect(response.json()).resolves.toEqual({
      error: "tts_text_required",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("rejects oversized text before forwarding", async () => {
    process.env.VOICE_CONCIERGE_LOCAL_AUDIO = "true";
    process.env.VOICE_CONCIERGE_BACKEND_API_KEY = "test-key";
    process.env.VOICE_CONCIERGE_BACKEND_URL = "https://backend.test/api";
    process.env.VOICE_CONCIERGE_TTS_MAX_CHARS = "8";

    const response = await POST(synthesizeRequest({ text: "too many chars" }));

    expect(response.status).toBe(413);
    await expect(response.json()).resolves.toEqual({
      error: "tts_text_too_large",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("allows an internal session cookie to synthesize in production", async () => {
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

      return new Response("RIFF", {
        status: 200,
        headers: {
          "Content-Type": "audio/wav",
          "X-Voice-Provider": "chatterbox-v3",
          "X-Voice-Constraints": "local_only,no_cloud_audio_fallback",
        },
      });
    });

    const response = await POST(
      synthesizeRequest(
        { text: "Ciao", language: "it" },
        { cookie: "nz_access_token=staff-token" },
      ),
    );

    expect(response.status).toBe(200);
    expect(response.headers.get("Content-Type")).toBe("audio/wav");
    expect(response.headers.get("X-Voice-Provider")).toBe("chatterbox-v3");
    expect(response.headers.get("Cache-Control")).toBe("no-store");
    await expect(response.text()).resolves.toBe("RIFF");
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
      "https://backend.test/api/voice/local-audio/synthesize",
      expect.objectContaining({
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": "test-key",
        },
        redirect: "error",
        signal: expect.any(AbortSignal),
        body: JSON.stringify({ text: "Ciao", voice: "it" }),
      }),
    );
  });

  it("forwards local TTS through the server-side backend bridge", async () => {
    process.env.VOICE_CONCIERGE_LOCAL_AUDIO = "true";
    process.env.VOICE_CONCIERGE_BACKEND_API_KEY = "test-key";
    process.env.VOICE_CONCIERGE_BACKEND_URL = "https://backend.test/api";
    vi.mocked(global.fetch).mockResolvedValue(
      new Response("RIFF", {
        status: 200,
        headers: {
          "Content-Type": "audio/wav",
          "X-Voice-Provider": "chatterbox-v3",
          "X-Voice-Constraints": "local_only,no_cloud_audio_fallback",
        },
      }),
    );

    const response = await POST(
      synthesizeRequest({ text: "Hello", language: "en" }),
    );

    expect(response.status).toBe(200);
    expect(response.headers.get("Content-Type")).toBe("audio/wav");
    expect(response.headers.get("X-Voice-Provider")).toBe("chatterbox-v3");
    expect(response.headers.get("X-Voice-Constraints")).toBe(
      "local_only,no_cloud_audio_fallback",
    );
    await expect(response.text()).resolves.toBe("RIFF");
    expect(global.fetch).toHaveBeenCalledWith(
      "https://backend.test/api/voice/local-audio/synthesize",
      expect.objectContaining({
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": "test-key",
        },
        redirect: "error",
        signal: expect.any(AbortSignal),
        body: JSON.stringify({ text: "Hello", voice: "en" }),
      }),
    );
  });

  it("uses a configurable backend synthesis timeout", async () => {
    process.env.VOICE_CONCIERGE_LOCAL_AUDIO = "true";
    process.env.VOICE_CONCIERGE_BACKEND_API_KEY = "test-key";
    process.env.VOICE_CONCIERGE_BACKEND_URL = "https://backend.test/api";
    process.env.VOICE_CONCIERGE_SYNTHESIZE_TIMEOUT_MS = "180000";
    const timeoutSignal = new AbortController().signal;
    const timeoutSpy = vi
      .spyOn(AbortSignal, "timeout")
      .mockReturnValue(timeoutSignal);
    vi.mocked(global.fetch).mockResolvedValue(
      new Response("RIFF", {
        status: 200,
        headers: { "Content-Type": "audio/wav" },
      }),
    );

    const response = await POST(synthesizeRequest({ text: "Hello" }));

    expect(response.status).toBe(200);
    expect(timeoutSpy).toHaveBeenCalledWith(180_000);
    expect(global.fetch).toHaveBeenCalledWith(
      "https://backend.test/api/voice/local-audio/synthesize",
      expect.objectContaining({
        signal: timeoutSignal,
      }),
    );
  });

  it("rejects oversized backend TTS audio before buffering when content length is known", async () => {
    process.env.VOICE_CONCIERGE_LOCAL_AUDIO = "true";
    process.env.VOICE_CONCIERGE_BACKEND_API_KEY = "test-key";
    process.env.VOICE_CONCIERGE_BACKEND_URL = "https://backend.test/api";
    process.env.VOICE_CONCIERGE_TTS_AUDIO_MAX_BYTES = "3";
    const arrayBuffer = vi.fn().mockResolvedValue(new ArrayBuffer(4));
    vi.mocked(global.fetch).mockResolvedValue({
      ok: true,
      headers: new Headers({
        "Content-Length": "4",
        "Content-Type": "audio/wav",
      }),
      arrayBuffer,
    } as unknown as Response);

    const response = await POST(synthesizeRequest({ text: "Hello" }));

    expect(response.status).toBe(413);
    await expect(response.json()).resolves.toEqual({
      error: "tts_audio_too_large",
    });
    expect(arrayBuffer).not.toHaveBeenCalled();
  });

  it("rejects oversized backend TTS audio after buffering when content length is absent", async () => {
    process.env.VOICE_CONCIERGE_LOCAL_AUDIO = "true";
    process.env.VOICE_CONCIERGE_BACKEND_API_KEY = "test-key";
    process.env.VOICE_CONCIERGE_BACKEND_URL = "https://backend.test/api";
    process.env.VOICE_CONCIERGE_TTS_AUDIO_MAX_BYTES = "3";
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(new Uint8Array([1, 2, 3, 4]), {
        status: 200,
        headers: {
          "Content-Type": "audio/wav",
        },
      }),
    );

    const response = await POST(synthesizeRequest({ text: "Hello" }));

    expect(response.status).toBe(413);
    await expect(response.json()).resolves.toEqual({
      error: "tts_audio_too_large",
    });
  });

  it("hides backend failure details from the browser", async () => {
    process.env.VOICE_CONCIERGE_LOCAL_AUDIO = "true";
    process.env.VOICE_CONCIERGE_BACKEND_API_KEY = "test-key";
    process.env.VOICE_CONCIERGE_BACKEND_URL = "https://backend.test/api";
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(JSON.stringify({ detail: "/tmp/client.wav failed" }), {
        status: 502,
      }),
    );

    const response = await POST(synthesizeRequest());

    expect(response.status).toBe(502);
    await expect(response.json()).resolves.toEqual({
      error: "backend_synthesize_failed",
    });
  });
});

function restoreEnv(key: string, value: string | undefined): void {
  if (value === undefined) {
    delete process.env[key];
  } else {
    process.env[key] = value;
  }
}
