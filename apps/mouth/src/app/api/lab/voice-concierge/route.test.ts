import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { POST } from "./route";

function request(body: unknown): Request {
  return new Request("http://localhost/api/lab/voice-concierge", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

describe("voice concierge route", () => {
  const originalFetch = global.fetch;
  const originalApiKey = process.env.GOOGLE_AI_STUDIO_API_KEY;
  const originalGeminiKey = process.env.GEMINI_API_KEY;
  const originalModel = process.env.GOOGLE_AI_STUDIO_MODEL;
  const originalLabEnabled = process.env.VOICE_CONCIERGE_LAB_ENABLED;
  const originalAllowCloudText = process.env.VOICE_CONCIERGE_ALLOW_CLOUD_TEXT;
  const originalVoiceBackendUrl = process.env.VOICE_CONCIERGE_BACKEND_URL;
  const originalNuzantaraApiUrl = process.env.NUZANTARA_API_URL;
  const originalTextToken = process.env.VOICE_CONCIERGE_TEXT_TOKEN;

  beforeEach(() => {
    vi.restoreAllMocks();
    delete process.env.GOOGLE_AI_STUDIO_API_KEY;
    delete process.env.GEMINI_API_KEY;
    delete process.env.GOOGLE_AI_STUDIO_MODEL;
    delete process.env.VOICE_CONCIERGE_LAB_ENABLED;
    delete process.env.VOICE_CONCIERGE_ALLOW_CLOUD_TEXT;
    delete process.env.VOICE_CONCIERGE_BACKEND_URL;
    delete process.env.NUZANTARA_API_URL;
    delete process.env.VOICE_CONCIERGE_TEXT_TOKEN;
    global.fetch = vi.fn();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    global.fetch = originalFetch;
    if (originalApiKey === undefined) {
      delete process.env.GOOGLE_AI_STUDIO_API_KEY;
    } else {
      process.env.GOOGLE_AI_STUDIO_API_KEY = originalApiKey;
    }
    if (originalGeminiKey === undefined) {
      delete process.env.GEMINI_API_KEY;
    } else {
      process.env.GEMINI_API_KEY = originalGeminiKey;
    }
    if (originalModel === undefined) {
      delete process.env.GOOGLE_AI_STUDIO_MODEL;
    } else {
      process.env.GOOGLE_AI_STUDIO_MODEL = originalModel;
    }
    if (originalLabEnabled === undefined) {
      delete process.env.VOICE_CONCIERGE_LAB_ENABLED;
    } else {
      process.env.VOICE_CONCIERGE_LAB_ENABLED = originalLabEnabled;
    }
    if (originalAllowCloudText === undefined) {
      delete process.env.VOICE_CONCIERGE_ALLOW_CLOUD_TEXT;
    } else {
      process.env.VOICE_CONCIERGE_ALLOW_CLOUD_TEXT = originalAllowCloudText;
    }
    if (originalVoiceBackendUrl === undefined) {
      delete process.env.VOICE_CONCIERGE_BACKEND_URL;
    } else {
      process.env.VOICE_CONCIERGE_BACKEND_URL = originalVoiceBackendUrl;
    }
    if (originalNuzantaraApiUrl === undefined) {
      delete process.env.NUZANTARA_API_URL;
    } else {
      process.env.NUZANTARA_API_URL = originalNuzantaraApiUrl;
    }
    if (originalTextToken === undefined) {
      delete process.env.VOICE_CONCIERGE_TEXT_TOKEN;
    } else {
      process.env.VOICE_CONCIERGE_TEXT_TOKEN = originalTextToken;
    }
  });

  it("does not expose the prototype in production without an explicit flag", async () => {
    vi.stubEnv("NODE_ENV", "production");

    const response = await POST(
      request({ message: "Can I set up a PT PMA for a cafe in Bali?" }),
    );

    expect(response.status).toBe(404);
    await expect(response.json()).resolves.toMatchObject({
      error: "voice_concierge_disabled",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("rejects an empty message", async () => {
    const response = await POST(request({ message: " " }));

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({
      error: "message required",
    });
  });

  it("requires internal auth in production before demo or Gemini text handling", async () => {
    vi.stubEnv("NODE_ENV", "production");
    process.env.VOICE_CONCIERGE_LAB_ENABLED = "true";

    const response = await POST(
      request({ message: "Can I set up a PT PMA for a cafe in Bali?" }),
    );

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toMatchObject({
      error: "voice_concierge_forbidden",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("allows an internal session cookie to use demo text mode in production", async () => {
    vi.stubEnv("NODE_ENV", "production");
    process.env.VOICE_CONCIERGE_LAB_ENABLED = "true";
    process.env.VOICE_CONCIERGE_BACKEND_URL = "https://backend.test/api";
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "staff-1",
          email: "staff@example.com",
          name: "Staff",
          role: "admin",
          language: "en",
        }),
        { status: 200 },
      ),
    );

    const response = await POST(
      new Request("http://localhost/api/lab/voice-concierge", {
        method: "POST",
        headers: { cookie: "nz_access_token=staff-token" },
        body: JSON.stringify({
          message: "Can I set up a PT PMA for a cafe in Bali?",
        }),
      }),
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      mode: "demo",
      provider: "local-demo",
    });
    expect(global.fetch).toHaveBeenCalledWith(
      "https://backend.test/api/auth/profile",
      expect.objectContaining({
        method: "GET",
        headers: { Authorization: "Bearer staff-token" },
        redirect: "error",
      }),
    );
  });

  it("allows a Bali Zero job-title role session in production", async () => {
    vi.stubEnv("NODE_ENV", "production");
    process.env.VOICE_CONCIERGE_LAB_ENABLED = "true";
    process.env.VOICE_CONCIERGE_BACKEND_URL = "https://backend.test/api";
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          data: {
            id: "staff-2",
            email: "consultant@balizero.com",
            name: "Consultant",
            role: "Executive Consultant",
            language: "en",
          },
        }),
        { status: 200 },
      ),
    );

    const response = await POST(
      new Request("http://localhost/api/lab/voice-concierge", {
        method: "POST",
        headers: { cookie: "nz_access_token=consultant-token" },
        body: JSON.stringify({
          message: "Can I set up a PT PMA for a cafe in Bali?",
        }),
      }),
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      mode: "demo",
      provider: "local-demo",
    });
    expect(global.fetch).toHaveBeenCalledWith(
      "https://backend.test/api/auth/profile",
      expect.objectContaining({
        method: "GET",
        headers: { Authorization: "Bearer consultant-token" },
        redirect: "error",
      }),
    );
  });

  it("rejects a job-title role session without an internal email domain", async () => {
    vi.stubEnv("NODE_ENV", "production");
    process.env.VOICE_CONCIERGE_LAB_ENABLED = "true";
    process.env.VOICE_CONCIERGE_BACKEND_URL = "https://backend.test/api";
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          data: {
            id: "external-1",
            email: "consultant@example.com",
            name: "External Consultant",
            role: "Executive Consultant",
            role_level: "member",
            language: "en",
          },
        }),
        { status: 200 },
      ),
    );

    const response = await POST(
      new Request("http://localhost/api/lab/voice-concierge", {
        method: "POST",
        headers: { cookie: "nz_access_token=external-token" },
        body: JSON.stringify({
          message: "Can I set up a PT PMA for a cafe in Bali?",
        }),
      }),
    );

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toMatchObject({
      error: "voice_concierge_forbidden",
    });
  });

  it("rejects partner sessions even when the email domain is internal", async () => {
    vi.stubEnv("NODE_ENV", "production");
    process.env.VOICE_CONCIERGE_LAB_ENABLED = "true";
    process.env.VOICE_CONCIERGE_BACKEND_URL = "https://backend.test/api";
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          data: {
            id: "partner-1",
            email: "partner@balizero.com",
            name: "Partner",
            role: "partner",
            language: "en",
          },
        }),
        { status: 200 },
      ),
    );

    const response = await POST(
      new Request("http://localhost/api/lab/voice-concierge", {
        method: "POST",
        headers: { cookie: "nz_access_token=partner-token" },
        body: JSON.stringify({
          message: "Can I set up a PT PMA for a cafe in Bali?",
        }),
      }),
    );

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toMatchObject({
      error: "voice_concierge_forbidden",
    });
  });

  it("keeps the production technical token path for server-to-server text calls", async () => {
    vi.stubEnv("NODE_ENV", "production");
    process.env.VOICE_CONCIERGE_LAB_ENABLED = "true";
    process.env.VOICE_CONCIERGE_TEXT_TOKEN = "text-token";

    const response = await POST(
      new Request("http://localhost/api/lab/voice-concierge", {
        method: "POST",
        headers: { "x-voice-lab-token": "text-token" },
        body: JSON.stringify({
          message: "Can I set up a PT PMA for a cafe in Bali?",
        }),
      }),
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      mode: "demo",
      provider: "local-demo",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("blocks obvious PII before calling Gemini", async () => {
    const response = await POST(
      request({ message: "My passport is A1234567, can you check my visa?" }),
    );

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({
      error: "pii_not_allowed",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("blocks obvious PII in history before calling Gemini", async () => {
    process.env.GOOGLE_AI_STUDIO_API_KEY = "test-key";

    const response = await POST(
      request({
        message: "Can I set up a PT PMA?",
        history: [
          {
            role: "user",
            content: "Previous detail: my passport is A1234567",
          },
        ],
      }),
    );

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({
      error: "pii_not_allowed",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("blocks private client names before calling Gemini", async () => {
    process.env.GOOGLE_AI_STUDIO_API_KEY = "test-key";
    process.env.VOICE_CONCIERGE_ALLOW_CLOUD_TEXT = "true";

    const response = await POST(
      request({
        message: "My client is John Smith and he wants to open a PT PMA.",
      }),
    );

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({
      error: "pii_not_allowed",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("blocks private client names in history before calling Gemini", async () => {
    process.env.GOOGLE_AI_STUDIO_API_KEY = "test-key";
    process.env.VOICE_CONCIERGE_ALLOW_CLOUD_TEXT = "true";

    const response = await POST(
      request({
        message: "Can I set up a PT PMA?",
        history: [
          {
            role: "user",
            content: "Previous note: my client is John Smith.",
          },
        ],
      }),
    );

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({
      error: "pii_not_allowed",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("blocks private company names before calling Gemini", async () => {
    process.env.GOOGLE_AI_STUDIO_API_KEY = "test-key";
    process.env.VOICE_CONCIERGE_ALLOW_CLOUD_TEXT = "true";

    const response = await POST(
      request({
        message: "The company is PT Bali Sunrise and it needs tax help.",
      }),
    );

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({
      error: "pii_not_allowed",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("blocks private address details before calling Gemini", async () => {
    process.env.GOOGLE_AI_STUDIO_API_KEY = "test-key";
    process.env.VOICE_CONCIERGE_ALLOW_CLOUD_TEXT = "true";

    const response = await POST(
      request({
        message: "The address is Jalan Sunset Road 88, can we use it?",
      }),
    );

    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toMatchObject({
      error: "pii_not_allowed",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("returns demo mode when no AI Studio key is configured", async () => {
    const response = await POST(
      request({ message: "Can I set up a PT PMA for a cafe in Bali?" }),
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      mode: "demo",
      provider: "local-demo",
      intent: "company",
      next_action: "collect_non_pii_context",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("infers Italian locale and intent in demo mode", async () => {
    const response = await POST(
      request({ message: "Vorrei aprire una societa a Bali" }),
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      mode: "demo",
      provider: "local-demo",
      intent: "company",
      answer: expect.stringContaining("Per una PT PMA"),
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("does not call Gemini without an explicit cloud-text opt-in", async () => {
    process.env.GOOGLE_AI_STUDIO_API_KEY = "test-key";

    const response = await POST(
      request({ message: "Can I set up a PT PMA for a cafe in Bali?" }),
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      mode: "demo",
      provider: "local-demo",
      safety_note: "Cloud text concierge disabled, so no Gemini call was made.",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("calls Gemini and normalizes structured output when a key is configured", async () => {
    process.env.GOOGLE_AI_STUDIO_API_KEY = "test-key";
    process.env.GOOGLE_AI_STUDIO_MODEL = "gemini-test";
    process.env.VOICE_CONCIERGE_ALLOW_CLOUD_TEXT = "true";
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          candidates: [
            {
              content: {
                parts: [
                  {
                    text: JSON.stringify({
                      answer:
                        "A PT PMA can be appropriate, but first confirm KBLI and zoning.",
                      intent: "company",
                      risk_level: "medium",
                      next_action: "collect_non_pii_context",
                      quick_replies: ["Ask about KBLI", "Check zoning"],
                    }),
                  },
                ],
              },
            },
          ],
        }),
        { status: 200 },
      ),
    );

    const response = await POST(
      request({ message: "I want to open a cafe in Bali" }),
    );

    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body).toMatchObject({
      mode: "gemini",
      provider: "google-ai-studio",
      model: "gemini-test",
      intent: "company",
      next_action: "collect_non_pii_context",
    });
    expect(body.quick_replies).toEqual(["Ask about KBLI", "Check zoning"]);
    expect(global.fetch).toHaveBeenCalledWith(
      "https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent?key=test-key",
      expect.objectContaining({
        method: "POST",
        signal: expect.any(AbortSignal),
      }),
    );
  });

  it("does not forward prior history to Gemini even when cloud text is enabled", async () => {
    process.env.GOOGLE_AI_STUDIO_API_KEY = "test-key";
    process.env.VOICE_CONCIERGE_ALLOW_CLOUD_TEXT = "true";
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          candidates: [
            {
              content: {
                parts: [
                  {
                    text: JSON.stringify({
                      answer: "Start with KBLI and zoning.",
                      intent: "company",
                      risk_level: "medium",
                      next_action: "collect_non_pii_context",
                      quick_replies: ["Check KBLI"],
                    }),
                  },
                ],
              },
            },
          ],
        }),
        { status: 200 },
      ),
    );

    const response = await POST(
      request({
        message: "Can I open a cafe in Bali?",
        history: [
          {
            role: "user",
            content: "Previous harmless turn that should stay local.",
          },
        ],
      }),
    );

    expect(response.status).toBe(200);
    const [, init] = vi.mocked(global.fetch).mock.calls[0] ?? [];
    const geminiBody = JSON.parse(String(init?.body)) as {
      contents: Array<{ parts: Array<{ text: string }> }>;
    };
    expect(geminiBody.contents).toHaveLength(1);
    expect(JSON.stringify(geminiBody)).not.toContain("Previous harmless turn");
  });

  it("sends the inferred Italian locale to Gemini", async () => {
    process.env.GOOGLE_AI_STUDIO_API_KEY = "test-key";
    process.env.VOICE_CONCIERGE_ALLOW_CLOUD_TEXT = "true";
    vi.mocked(global.fetch).mockResolvedValue(
      new Response(
        JSON.stringify({
          candidates: [
            {
              content: {
                parts: [
                  {
                    text: JSON.stringify({
                      answer: "Per una PT PMA, iniziamo da KBLI e zoning.",
                      intent: "company",
                      risk_level: "medium",
                      next_action: "collect_non_pii_context",
                      quick_replies: ["Verifica KBLI"],
                    }),
                  },
                ],
              },
            },
          ],
        }),
        { status: 200 },
      ),
    );

    const response = await POST(
      request({ message: "Vorrei aprire una societa a Bali" }),
    );

    expect(response.status).toBe(200);
    const [, init] = vi.mocked(global.fetch).mock.calls[0] ?? [];
    const geminiBody = JSON.parse(String(init?.body)) as {
      contents: Array<{ parts: Array<{ text: string }> }>;
    };
    const lastContent = geminiBody.contents[geminiBody.contents.length - 1];
    expect(lastContent?.parts[0]?.text).toContain("Locale preference: it");
  });

  it("hides Gemini network failure details", async () => {
    process.env.GOOGLE_AI_STUDIO_API_KEY = "test-key";
    process.env.VOICE_CONCIERGE_ALLOW_CLOUD_TEXT = "true";
    vi.mocked(global.fetch).mockRejectedValue(
      new Error("private network detail"),
    );

    const response = await POST(
      request({ message: "Can I open a cafe in Bali?" }),
    );

    expect(response.status).toBe(502);
    await expect(response.json()).resolves.toEqual({
      error: "gemini_request_failed",
    });
  });
});
