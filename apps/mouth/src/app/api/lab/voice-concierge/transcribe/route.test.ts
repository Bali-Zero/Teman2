import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { POST } from "./route";

function audioRequest(
  fields?: {
    fileName?: string;
    content?: string;
    contentType?: string;
    fieldName?: string;
    language?: string;
    extraFile?: boolean;
  },
  headers?: HeadersInit,
): Request {
  const form = new FormData();
  const file = new File(
    [fields?.content ?? "audio"],
    fields?.fileName ?? "sample.wav",
    {
      type: fields?.contentType ?? "audio/wav",
    },
  );
  form.append(fields?.fieldName ?? "file", file);
  if (fields?.language) form.append("language", fields.language);
  if (fields?.extraFile) {
    form.append(
      "extra",
      new File(["audio2"], "second.wav", { type: "audio/wav" }),
    );
  }
  const request = new Request(
    "http://localhost/api/lab/voice-concierge/transcribe",
    {
      method: "POST",
    },
  );
  Object.defineProperty(request, "formData", {
    value: async () => form,
  });
  if (headers !== undefined) {
    const declaredHeaders = new Headers(headers);
    const originalHeaders = request.headers;
    Object.defineProperty(request, "headers", {
      value: {
        get(name: string): string | null {
          if (name.toLowerCase() === "content-length") return "512";
          return declaredHeaders.get(name) ?? originalHeaders.get(name);
        },
      },
    });
  }
  return request;
}

function configuredHeaders(token?: string): HeadersInit {
  return token ? { "x-voice-lab-token": token } : {};
}

