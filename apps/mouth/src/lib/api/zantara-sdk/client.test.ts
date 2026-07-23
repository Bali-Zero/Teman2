import { beforeEach, describe, expect, it, vi } from "vitest";
import { createZantaraSDK, ZantaraSDK } from "./client";

const fetchMock = vi.mocked(global.fetch);

function jsonResponse(
  body: unknown,
  init: { ok?: boolean; status?: number; statusText?: string } = {},
): Response {
  return {
    ok: init.ok ?? true,
    status: init.status ?? 200,
    statusText: init.statusText ?? "OK",
    json: vi.fn().mockResolvedValue(body),
    blob: vi
      .fn()
      .mockResolvedValue(new Blob(["audio"], { type: "audio/mpeg" })),
  } as unknown as Response;
}

describe("ZantaraSDK", () => {
  beforeEach(() => {
    fetchMock.mockReset();
  });

  it("creates SDK instances and trims trailing slashes from baseUrl", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ answer: "ok" }));

    const sdk = createZantaraSDK({
      baseUrl: "https://api.example.com/",
      apiKey: "token-123",
    });
    const result = await sdk.queryAgenticRAG({
      query: "What KBLI fits a restaurant?",
    } as never);

    expect(sdk).toBeInstanceOf(ZantaraSDK);
    expect(result).toEqual({ answer: "ok" });
    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.example.com/api/agentic-rag/query",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          Authorization: "Bearer token-123",
        }),
        body: JSON.stringify({ query: "What KBLI fits a restaurant?" }),
        signal: expect.any(AbortSignal),
      }),
    );
  });

  it("serializes optional query parameters for memory and timeline endpoints", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse([{ id: "collective-1" }]))
      .mockResolvedValueOnce(jsonResponse([{ id: "event-1" }]));

    const sdk = new ZantaraSDK({ baseUrl: "https://api.example.com" });

    await expect(sdk.getCollectiveMemory("visa", 3)).resolves.toEqual([
      { id: "collective-1" },
    ]);
    await expect(
      sdk.getEpisodicTimeline({
        user_id: "user-1",
        start_date: "2026-01-01",
        emotion: "concern",
        limit: 25,
      } as never),
    ).resolves.toEqual([{ id: "event-1" }]);

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "https://api.example.com/api/collective-memory?category=visa&limit=3",
      expect.any(Object),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "https://api.example.com/api/episodic-memory/timeline?user_id=user-1&start_date=2026-01-01&emotion=concern&limit=25",
      expect.any(Object),
    );
  });

  it("unwraps paginated compliance alerts and serializes pagination", async () => {
    const alert = { alert_id: "alert-1", status: "sent" };
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ items: [alert], limit: 25, offset: 50 }),
    );

    const sdk = new ZantaraSDK({ baseUrl: "https://api.example.com" });

    await expect(
      sdk.getComplianceAlerts("42", "sent", 25, 50),
    ).resolves.toEqual([alert]);
    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.example.com/api/compliance/alerts?client_id=42&status=sent&limit=25&offset=50",
      expect.any(Object),
    );
  });

  it("returns the backend acknowledgement outcome contract", async () => {
    const outcome = {
      alert_id: "alert-1",
      outcome: "acknowledged",
      status: "acknowledged",
    };
    fetchMock.mockResolvedValueOnce(jsonResponse(outcome));

    const sdk = new ZantaraSDK({ baseUrl: "https://api.example.com" });

    await expect(sdk.acknowledgeAlert("alert-1")).resolves.toEqual(outcome);
    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.example.com/api/compliance/alerts/alert-1/outcome",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ outcome: "acknowledged" }),
      }),
    );
  });

  it("throws API errors returned as JSON", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        { message: "Unauthorized", code: "UNAUTHORIZED" },
        { ok: false, status: 401, statusText: "Unauthorized" },
      ),
    );

    const sdk = new ZantaraSDK({ baseUrl: "https://api.example.com" });

    await expect(sdk.getUserMemory("user-1")).rejects.toEqual({
      message: "Unauthorized",
      code: "UNAUTHORIZED",
    });
  });

  it("throws a fallback API error when the error response body is not JSON", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 502,
      statusText: "Bad Gateway",
      json: vi.fn().mockRejectedValue(new Error("not json")),
    } as unknown as Response);

    const sdk = new ZantaraSDK({ baseUrl: "https://api.example.com" });

    await expect(sdk.getJourney("journey-1")).rejects.toEqual({
      message: "HTTP 502: Bad Gateway",
      code: "HTTP_502",
    });
  });

  it("normalizes AbortError failures to TIMEOUT API errors", async () => {
    const abortError = Object.assign(new Error("aborted"), {
      name: "AbortError",
    });
    fetchMock.mockRejectedValueOnce(abortError);

    const sdk = new ZantaraSDK({
      baseUrl: "https://api.example.com",
      timeout: 1,
    });

    await expect(sdk.getTeamInsights()).rejects.toEqual({
      message: "Request timeout",
      code: "TIMEOUT",
    });
  });

  it("uses multipart upload for transcription with optional auth header", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ text: "hello" }));

    const sdk = new ZantaraSDK({
      baseUrl: "https://api.example.com/",
      apiKey: "token-123",
    });
    const result = await sdk.transcribeAudio({
      file: new File(["abc"], "sample.wav", { type: "audio/wav" }),
      language: "en",
    });

    expect(result).toEqual({ text: "hello" });
    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.example.com/audio/transcribe",
      expect.objectContaining({
        method: "POST",
        body: expect.any(FormData),
        headers: { Authorization: "Bearer token-123" },
      }),
    );
  });

  it("returns speech blobs from the audio endpoint", async () => {
    const blob = new Blob(["voice"], { type: "audio/mpeg" });
    fetchMock.mockResolvedValueOnce({
      ok: true,
      blob: vi.fn().mockResolvedValue(blob),
    } as unknown as Response);

    const sdk = new ZantaraSDK({ baseUrl: "https://api.example.com" });

    await expect(sdk.generateSpeech({ text: "hello" } as never)).resolves.toBe(
      blob,
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.example.com/audio/speech",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: "hello" }),
      }),
    );
  });
});
