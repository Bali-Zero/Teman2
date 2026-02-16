import { describe, it, expect, vi, beforeEach } from "vitest";
import { WorkflowApi } from "./index";
import { ApiClient } from "../api-client";

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe("WorkflowApi", () => {
  let api: ApiClient;
  let workflowApi: WorkflowApi;
  const baseUrl = "https://api.test.com";

  beforeEach(() => {
    vi.restoreAllMocks();
    mockFetch.mockReset();
    api = new ApiClient(baseUrl);
    workflowApi = new WorkflowApi(api as any);
  });

  describe("getEnrichment", () => {
    it("should call the correct endpoint", async () => {
      const mockResponse = { data: "enriched" };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => mockResponse,
      });

      const result = await workflowApi.getEnrichment(123);

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/workflow/conversations/123/enrichment"),
        expect.objectContaining({ method: "GET" }),
      );
      expect(result).toEqual(mockResponse);
    });
  });

  describe("assign", () => {
    it("should call the correct endpoint with user_id", async () => {
      const mockResponse = { success: true };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => mockResponse,
      });

      const result = await workflowApi.assign(123, "user-456");

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/workflow/conversations/123/assign"),
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ assigned_to: "user-456" }),
        }),
      );
      expect(result).toEqual(mockResponse);
    });
  });

  describe("updateStatus", () => {
    it("should call the correct endpoint with status", async () => {
      const mockResponse = { success: true };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => mockResponse,
      });

      const result = await workflowApi.updateStatus(123, "closed");

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/workflow/conversations/123/status"),
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ status: "closed" }),
        }),
      );
      expect(result).toEqual(mockResponse);
    });
  });

  describe("getNotes", () => {
    it("should call the correct endpoint", async () => {
      const mockResponse = [{ id: 1, content: "test note" }];
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => mockResponse,
      });

      const result = await workflowApi.getNotes(123);

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/workflow/conversations/123/notes"),
        expect.objectContaining({ method: "GET" }),
      );
      expect(result).toEqual(mockResponse);
    });
  });

  describe("addNote", () => {
    it("should call the correct endpoint with note details", async () => {
      const mockResponse = { success: true, id: 1 };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => mockResponse,
      });

      const result = await workflowApi.addNote(
        123,
        "New note",
        "user-456",
        "John Doe",
      );

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/workflow/conversations/123/notes"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            content: "New note",
            author_id: "user-456",
            author_name: "John Doe",
          }),
        }),
      );
      expect(result).toEqual(mockResponse);
    });
  });
});
