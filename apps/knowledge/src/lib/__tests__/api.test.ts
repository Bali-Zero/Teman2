import { describe, it, expect, vi, beforeEach } from "vitest";
import { KnowledgeApi, KnowledgeActivityApi } from "../api";

// Mock logger
vi.mock("@/lib/logger", () => ({
  logger: {
    error: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
    warn: vi.fn(),
  },
}));

describe("KnowledgeApi", () => {
  let api: KnowledgeApi;

  beforeEach(() => {
    api = new KnowledgeApi();
    vi.clearAllMocks();
    (global.fetch as ReturnType<typeof vi.fn>).mockReset();
  });

  describe("searchDocs", () => {
    it("sends POST request with correct payload", async () => {
      const mockResponse = {
        results: [
          {
            text: "KITAS visa information",
            metadata: {
              book_title: "Visa Guide",
              book_author: "BZ",
              tier: "S",
              min_level: 1,
              chunk_index: 0,
              file_path: "/docs/visa.md",
              total_chunks: 10,
              collection: "visa_docs",
              title: "KITAS Overview",
            },
            similarity_score: 0.85,
          },
        ],
        total: 1,
        query: "visa",
        execution_time_ms: 150,
      };

      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await api.searchDocs({ query: "visa", limit: 20 });

      expect(result.results).toHaveLength(1);
      expect(result.results[0].text).toContain("KITAS");
      expect(result.query).toBe("visa");

      const [url, options] = (global.fetch as ReturnType<typeof vi.fn>).mock
        .calls[0];
      expect(url).toContain("/api/search/");
      expect(options.method).toBe("POST");
      const body = JSON.parse(options.body);
      expect(body.query).toBe("visa");
      expect(body.limit).toBe(20);
    });

    it("clamps level between 0 and 3", async () => {
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ results: [], total: 0, query: "test" }),
      });

      await api.searchDocs({ query: "test", level: 10 });

      const body = JSON.parse(
        (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].body,
      );
      expect(body.level).toBe(3);
    });

    it("clamps limit between 1 and 50", async () => {
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ results: [], total: 0, query: "test" }),
      });

      await api.searchDocs({ query: "test", limit: 100 });

      const body = JSON.parse(
        (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].body,
      );
      expect(body.limit).toBe(50);
    });

    it("throws on HTTP error", async () => {
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
      });

      await expect(api.searchDocs({ query: "test" })).rejects.toThrow(
        "HTTP 500",
      );
    });

    it("uses default values for optional params", async () => {
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ results: [], total: 0, query: "test" }),
      });

      await api.searchDocs({ query: "test" });

      const body = JSON.parse(
        (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].body,
      );
      expect(body.level).toBe(1);
      expect(body.limit).toBe(8);
      expect(body.collection).toBeNull();
      expect(body.tier_filter).toBeNull();
    });
  });
});

describe("KnowledgeActivityApi", () => {
  let activityApi: KnowledgeActivityApi;

  beforeEach(() => {
    activityApi = new KnowledgeActivityApi();
    vi.clearAllMocks();
    (global.fetch as ReturnType<typeof vi.fn>).mockReset();
  });

  describe("logView", () => {
    it("sends view activity log", async () => {
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({}),
      });

      await activityApi.logView("knowledge_hub", "doc-1", "Title", "visa");

      const [url, options] = (global.fetch as ReturnType<typeof vi.fn>).mock
        .calls[0];
      expect(url).toContain("/api/knowledge/activity/log");
      const body = JSON.parse(options.body);
      expect(body.action_type).toBe("view");
      expect(body.resource_type).toBe("knowledge_hub");
      expect(body.resource_id).toBe("doc-1");
    });
  });

  describe("logDownload", () => {
    it("sends download activity log", async () => {
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({}),
      });

      await activityApi.logDownload("document", "doc-2", "Report");

      const body = JSON.parse(
        (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].body,
      );
      expect(body.action_type).toBe("download");
    });
  });

  describe("logActivity", () => {
    it("silently catches errors (non-critical)", async () => {
      (global.fetch as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
        new Error("Network error"),
      );

      // Should not throw
      await activityApi.logView("hub");
    });
  });
});
