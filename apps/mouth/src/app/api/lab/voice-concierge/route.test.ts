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

  beforeEach(() => {
    vi.restoreAllMocks();
    delete process.env.GOOGLE_AI_STUDIO_API_KEY;
    delete process.env.GEMINI_API_KEY;
    delete process.env.GOOGLE_AI_STUDIO_MODEL;
    delete process.env.VOICE_CONCIERGE_LAB_ENABLED;
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

  it("calls Gemini and normalizes structured output when a key is configured", async () => {
    process.env.GOOGLE_AI_STUDIO_API_KEY = "test-key";
    process.env.GOOGLE_AI_STUDIO_MODEL = "gemini-test";
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
      expect.objectContaining({ method: "POST" }),
    );
  });
});
