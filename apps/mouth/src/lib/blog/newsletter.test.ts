import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
  type Mock,
} from "vitest";
import type {
  Article,
  ArticleListItem,
  NewsletterSubscriber,
  NewsletterSubscribeRequest,
} from "./types";

const loggerMock = vi.hoisted(() => ({
  error: vi.fn(),
  warn: vi.fn(),
}));

vi.mock("../logger", () => ({
  logger: loggerMock,
}));

const fetchMock = global.fetch as Mock;

async function loadNewsletterModule(): Promise<typeof import("./newsletter")> {
  vi.resetModules();
  vi.stubEnv("NEXT_PUBLIC_ZANTARA_API_URL", "https://api.test");
  vi.stubEnv("ZANTARA_API_KEY", "test-api-key");
  return import("./newsletter");
}

function jsonResponse(body: unknown, ok = true): Response {
  return {
    ok,
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response;
}

const subscribeRequest: NewsletterSubscribeRequest = {
  email: "reader@example.com",
  name: "Ayu Reader",
  categories: ["business", "property"],
  frequency: "weekly",
  language: "en",
};

const subscriber: NewsletterSubscriber = {
  id: "sub-1",
  email: "reader@example.com",
  name: "Ayu Reader",
  categories: ["business", "property"],
  frequency: "weekly",
  language: "en",
  subscribedAt: new Date("2026-01-01T00:00:00.000Z"),
  confirmed: true,
};

const author = {
  id: "author-1",
  name: "Bali Zero",
  avatar: "https://cdn.test/avatar.png",
  role: "Editor",
  isAI: false,
};

const article: Article = {
  id: "article-1",
  slug: "new-bali-rules",
  title: "New Bali Business Rules",
  excerpt: "What operators need to know this week.",
  content: "Full article",
  coverImage: "https://cdn.test/cover.png",
  coverImageAlt: "Bali storefront",
  category: "business",
  tags: ["oss", "business"],
  author,
  createdAt: new Date("2026-01-01T00:00:00.000Z"),
  updatedAt: new Date("2026-01-02T00:00:00.000Z"),
  publishedAt: new Date("2026-01-03T00:00:00.000Z"),
  status: "published",
  featured: false,
  trending: false,
  readingTime: 6,
  viewCount: 120,
  shareCount: 5,
  likeCount: 8,
  commentCount: 1,
  aiGenerated: false,
  relatedArticleIds: [],
  locale: "en",
  autoNotifyClients: true,
};

const digestArticle: ArticleListItem = {
  id: "article-1",
  slug: "new-bali-rules",
  title: "New Bali Business Rules",
  excerpt: "What operators need to know this week.",
  coverImage: "https://cdn.test/cover.png",
  category: "business",
  author,
  publishedAt: new Date("2026-01-03T00:00:00.000Z"),
  readingTime: 6,
  viewCount: 120,
  featured: false,
  trending: false,
  aiGenerated: false,
};

describe("NewsletterService", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    loggerMock.error.mockReset();
    loggerMock.warn.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("subscribes a reader and sends a confirmation email", async () => {
    const { subscribeToNewsletter } = await loadNewsletterModule();
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ subscriber }))
      .mockResolvedValueOnce(jsonResponse({ queued: true }));

    const result = await subscribeToNewsletter(subscribeRequest);

    expect(result).toEqual({
      success: true,
      subscriberId: "sub-1",
      message: "Please check your email to confirm your subscription.",
    });
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "https://api.test/api/blog/newsletter/subscribe",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(subscribeRequest),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "https://api.test/api/email/send",
      expect.objectContaining({
        method: "POST",
        body: expect.stringContaining("reader@example.com"),
      }),
    );
    expect(loggerMock.warn).toHaveBeenCalledWith(
      "Zoho integration not configured",
      expect.objectContaining({ action: "syncToZoho" }),
    );
  });

  it("returns backend subscription errors without sending follow-up email", async () => {
    const { subscribeToNewsletter } = await loadNewsletterModule();
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ message: "Already subscribed" }, false),
    );

    const result = await subscribeToNewsletter(subscribeRequest);

    expect(result).toEqual({
      success: false,
      message: "Already subscribed",
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("returns false and logs when unsubscribe fails at the network layer", async () => {
    const { unsubscribeFromNewsletter } = await loadNewsletterModule();
    fetchMock.mockRejectedValueOnce(new Error("offline"));

    await expect(unsubscribeFromNewsletter("sub-1")).resolves.toBe(false);
    expect(loggerMock.error).toHaveBeenCalledWith(
      "Newsletter unsubscribe failed",
      expect.objectContaining({ action: "unsubscribe" }),
      expect.any(Error),
    );
  });

  it("posts preference updates and returns the backend status", async () => {
    const { NewsletterService } = await loadNewsletterModule();
    fetchMock.mockResolvedValueOnce(jsonResponse({ ok: true }));

    const result = await NewsletterService.updatePreferences("sub-1", {
      categories: ["taxes"],
      frequency: "monthly",
    });

    expect(result).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.test/api/blog/newsletter/preferences",
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

  it("sends article newsletters in batches and counts rejected email sends", async () => {
    vi.useFakeTimers();
    const { sendArticleNewsletter } = await loadNewsletterModule();
    const secondSubscriber = { ...subscriber, id: "sub-2", email: "b@example.com" };
    fetchMock
      .mockResolvedValueOnce(jsonResponse(article))
      .mockResolvedValueOnce(jsonResponse({ subscribers: [subscriber, secondSubscriber] }))
      .mockResolvedValueOnce(jsonResponse({ queued: true }))
      .mockRejectedValueOnce(new Error("email failed"))
      .mockResolvedValueOnce(jsonResponse({ logged: true }));

    const promise = sendArticleNewsletter("article-1");
    await vi.runAllTimersAsync();
    const result = await promise;

    expect(result).toEqual({ sent: 1, failed: 1 });
    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.test/api/blog/newsletter/log",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          articleId: "article-1",
          recipientCount: 2,
          sentCount: 1,
          failedCount: 1,
        }),
      }),
    );
  });

  it("returns early when an article newsletter has no subscribers", async () => {
    const { sendArticleNewsletter } = await loadNewsletterModule();
    fetchMock
      .mockResolvedValueOnce(jsonResponse(article))
      .mockResolvedValueOnce(jsonResponse({ subscribers: [] }));

    await expect(sendArticleNewsletter("article-1")).resolves.toEqual({
      sent: 0,
      failed: 0,
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("sends weekly digest only to subscribers with matching categories", async () => {
    const { sendWeeklyDigest } = await loadNewsletterModule();
    const propertyOnlySubscriber = {
      ...subscriber,
      id: "sub-2",
      email: "property@example.com",
      categories: ["property"] as const,
    };
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ articles: [digestArticle] }))
      .mockResolvedValueOnce(
        jsonResponse({ subscribers: [subscriber, propertyOnlySubscriber] }),
      )
      .mockResolvedValueOnce(jsonResponse({ queued: true }));

    const result = await sendWeeklyDigest();

    expect(result).toEqual({ sent: 1, articlesIncluded: 1 });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock).toHaveBeenLastCalledWith(
      "https://api.test/api/email/send",
      expect.objectContaining({
        method: "POST",
        body: expect.stringContaining("reader@example.com"),
      }),
    );
  });

  it("notifies only matched clients that have WhatsApp numbers", async () => {
    const { notifyClients } = await loadNewsletterModule();
    fetchMock
      .mockResolvedValueOnce(jsonResponse(article))
      .mockResolvedValueOnce(
        jsonResponse({
          clients: [
            { id: "client-1", name: "Ayu", whatsapp: "+628111" },
            { id: "client-2", name: "No Phone" },
          ],
        }),
      )
      .mockResolvedValueOnce(jsonResponse({ sent: true }));

    const result = await notifyClients("article-1");

    expect(result).toBe(1);
    expect(fetchMock).toHaveBeenLastCalledWith(
      "https://api.test/api/whatsapp/send",
      expect.objectContaining({
        method: "POST",
        body: expect.stringContaining("+628111"),
      }),
    );
  });

  it("does not notify clients when article auto notification is disabled", async () => {
    const { notifyClients } = await loadNewsletterModule();
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ ...article, autoNotifyClients: false }),
    );

    await expect(notifyClients("article-1")).resolves.toBe(0);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
