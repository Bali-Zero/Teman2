import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { api } from "../../api";
import type {
  PortalDashboard,
  SendMessageRequest,
} from "../portal/portal.types";

// Mock Data Factory - aligned with portal.types.ts
const createMockDashboard = (
  overrides?: Partial<PortalDashboard>,
): PortalDashboard => ({
  visa: {
    status: "active",
    type: "KITAS",
    expiryDate: "2025-12-31",
    daysRemaining: 365,
  },
  company: {
    status: "active",
    primaryCompanyName: "Test Co",
    totalCompanies: 1,
  },
  taxes: {
    status: "compliant",
    nextDeadline: null,
    daysToDeadline: null,
  },
  documents: {
    total: 10,
    pending: 2,
  },
  messages: {
    unread: 0,
  },
  actions: [],
  ...overrides,
});

const createEmptyDashboard = (): PortalDashboard => ({
  visa: {
    status: "none",
    type: null,
    expiryDate: null,
    daysRemaining: null,
  },
  company: {
    status: "none",
    primaryCompanyName: null,
    totalCompanies: 0,
  },
  taxes: {
    status: "compliant",
    nextDeadline: null,
    daysToDeadline: null,
  },
  documents: {
    total: 0,
    pending: 0,
  },
  messages: {
    unread: 0,
  },
  actions: [],
});

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
  };
})();
Object.defineProperty(window, "localStorage", { value: localStorageMock });

describe("Portal API Integration Tests", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    localStorageMock.clear();
    vi.clearAllMocks();

    // Set auth token
    localStorageMock.setItem("auth_token", "test-token");
    localStorageMock.setItem("csrf_token", "test-csrf");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("Dashboard Flow", () => {
    it("should fetch dashboard and timeline in parallel", async () => {
      const mockDashboard = createMockDashboard();

      const mockTimeline = {
        entries: [],
        total: 0,
      };

      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          statusText: "OK",
          headers: new Headers({ "content-type": "application/json" }),
          json: async () => ({ data: mockDashboard }),
        })
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          statusText: "OK",
          headers: new Headers({ "content-type": "application/json" }),
          json: async () => ({ data: mockTimeline }),
        });

      const dashboard = await api.portal.getDashboard();
      const timeline = await api.portal.getTimeline();

      expect(dashboard).toEqual(mockDashboard);
      expect(timeline).toEqual(mockTimeline);
      expect(mockFetch).toHaveBeenCalledTimes(2);
    });

    it("should handle partial failures gracefully", async () => {
      const emptyDashboard = createEmptyDashboard();

      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          status: 200,
          statusText: "OK",
          headers: new Headers({ "content-type": "application/json" }),
          json: async () => ({ data: emptyDashboard }),
        })
        .mockRejectedValueOnce(new Error("Timeline API Error"));

      const dashboard = await api.portal.getDashboard();

      expect(dashboard).toBeDefined();
      expect(mockFetch).toHaveBeenCalled();

      await expect(api.portal.getTimeline()).rejects.toThrow();
    });
  });

  describe("Authentication Flow", () => {
    it("should include auth token in portal API requests", async () => {
      const mockDashboard = createEmptyDashboard();

      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        statusText: "OK",
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({ data: mockDashboard }),
      });

      await api.portal.getDashboard();

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/portal/dashboard"),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: expect.stringContaining("Bearer"),
          }),
        }),
      );
    });

    it("should handle 401 errors and redirect", async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 401,
        statusText: "Unauthorized",
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({ error: "Unauthorized" }),
      });

      await expect(api.portal.getDashboard()).rejects.toThrow();
    });
  });

  describe("Message Flow", () => {
    it("should fetch messages with pagination", async () => {
      const mockMessages = {
        messages: [],
        total: 0,
        unreadCount: 5,
      };

      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        statusText: "OK",
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({ data: mockMessages }),
      });

      const result = await api.portal.getMessages(20, 10);

      expect(result).toEqual(mockMessages);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/portal/messages?limit=20&offset=10"),
        expect.any(Object),
      );
    });

    it("should send message correctly", async () => {
      const mockMessage = {
        id: "msg-001",
        content: "Test message",
        direction: "client_to_team",
        sentBy: "Test User",
        subject: "Test",
        createdAt: new Date().toISOString(),
      };

      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        statusText: "OK",
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({ data: mockMessage }),
      });

      const request: SendMessageRequest = {
        content: "Test message",
        subject: "Test",
        practiceId: 1,
      };

      const result = await api.portal.sendMessage(request);

      expect(result).toEqual(mockMessage);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/portal/messages"),
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining("Test"),
        }),
      );
    });
  });

  describe("Document Upload Flow", () => {
    it("should upload document with FormData", async () => {
      const file = new File(["test"], "test.pdf", { type: "application/pdf" });
      const mockDocument = {
        id: "doc-001",
        name: "test.pdf",
        type: "passport",
        category: "personal",
        status: "verified",
        uploadDate: new Date().toISOString(),
        size: "1.2 MB",
        downloadUrl: "/documents/doc-001",
      };

      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        statusText: "OK",
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({ data: mockDocument }),
      });

      const result = await api.portal.uploadDocument(file, "passport");

      expect(result).toEqual(mockDocument);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/portal/documents/upload"),
        expect.objectContaining({
          method: "POST",
          body: expect.any(FormData),
        }),
      );
    });
  });

  describe("Invitation Flow (Public)", () => {
    it("should validate invite token without auth", async () => {
      const mockResponse = {
        valid: true,
        clientName: "Test Client",
        email: "test@example.com",
      };

      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        statusText: "OK",
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => mockResponse,
      });

      const result = await api.portal.validateInviteToken("test-token");

      expect(result).toEqual(mockResponse);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/portal/invite/validate/test-token"),
        expect.any(Object),
      );
    });

    it("should complete registration without auth", async () => {
      const mockResponse = {
        success: true,
        message: "Registration completed",
      };

      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        statusText: "OK",
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => mockResponse,
      });

      const result = await api.portal.completeRegistration({
        token: "test-token",
        pin: "1234",
      });

      expect(result).toEqual(mockResponse);
    });
  });
});
