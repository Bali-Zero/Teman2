import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const loggerMock = vi.hoisted(() => ({
  error: vi.fn(),
  warn: vi.fn(),
}));

vi.mock("../logger", () => ({
  logger: loggerMock,
}));

const fetchMock = vi.mocked(global.fetch);

function jsonResponse(body: unknown, ok = true): Response {
  return {
    ok,
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response;
}

async function loadNewsletterService() {
  vi.resetModules();
  vi.stubEnv("NEXT_PUBLIC_ZANTARA_API_URL", "https://zantara.test");
  vi.stubEnv("ZANTARA_API_KEY", "api-key");
  return (await import("./newsletter")).NewsletterService;
}

describe("NewsletterService", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    loggerMock.error.mockReset();
    loggerMock.warn.mockReset();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("subscribes, skips unconfigured Zoho sync, and sends confirmation email", async () => {
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse({
          subscriber: {
            id: "sub-1",
            email: "client@example.com",
            name: "Client Name",
            categories: ["business"],
            frequency: "weekly",
            language: "en",
          },
        }),
      )
      .mockResolvedValueOnce(jsonResponse({ success: true }));
    const NewsletterService = await loadNewsletterService();

    await expect(
      NewsletterService.subscribe({
        email: "client@example.com",
        name: "Client Name",
        categories: ["business"],
        frequency: "weekly",
        language: "en",
      }),
    ).resolves.toEqual({
      success: true,
      subscriberId: "sub-1",
      message: "Please check your email to confirm your subscription.",
    });

    expect(loggerMock.warn).toHaveBeenCalledWith(
      "Zoho integration not configured",
      expect.objectContaining({
        component: "NewsletterService",
        action: "syncToZoho",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "https://zantara.test/api/blog/newsletter/subscribe",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "https://zantara.test/api/email/send",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer api-key",
        }),
      }),
    );
  });

  it("returns backend subscription errors without sending confirmation email", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ message: "Already subscribed" }, false),
    );
    const NewsletterService = await loadNewsletterService();

    await expect(
      NewsletterService.subscribe({
        email: "client@example.com",
        categories: ["business"],
        frequency: "weekly",
        language: "en",
      }),
    ).resolves.toEqual({
      success: false,
      message: "Already subscribed",
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("maps confirm, unsubscribe, and preference updates to boolean outcomes", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ ok: true }, true))
      .mockResolvedValueOnce(jsonResponse({ ok: false }, false))
      .mockResolvedValueOnce(jsonResponse({ ok: true }, true));
    const NewsletterService = await loadNewsletterService();

    await expect(
      NewsletterService.confirmSubscription("sub-1", "token"),
    ).resolves.toBe(true);
    await expect(NewsletterService.unsubscribe("sub-1")).resolves.toBe(false);
    await expect(
      NewsletterService.updatePreferences("sub-1", {
        categories: ["taxes"],
        frequency: "monthly",
      }),
    ).resolves.toBe(true);

    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "https://zantara.test/api/blog/newsletter/preferences",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({
          subscriberId: "sub-1",
          categories: ["taxes"],
          frequency: "monthly",
        }),
      }),
    );
  });

  it("short-circuits article newsletters when no confirmed subscriber matches", async () => {
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse({
          id: "article-1",
          title: "Bali business update",
          category: "business",
        }),
      )
      .mockResolvedValueOnce(jsonResponse({ subscribers: [] }));
    const NewsletterService = await loadNewsletterService();

    await expect(
      NewsletterService.sendArticleNewsletter("article-1"),
    ).resolves.toEqual({ sent: 0, failed: 0 });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("short-circuits weekly digest when there are no published articles", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ articles: [] }));
    const NewsletterService = await loadNewsletterService();

    await expect(NewsletterService.sendWeeklyDigest()).resolves.toEqual({
      sent: 0,
      articlesIncluded: 0,
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("notifies only matched clients that have WhatsApp numbers", async () => {
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse({
          id: "article-1",
          title: "Tax deadline",
          slug: "tax-deadline",
          category: "taxes",
          tags: ["tax"],
          autoNotifyClients: true,
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          clients: [
            { id: 1, name: "Marta", whatsapp: "+628111111" },
            { id: 2, name: "No Phone" },
          ],
        }),
      )
      .mockResolvedValueOnce(jsonResponse({ success: true }));
    const NewsletterService = await loadNewsletterService();

    await expect(
      NewsletterService.notifyRelevantClients("article-1"),
    ).resolves.toBe(1);
    expect(fetchMock).toHaveBeenLastCalledWith(
      "https://zantara.test/api/whatsapp/send",
      expect.objectContaining({
        method: "POST",
        body: expect.stringContaining("+628111111"),
      }),
    );
  });
});
