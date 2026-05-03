import { describe, it, expect, vi, beforeEach } from "vitest";
import { KnowledgeApi } from "../knowledge.api";
import type { IApiClient } from "../../types/api-client.types";
import type { KnowledgeSearchResponse, TierLevel } from "../knowledge.types";

describe("KnowledgeApi", () => {
  let knowledgeApi: KnowledgeApi;
  let mockClient: IApiClient;

  beforeEach(() => {
    mockClient = {
      request: vi.fn(),
      isAdmin: vi.fn(() => false),
    } as any;
    knowledgeApi = new KnowledgeApi(mockClient);
  });

  describe("searchDocs", () => {
    it("should search documents with default parameters", async () => {
      const mockResponse: KnowledgeSearchResponse = {
        results: [
          {
            text: "Test content",
            metadata: {
              book_title: "Test Book",
              book_author: "Test Author",
              tier: "A" as TierLevel,
              min_level: 1,
              chunk_index: 0,
              file_path: "/test/path",
              total_chunks: 1,
              title: "Test Doc",
            },
            similarity_score: 0.95,
          },
        ],
        total: 1,
        query: "test query",
      };

      vi.mocked(mockClient.request).mockResolvedValue(mockResponse);

      const result = await knowledgeApi.searchDocs({ query: "test query" });

      expect(mockClient.request).toHaveBeenCalledWith("/api/search/", {
        method: "POST",
        body: JSON.stringify({
          query: "test query",
          level: 1,
          limit: 8,
          collection: null,
          tier_filter: null,
        }),
      });
      expect(result).toEqual(mockResponse);
    });

    it("should use admin level when user is admin", async () => {
      vi.mocked(mockClient.isAdmin).mockReturnValue(true);

      const mockResponse: KnowledgeSearchResponse = {
        results: [],
        total: 0,
        query: "admin query",
      };

      vi.mocked(mockClient.request).mockResolvedValue(mockResponse);

      await knowledgeApi.searchDocs({ query: "admin query" });

      expect(mockClient.request).toHaveBeenCalledWith("/api/search/", {
        method: "POST",
        body: expect.stringContaining('"level":3'),
      });
    });

    it("should respect custom level parameter", async () => {
      const mockResponse = { results: [], total: 0, query: "test" } as any;
      vi.mocked(mockClient.request).mockResolvedValue(mockResponse);

      await knowledgeApi.searchDocs({ query: "test", level: 2 });

      expect(mockClient.request).toHaveBeenCalledWith("/api/search/", {
        method: "POST",
        body: expect.stringContaining('"level":2'),
      });
    });

    it("should clamp level to maximum of 3", async () => {
      const mockResponse = { results: [], total: 0, query: "test" } as any;
      vi.mocked(mockClient.request).mockResolvedValue(mockResponse);

      await knowledgeApi.searchDocs({ query: "test", level: 10 });

      expect(mockClient.request).toHaveBeenCalledWith("/api/search/", {
        method: "POST",
        body: expect.stringContaining('"level":3'),
      });
    });

    it("should clamp level to minimum of 0", async () => {
      const mockResponse = { results: [], total: 0, query: "test" } as any;
      vi.mocked(mockClient.request).mockResolvedValue(mockResponse);

      await knowledgeApi.searchDocs({ query: "test", level: -5 });

      expect(mockClient.request).toHaveBeenCalledWith("/api/search/", {
        method: "POST",
        body: expect.stringContaining('"level":0'),
      });
    });

    it("should respect custom limit parameter", async () => {
      const mockResponse = { results: [], total: 0, query: "test" } as any;
      vi.mocked(mockClient.request).mockResolvedValue(mockResponse);

      await knowledgeApi.searchDocs({ query: "test", limit: 20 });

      expect(mockClient.request).toHaveBeenCalledWith("/api/search/", {
        method: "POST",
        body: expect.stringContaining('"limit":20'),
      });
    });

    it("should clamp limit to maximum of 50", async () => {
      const mockResponse = { results: [], total: 0, query: "test" } as any;
      vi.mocked(mockClient.request).mockResolvedValue(mockResponse);

      await knowledgeApi.searchDocs({ query: "test", limit: 100 });

      expect(mockClient.request).toHaveBeenCalledWith("/api/search/", {
        method: "POST",
        body: expect.stringContaining('"limit":50'),
      });
    });

    it("should clamp limit to minimum of 1", async () => {
      const mockResponse = { results: [], total: 0, query: "test" } as any;
      vi.mocked(mockClient.request).mockResolvedValue(mockResponse);

      await knowledgeApi.searchDocs({ query: "test", limit: 0 });

      expect(mockClient.request).toHaveBeenCalledWith("/api/search/", {
        method: "POST",
        body: expect.stringContaining('"limit":1'),
      });
    });

    it("should include collection parameter when provided", async () => {
      const mockResponse = { results: [], total: 0, query: "test" } as any;
      vi.mocked(mockClient.request).mockResolvedValue(mockResponse);

      await knowledgeApi.searchDocs({ query: "test", collection: "docs" });

      expect(mockClient.request).toHaveBeenCalledWith("/api/search/", {
        method: "POST",
        body: expect.stringContaining('"collection":"docs"'),
      });
    });

    it("should include tier_filter when provided", async () => {
      const mockResponse = { results: [], total: 0, query: "test" } as any;
      vi.mocked(mockClient.request).mockResolvedValue(mockResponse);

      await knowledgeApi.searchDocs({
        query: "test",
        tier_filter: ["A", "S"] as TierLevel[],
      });

      expect(mockClient.request).toHaveBeenCalledWith("/api/search/", {
        method: "POST",
        body: expect.stringContaining('"tier_filter":["A","S"]'),
      });
    });

    it("should handle empty results", async () => {
      const mockResponse = {
        results: [],
        total: 0,
        query: "nonexistent",
      } as any;

      vi.mocked(mockClient.request).mockResolvedValue(mockResponse);

      const result = await knowledgeApi.searchDocs({ query: "nonexistent" });

      expect(result.results).toHaveLength(0);
      expect(result.total).toBe(0);
    });

    it("should handle multiple results", async () => {
      const mockResponse = {
        results: [
          { text: "Content 1", metadata: {} as any, similarity_score: 0.95 },
          { text: "Content 2", metadata: {} as any, similarity_score: 0.85 },
          { text: "Content 3", metadata: {} as any, similarity_score: 0.75 },
        ],
        total: 3,
        query: "test",
      } as any;

      vi.mocked(mockClient.request).mockResolvedValue(mockResponse);

      const result = await knowledgeApi.searchDocs({ query: "test" });

      expect(result.results).toHaveLength(3);
      expect(result.total).toBe(3);
    });

    it("should handle API errors", async () => {
      vi.mocked(mockClient.request).mockRejectedValue(new Error("API Error"));

      await expect(knowledgeApi.searchDocs({ query: "test" })).rejects.toThrow(
        "API Error",
      );
    });

    it("should handle network errors", async () => {
      vi.mocked(mockClient.request).mockRejectedValue(
        new Error("Network error"),
      );

      await expect(knowledgeApi.searchDocs({ query: "test" })).rejects.toThrow(
        "Network error",
      );
    });
  });
});
