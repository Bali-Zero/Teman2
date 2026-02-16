import { describe, it, expect, vi, beforeEach } from "vitest";
import { ConversationsApi } from "../conversations.api";
import type { IApiClient } from "../../types/api-client.types";

describe("ConversationsApi", () => {
  let conversationsApi: ConversationsApi;
  let mockClient: IApiClient;

  beforeEach(() => {
    mockClient = {
      request: vi.fn(),
    } as any;
    conversationsApi = new ConversationsApi(mockClient);
  });

  describe("getConversationHistory", () => {
    it("should get conversation history without session ID", async () => {
      const mockResponse = {
        success: true,
        messages: [
          { role: "user", content: "Hello" },
          { role: "assistant", content: "Hi there!" },
        ],
      };

      vi.mocked(mockClient.request).mockResolvedValue(mockResponse);

      const result = await conversationsApi.getConversationHistory();

      expect(mockClient.request).toHaveBeenCalledWith(
        "/api/bali-zero/conversations/history?limit=50",
      );
      expect(result).toEqual(mockResponse);
    });

    it("should get conversation history with session ID", async () => {
      const mockResponse = {
        success: true,
        messages: [],
      };

      vi.mocked(mockClient.request).mockResolvedValue(mockResponse);

      await conversationsApi.getConversationHistory("session-123");

      expect(mockClient.request).toHaveBeenCalledWith(
        "/api/bali-zero/conversations/history?session_id=session-123&limit=50",
      );
    });
  });

  describe("saveConversation", () => {
    it("should save conversation with messages", async () => {
      const messages = [
        { role: "user", content: "Hello" },
        { role: "assistant", content: "Hi!" },
      ];

      const mockResponse = {
        success: true,
        conversation_id: 123,
        messages_saved: 2,
      };

      vi.mocked(mockClient.request).mockResolvedValue(mockResponse);

      const result = await conversationsApi.saveConversation(messages);

      expect(mockClient.request).toHaveBeenCalledWith(
        "/api/bali-zero/conversations/save",
        {
          method: "POST",
          body: JSON.stringify({
            messages,
            session_id: undefined,
            metadata: undefined,
          }),
        },
      );
      expect(result).toEqual(mockResponse);
    });

    it("should save conversation with session ID", async () => {
      const messages = [{ role: "user", content: "Test" }];

      const mockResponse = {
        success: true,
        conversation_id: 456,
        messages_saved: 1,
      };

      vi.mocked(mockClient.request).mockResolvedValue(mockResponse);

      await conversationsApi.saveConversation(messages, "session-456");

      expect(mockClient.request).toHaveBeenCalledWith(
        "/api/bali-zero/conversations/save",
        {
          method: "POST",
          body: expect.stringContaining('"session_id":"session-456"'),
        },
      );
    });

    it("should save conversation with metadata", async () => {
      const messages = [{ role: "user", content: "Test" }];
      const metadata = { source: "web", timestamp: "2024-01-01" };

      const mockResponse = {
        success: true,
        conversation_id: 789,
        messages_saved: 1,
      };

      vi.mocked(mockClient.request).mockResolvedValue(mockResponse);

      await conversationsApi.saveConversation(messages, undefined, metadata);

      expect(mockClient.request).toHaveBeenCalledWith(
        "/api/bali-zero/conversations/save",
        {
          method: "POST",
          body: expect.stringContaining(
            '"metadata":{"source":"web","timestamp":"2024-01-01"}',
          ),
        },
      );
    });

    it("should save messages with sources", async () => {
      const messages = [
        {
          role: "assistant",
          content: "Answer",
          sources: [{ title: "Doc 1", content: "Content" }],
        },
      ];

      const mockResponse = {
        success: true,
        conversation_id: 100,
        messages_saved: 1,
      };

      vi.mocked(mockClient.request).mockResolvedValue(mockResponse);

      await conversationsApi.saveConversation(messages);

      expect(mockClient.request).toHaveBeenCalledWith(
        "/api/bali-zero/conversations/save",
        {
          method: "POST",
          body: expect.stringContaining('"sources"'),
        },
      );
    });

    it("should save messages with image URLs", async () => {
      const messages = [
        {
          role: "user",
          content: "Check this image",
          imageUrl: "https://example.com/image.jpg",
        },
      ];

      const mockResponse = {
        success: true,
        conversation_id: 200,
        messages_saved: 1,
      };

      vi.mocked(mockClient.request).mockResolvedValue(mockResponse);

      await conversationsApi.saveConversation(messages);

      expect(mockClient.request).toHaveBeenCalledWith(
        "/api/bali-zero/conversations/save",
        {
          method: "POST",
          body: expect.stringContaining('"imageUrl"'),
        },
      );
    });
  });

  describe("clearConversations", () => {
    it("should clear all conversations without session ID", async () => {
      const mockResponse = {
        success: true,
        deleted_count: 5,
      };

      vi.mocked(mockClient.request).mockResolvedValue(mockResponse);

      const result = await conversationsApi.clearConversations();

      expect(mockClient.request).toHaveBeenCalledWith(
        "/api/bali-zero/conversations/clear?",
        {
          method: "DELETE",
        },
      );
      expect(result).toEqual(mockResponse);
    });

    it("should clear conversations with session ID", async () => {
      const mockResponse = {
        success: true,
        deleted_count: 2,
      };

      vi.mocked(mockClient.request).mockResolvedValue(mockResponse);

      await conversationsApi.clearConversations("session-789");

      expect(mockClient.request).toHaveBeenCalledWith(
        "/api/bali-zero/conversations/clear?session_id=session-789",
        {
          method: "DELETE",
        },
      );
    });
  });

  describe("getConversationStats", () => {
    it("should get conversation statistics", async () => {
      const mockResponse = {
        success: true,
        user_email: "user@example.com",
        total_conversations: 10,
        total_messages: 50,
        last_conversation: "2024-01-01T12:00:00Z",
      };

      vi.mocked(mockClient.request).mockResolvedValue(mockResponse);

      const result = await conversationsApi.getConversationStats();

      expect(mockClient.request).toHaveBeenCalledWith(
        "/api/bali-zero/conversations/stats",
      );
      expect(result).toEqual(mockResponse);
    });

    it("should handle null last_conversation", async () => {
      const mockResponse = {
        success: true,
        user_email: "new@example.com",
        total_conversations: 0,
        total_messages: 0,
        last_conversation: null,
      };

      vi.mocked(mockClient.request).mockResolvedValue(mockResponse);

      const result = await conversationsApi.getConversationStats();

      expect(result.last_conversation).toBeNull();
    });
  });

  describe("listConversations", () => {
    it("should list conversations with default pagination", async () => {
      const mockResponse = {
        success: true,
        conversations: [
          {
            id: 1,
            title: "Conversation 1",
            preview: "First message...",
            created_at: "2024-01-01",
          },
        ],
        total: 1,
      };

      vi.mocked(mockClient.request).mockResolvedValue(mockResponse);

      const result = await conversationsApi.listConversations();

      expect(mockClient.request).toHaveBeenCalledWith(
        "/api/bali-zero/conversations/list?limit=20&offset=0",
      );
      expect(result).toEqual(mockResponse);
    });

    it("should list conversations with custom limit", async () => {
      const mockResponse = {
        success: true,
        conversations: [],
        total: 0,
      };

      vi.mocked(mockClient.request).mockResolvedValue(mockResponse);

      await conversationsApi.listConversations(50);

      expect(mockClient.request).toHaveBeenCalledWith(
        "/api/bali-zero/conversations/list?limit=50&offset=0",
      );
    });

    it("should list conversations with custom offset", async () => {
      const mockResponse = {
        success: true,
        conversations: [],
        total: 0,
      };

      vi.mocked(mockClient.request).mockResolvedValue(mockResponse);

      await conversationsApi.listConversations(20, 40);

      expect(mockClient.request).toHaveBeenCalledWith(
        "/api/bali-zero/conversations/list?limit=20&offset=40",
      );
    });
  });

  describe("getConversation", () => {
    it("should get a single conversation by ID", async () => {
      const mockResponse = {
        success: true,
        conversation: {
          id: 123,
          title: "Test Conversation",
          messages: [
            { role: "user", content: "Hello" },
            { role: "assistant", content: "Hi!" },
          ],
          created_at: "2024-01-01",
        },
      };

      vi.mocked(mockClient.request).mockResolvedValue(mockResponse);

      const result = await conversationsApi.getConversation(123);

      expect(mockClient.request).toHaveBeenCalledWith(
        "/api/bali-zero/conversations/123",
      );
      expect(result).toEqual(mockResponse);
    });

    it("should handle different conversation IDs", async () => {
      const mockResponse = {
        success: true,
        conversation: {
          id: 999,
          title: "Another Conversation",
          messages: [],
          created_at: "2024-01-02",
        },
      };

      vi.mocked(mockClient.request).mockResolvedValue(mockResponse);

      await conversationsApi.getConversation(999);

      expect(mockClient.request).toHaveBeenCalledWith(
        "/api/bali-zero/conversations/999",
      );
    });
  });

  describe("deleteConversation", () => {
    it("should delete a conversation by ID", async () => {
      const mockResponse = {
        success: true,
        deleted_id: 456,
      };

      vi.mocked(mockClient.request).mockResolvedValue(mockResponse);

      const result = await conversationsApi.deleteConversation(456);

      expect(mockClient.request).toHaveBeenCalledWith(
        "/api/bali-zero/conversations/456",
        {
          method: "DELETE",
        },
      );
      expect(result).toEqual(mockResponse);
    });

    it("should handle different conversation IDs for deletion", async () => {
      const mockResponse = {
        success: true,
        deleted_id: 789,
      };

      vi.mocked(mockClient.request).mockResolvedValue(mockResponse);

      await conversationsApi.deleteConversation(789);

      expect(mockClient.request).toHaveBeenCalledWith(
        "/api/bali-zero/conversations/789",
        {
          method: "DELETE",
        },
      );
    });
  });

  describe("getUserMemoryContext", () => {
    it("should get user memory context", async () => {
      const mockResponse = {
        profile_facts: ["Fact 1", "Fact 2"],
        summary: "User summary",
        counters: { interactions: 10 },
      };

      vi.mocked(mockClient.request).mockResolvedValue(mockResponse);

      const result = await conversationsApi.getUserMemoryContext();

      expect(mockClient.request).toHaveBeenCalledWith(
        "/api/bali-zero/conversations/memory/context",
      );
      expect(result).toEqual(mockResponse);
    });

    it("should handle empty memory context", async () => {
      const mockResponse = {
        profile_facts: [],
        summary: "",
        counters: {},
      };

      vi.mocked(mockClient.request).mockResolvedValue(mockResponse);

      const result = await conversationsApi.getUserMemoryContext();

      expect(result.profile_facts).toHaveLength(0);
      expect(result.summary).toBe("");
    });
  });

  describe("error handling", () => {
    it("should handle API errors in getConversationHistory", async () => {
      vi.mocked(mockClient.request).mockRejectedValue(new Error("API Error"));

      await expect(conversationsApi.getConversationHistory()).rejects.toThrow(
        "API Error",
      );
    });

    it("should handle API errors in saveConversation", async () => {
      vi.mocked(mockClient.request).mockRejectedValue(new Error("Save failed"));

      await expect(
        conversationsApi.saveConversation([{ role: "user", content: "test" }]),
      ).rejects.toThrow("Save failed");
    });

    it("should handle API errors in deleteConversation", async () => {
      vi.mocked(mockClient.request).mockRejectedValue(
        new Error("Delete failed"),
      );

      await expect(conversationsApi.deleteConversation(123)).rejects.toThrow(
        "Delete failed",
      );
    });
  });
});