describe("voice concierge transcribe route", () => {
  const originalFetch = global.fetch;
  const originalBackendApiKey = process.env.VOICE_CONCIERGE_BACKEND_API_KEY;
  const originalApiKeys = process.env.API_KEYS;
  const originalGenericApiKey = process.env.API_KEY;
  const originalVoiceBackendUrl = process.env.VOICE_CONCIERGE_BACKEND_URL;
  const originalNuzantaraApiUrl = process.env.NUZANTARA_API_URL;
  const originalLocalAudio = process.env.VOICE_CONCIERGE_LOCAL_AUDIO;
  const originalLocalAudioEnabled =
    process.env.VOICE_CONCIERGE_LOCAL_AUDIO_ENABLED;
  const originalLabEnabled = process.env.VOICE_CONCIERGE_LAB_ENABLED;
  const originalStatusToken = process.env.VOICE_CONCIERGE_STATUS_TOKEN;
  const originalTranscribeToken = process.env.VOICE_CONCIERGE_TRANSCRIBE_TOKEN;
  const originalAudioMaxBytes = process.env.VOICE_CONCIERGE_AUDIO_MAX_BYTES;

  beforeEach(() => {
    vi.restoreAllMocks();
    delete process.env.VOICE_CONCIERGE_BACKEND_API_KEY;
    delete process.env.API_KEYS;
    delete process.env.API_KEY;
    delete process.env.VOICE_CONCIERGE_BACKEND_URL;
    delete process.env.NUZANTARA_API_URL;
    delete process.env.VOICE_CONCIERGE_LOCAL_AUDIO;
    delete process.env.VOICE_CONCIERGE_LOCAL_AUDIO_ENABLED;
    delete process.env.VOICE_CONCIERGE_LAB_ENABLED;
    delete process.env.VOICE_CONCIERGE_STATUS_TOKEN;
    delete process.env.VOICE_CONCIERGE_TRANSCRIBE_TOKEN;
    delete process.env.VOICE_CONCIERGE_AUDIO_MAX_BYTES;
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
    restoreEnv("VOICE_CONCIERGE_LAB_ENABLED", originalLabEnabled);
    restoreEnv("VOICE_CONCIERGE_STATUS_TOKEN", originalStatusToken);
    restoreEnv("VOICE_CONCIERGE_TRANSCRIBE_TOKEN", originalTranscribeToken);
    restoreEnv("VOICE_CONCIERGE_AUDIO_MAX_BYTES", originalAudioMaxBytes);
  });

  it("fails closed without calling the backend when local audio is disabled", async () => {
    const response = await POST(audioRequest());

    expect(response.status).toBe(503);
    await expect(response.json()).resolves.toEqual({
      error: "local_audio_disabled",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("fails closed when no internal backend API key exists", async () => {
    process.env.VOICE_CONCIERGE_LOCAL_AUDIO = "true";
    process.env.VOICE_CONCIERGE_BACKEND_URL = "https://backend.test/api";

    const response = await POST(audioRequest(undefined, configuredHeaders()));

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

    const response = await POST(audioRequest(undefined, configuredHeaders()));

    expect(response.status).toBe(503);
    await expect(response.json()).resolves.toEqual({
      error: "internal_api_key_missing",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("requires a lab token before transcribing in production", async () => {
    vi.stubEnv("NODE_ENV", "production");
    process.env.VOICE_CONCIERGE_LAB_ENABLED = "true";
    process.env.VOICE_CONCIERGE_LOCAL_AUDIO = "true";
    process.env.VOICE_CONCIERGE_BACKEND_API_KEY = "test-key";
    process.env.VOICE_CONCIERGE_BACKEND_URL = "https://backend.test/api";
    process.env.VOICE_CONCIERGE_TRANSCRIBE_TOKEN = "lab-token";

    const response = await POST(audioRequest(undefined, configuredHeaders()));

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toEqual({
      error: "voice_concierge_transcribe_forbidden",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("requires internal auth in production before returning local-audio disabled", async () => {
    vi.stubEnv("NODE_ENV", "production");
    process.env.VOICE_CONCIERGE_LAB_ENABLED = "true";

    const response = await POST(audioRequest());

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toEqual({
      error: "voice_concierge_transcribe_forbidden",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("allows a production technical token to reach local-audio disabled", async () => {
    vi.stubEnv("NODE_ENV", "production");
    process.env.VOICE_CONCIERGE_LAB_ENABLED = "true";
    process.env.VOICE_CONCIERGE_TRANSCRIBE_TOKEN = "lab-token";

    const response = await POST(
      audioRequest(undefined, configuredHeaders("lab-token")),
    );

    expect(response.status).toBe(503);
    await expect(response.json()).resolves.toEqual({
      error: "local_audio_disabled",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("does not accept the read-only status token for production transcription", async () => {
    vi.stubEnv("NODE_ENV", "production");
    process.env.VOICE_CONCIERGE_LAB_ENABLED = "true";
    process.env.VOICE_CONCIERGE_LOCAL_AUDIO = "true";
    process.env.VOICE_CONCIERGE_BACKEND_API_KEY = "test-key";
    process.env.VOICE_CONCIERGE_BACKEND_URL = "https://backend.test/api";
    process.env.VOICE_CONCIERGE_STATUS_TOKEN = "status-token";

    const response = await POST(
      audioRequest(undefined, configuredHeaders("status-token")),
    );

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toEqual({
      error: "voice_concierge_transcribe_forbidden",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("allows an internal session cookie to transcribe in production", async () => {
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
          text: "ciao dal provider locale",
          language: "it",
          duration_seconds: null,
          provider: "whisper.cpp",
          constraints: [
            "local_only",
            "no_cloud_audio_fallback",
            "no_raw_audio_persistence",
          ],
        }),
        { status: 200 },
      );
    });

    const response = await POST(
      audioRequest(
        { language: "it" },
        { cookie: "nz_access_token=staff-token" },
      ),
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      text: "ciao dal provider locale",
      provider: "whisper.cpp",
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
      "https://backend.test/api/voice/local-audio/transcribe",
      expect.objectContaining({
        method: "POST",
        headers: { "X-API-Key": "test-key" },
        redirect: "error",
        signal: expect.any(AbortSignal),
        body: expect.any(FormData),
      }),
    );
  });

  it("rejects a non-internal session before transcribing in production", async () => {
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

    const response = await POST(
      audioRequest(undefined, { cookie: "nz_access_token=client-token" }),
    );

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toEqual({
      error: "voice_concierge_transcribe_forbidden",
    });
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(global.fetch).toHaveBeenCalledWith(
      "https://backend.test/api/auth/profile",
      expect.objectContaining({
        headers: { Authorization: "Bearer client-token" },
      }),
    );
  });

  it("rejects uploads without content length before parsing or forwarding", async () => {
    process.env.VOICE_CONCIERGE_LOCAL_AUDIO = "true";
    process.env.VOICE_CONCIERGE_BACKEND_API_KEY = "test-key";
    process.env.VOICE_CONCIERGE_BACKEND_URL = "https://backend.test/api";

    const response = await POST(audioRequest());

    expect(response.status).toBe(411);
    await expect(response.json()).resolves.toEqual({
      error: "content_length_required",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("rejects non-audio MIME before forwarding", async () => {
    process.env.VOICE_CONCIERGE_LOCAL_AUDIO = "true";
    process.env.VOICE_CONCIERGE_BACKEND_API_KEY = "test-key";
    process.env.VOICE_CONCIERGE_BACKEND_URL = "https://backend.test/api";

    const response = await POST(
      audioRequest(
        { fileName: "note.txt", content: "text", contentType: "text/plain" },
        configuredHeaders(),
      ),
    );

    expect(response.status).toBe(415);
    await expect(response.json()).resolves.toEqual({
      error: "unsupported_audio_content_type",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("rejects extra file parts before forwarding", async () => {
    process.env.VOICE_CONCIERGE_LOCAL_AUDIO = "true";
    process.env.VOICE_CONCIERGE_BACKEND_API_KEY = "test-key";
    process.env.VOICE_CONCIERGE_BACKEND_URL = "https://backend.test/api";

    const response = await POST(
      audioRequest({ extraFile: true }, configuredHeaders()),
    );

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({
      error: "exactly_one_audio_file_required",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("forwards one local audio upload through the server-side backend bridge", async () => {
    process.env.VOICE_CONCIERGE_LOCAL_AUDIO = "true";
    process.env.API_KEYS = "test-key, second-key";
    process.env.VOICE_CONCIERGE_BACKEND_URL = "https://backend.test/api";
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          text: "ciao dal provider locale",
          language: "it",
          duration_seconds: null,
          provider: "whisper.cpp",
          constraints: [
            "local_only",
            "no_cloud_audio_fallback",
            "no_raw_audio_persistence",
          ],
        }),
        { status: 200 },
      ),
    );

    const response = await POST(
      audioRequest({ language: "it" }, configuredHeaders()),
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      text: "ciao dal provider locale",
      provider: "whisper.cpp",
      constraints: [
        "local_only",
        "no_cloud_audio_fallback",
        "no_raw_audio_persistence",
      ],
    });
    expect(global.fetch).toHaveBeenCalledWith(
      "https://backend.test/api/voice/local-audio/transcribe",
      expect.objectContaining({
        method: "POST",
        headers: { "X-API-Key": "test-key" },
        redirect: "error",
        signal: expect.any(AbortSignal),
        body: expect.any(FormData),
      }),
    );
    const forwardedForm = vi.mocked(global.fetch).mock.calls[0]?.[1]
      ?.body as FormData;
    expect(forwardedForm.get("language")).toBe("it");
    const forwardedFile = forwardedForm.get("file");
    expect(Object(forwardedFile).name).toBe("sample.wav");
    expect(Object(forwardedFile).type).toBe("audio/wav");
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

    const response = await POST(audioRequest(undefined, configuredHeaders()));

    expect(response.status).toBe(502);
    await expect(response.json()).resolves.toEqual({
      error: "backend_transcribe_failed",
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
