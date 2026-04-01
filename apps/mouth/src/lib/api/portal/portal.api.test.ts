import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { PortalApi } from "./portal.api";
import type { ApiClientBase } from "../client";
import type {
  PortalDashboard,
  VisaInfo,
  PortalCompany,
  TaxOverview,
  PortalDocument,
  MessagesResponse,
  PortalMessage,
  SendMessageRequest,
  PortalPreferences,
  PortalProfile,
  InviteValidationResponse,
  CompleteRegistrationRequest,
} from "./portal.types";

// ============================================================================
// Mock Data Factory - aligned with portal.types.ts
// ============================================================================

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
    unread: 3,
  },
  actions: [],
  ...overrides,
});

const createMockProfile = (
  overrides?: Partial<PortalProfile>,
): PortalProfile => ({
  id: 1,
  fullName: "Test User",
  email: "test@example.com",
  phone: "+62812345678",
  whatsapp: "+62812345678",
  nationality: "US",
  passportNumber: "ABC123456",
  address: "123 Test Street",
  memberSince: "2024-01-01",
  ...overrides,
});

const createMockVisaInfo = (overrides?: Partial<VisaInfo>): VisaInfo => ({
  current: {
    type: "KITAS",
    status: "active",
    issueDate: "2024-01-01",
    expiryDate: "2025-12-31",
    daysRemaining: 365,
    permitNumber: "PERMIT-001",
    sponsor: "PT Test Company",
  },
  history: [],
  documents: [],
  ...overrides,
});

const createMockCompany = (
  overrides?: Partial<PortalCompany>,
): PortalCompany => ({
  id: 1,
  name: "Test Company",
  type: "PT",
  status: "active",
  isPrimary: true,
  address: "123 Business Street",
  directors: ["John Doe"],
  licenses: [],
  compliance: [],
  ...overrides,
});

const createMockTaxOverview = (
  overrides?: Partial<TaxOverview>,
): TaxOverview => ({
  summary: {
    status: "compliant",
    totalDue: 0,
    nextDeadline: null,
    daysToDeadline: null,
  },
  obligations: [],
  history: [],
  ...overrides,
});

const createMockDocument = (
  overrides?: Partial<PortalDocument>,
): PortalDocument => ({
  id: "doc-001",
  name: "test.pdf",
  type: "passport",
  category: "personal",
  status: "verified",
  uploadDate: new Date().toISOString(),
  size: "1.2 MB",
  downloadUrl: "/documents/doc-001",
  ...overrides,
});

const createMockMessage = (
  overrides?: Partial<PortalMessage>,
): PortalMessage => ({
  id: "msg-001",
  content: "Test message",
  direction: "client_to_team",
  sentBy: "Test User",
  subject: "Test Subject",
  createdAt: new Date().toISOString(),
  ...overrides,
});

const createMockPreferences = (
  overrides?: Partial<PortalPreferences>,
): PortalPreferences => ({
  emailNotifications: true,
  whatsappNotifications: false,
  language: "en",
  timezone: "Asia/Jakarta",
  ...overrides,
});

// Mock ApiClientBase
const createMockClient = (): ApiClientBase => {
  const mockRequest = vi.fn();
  return {
    request: mockRequest,
  } as unknown as ApiClientBase;
};

// ============================================================================
// Tests
// ============================================================================

describe("PortalApi", () => {
  let portalApi: PortalApi;
  let mockClient: ApiClientBase;
  let mockRequest: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    mockRequest = vi.fn();
    mockClient = createMockClient();
    (mockClient.request as ReturnType<typeof vi.fn>) = mockRequest;
    portalApi = new PortalApi(mockClient);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  // ============================================================================
  // Dashboard Tests
  // ============================================================================

  describe("getDashboard", () => {
    it("should fetch dashboard data successfully", async () => {
      const mockDashboard = createMockDashboard();
      mockRequest.mockResolvedValue({ data: mockDashboard });

      const result = await portalApi.getDashboard();

      expect(mockRequest).toHaveBeenCalledWith("/api/portal/dashboard", {
        method: "GET",
      });
      expect(result).toEqual(mockDashboard);
    });

    it("should handle API errors gracefully", async () => {
      mockRequest.mockRejectedValue(new Error("API Error"));

      await expect(portalApi.getDashboard()).rejects.toThrow("API Error");
    });
  });

  // ============================================================================
  // Profile Tests
  // ============================================================================

  describe("getProfile", () => {
    it("should fetch profile data successfully", async () => {
      // Backend returns snake_case
      const mockBackendProfile = {
        id: 1,
        full_name: "Test User",
        email: "test@example.com",
        phone: "+62812345678",
        whatsapp: "+62812345678",
        nationality: "US",
        passport_number: "ABC123456",
        address: "123 Test Street",
        member_since: "2024-01-01",
      };
      mockRequest.mockResolvedValue({ data: mockBackendProfile });

      const result = await portalApi.getProfile();

      expect(mockRequest).toHaveBeenCalledWith("/api/portal/profile", {
        method: "GET",
      });
      // Result should be camelCase
      expect(result.fullName).toBe("Test User");
      expect(result.passportNumber).toBe("ABC123456");
      expect(result.memberSince).toBe("2024-01-01");
    });
  });

  // ============================================================================
  // Visa Tests
  // ============================================================================

  describe("getVisaStatus", () => {
    it("should fetch visa status successfully", async () => {
      // Backend returns snake_case; getVisaStatus maps to camelCase VisaInfo
      const backendResponse = {
        summary: { days_until_expiry: 365, status: "active" },
        current_visa: {
          id: 1,
          visa_type: "KITAS",
          status: "active",
          issue_date: "2024-01-01",
          expiry_date: "2025-12-31",
          visa_number: "PERMIT-001",
          sponsor_name: "PT Test Company",
        },
        history: [],
      };
      mockRequest.mockResolvedValue(backendResponse);

      const result = await portalApi.getVisaStatus();

      expect(mockRequest).toHaveBeenCalledWith("/api/portal/visa", {
        method: "GET",
      });
      expect(result).toEqual(createMockVisaInfo());
    });
  });

  // ============================================================================
  // Companies Tests
  // ============================================================================

  describe("getCompanies", () => {
    it("should fetch companies list successfully", async () => {
      const mockCompanies: PortalCompany[] = [createMockCompany()];
      mockRequest.mockResolvedValue({ data: mockCompanies });

      const result = await portalApi.getCompanies();

      expect(mockRequest).toHaveBeenCalledWith("/api/portal/companies", {
        method: "GET",
      });
      expect(result).toEqual(mockCompanies);
    });
  });

  describe("getCompanyDetail", () => {
    it("should fetch company detail successfully", async () => {
      const mockCompany = createMockCompany();
      mockRequest.mockResolvedValue({ data: mockCompany });

      const result = await portalApi.getCompanyDetail(1);

      expect(mockRequest).toHaveBeenCalledWith("/api/portal/company/1", {
        method: "GET",
      });
      expect(result).toEqual(mockCompany);
    });
  });

  describe("setPrimaryCompany", () => {
    it("should set primary company successfully", async () => {
      mockRequest.mockResolvedValue({ data: undefined });

      await portalApi.setPrimaryCompany(1);

      expect(mockRequest).toHaveBeenCalledWith("/api/portal/company/1/select", {
        method: "POST",
      });
    });
  });

  // ============================================================================
  // Taxes Tests
  // ============================================================================

  describe("getTaxOverview", () => {
    it("should fetch tax overview successfully", async () => {
      const mockTaxes = createMockTaxOverview();
      mockRequest.mockResolvedValue({ data: mockTaxes });

      const result = await portalApi.getTaxOverview();

      expect(mockRequest).toHaveBeenCalledWith("/api/portal/taxes", {
        method: "GET",
      });
      expect(result).toEqual(mockTaxes);
    });
  });

  // ============================================================================
  // Documents Tests
  // ============================================================================

  describe("getDocuments", () => {
    it("should fetch all documents when no type specified", async () => {
      const mockDocuments: PortalDocument[] = [];
      mockRequest.mockResolvedValue({ data: mockDocuments });

      await portalApi.getDocuments();

      expect(mockRequest).toHaveBeenCalledWith("/api/portal/documents", {
        method: "GET",
      });
    });

    it("should fetch documents filtered by type", async () => {
      const mockDocuments: PortalDocument[] = [];
      mockRequest.mockResolvedValue({ data: mockDocuments });

      await portalApi.getDocuments("passport");

      expect(mockRequest).toHaveBeenCalledWith(
        "/api/portal/documents?document_type=passport",
        {
          method: "GET",
        },
      );
    });

    it("should URL encode document type correctly", async () => {
      const mockDocuments: PortalDocument[] = [];
      mockRequest.mockResolvedValue({ data: mockDocuments });

      await portalApi.getDocuments("passport copy");

      expect(mockRequest).toHaveBeenCalledWith(
        "/api/portal/documents?document_type=passport%20copy",
        { method: "GET" },
      );
    });
  });

  describe("uploadDocument", () => {
    it("should upload document successfully", async () => {
      const file = new File(["test"], "test.pdf", { type: "application/pdf" });
      const mockDocument = createMockDocument();
      mockRequest.mockResolvedValue({ data: mockDocument });

      const result = await portalApi.uploadDocument(file, "passport");

      expect(mockRequest).toHaveBeenCalledWith("/api/portal/documents/upload", {
        method: "POST",
        body: expect.any(FormData),
      });
      expect(result).toEqual(mockDocument);
    });

    it("should upload document with practice ID", async () => {
      const file = new File(["test"], "test.pdf", { type: "application/pdf" });
      const mockDocument = createMockDocument();
      mockRequest.mockResolvedValue({ data: mockDocument });

      await portalApi.uploadDocument(file, "passport", 123);

      expect(mockRequest).toHaveBeenCalledWith("/api/portal/documents/upload", {
        method: "POST",
        body: expect.any(FormData),
      });
    });
  });

  // ============================================================================
  // Messages Tests
  // ============================================================================

  describe("getMessages", () => {
    it("should fetch messages with default pagination", async () => {
      const mockMessages: MessagesResponse = {
        messages: [],
        total: 0,
        unreadCount: 0,
      };
      mockRequest.mockResolvedValue({ data: mockMessages });

      const result = await portalApi.getMessages();

      expect(mockRequest).toHaveBeenCalledWith(
        "/api/portal/messages?limit=50&offset=0",
        {
          method: "GET",
        },
      );
      expect(result).toEqual(mockMessages);
    });

    it("should fetch messages with custom pagination", async () => {
      const mockMessages: MessagesResponse = {
        messages: [],
        total: 0,
        unreadCount: 0,
      };
      mockRequest.mockResolvedValue({ data: mockMessages });

      await portalApi.getMessages(20, 10);

      expect(mockRequest).toHaveBeenCalledWith(
        "/api/portal/messages?limit=20&offset=10",
        {
          method: "GET",
        },
      );
    });
  });

  describe("sendMessage", () => {
    it("should send message successfully", async () => {
      const request: SendMessageRequest = {
        content: "Test message",
        subject: "Test Subject",
        practiceId: 1,
      };

      const mockMessage = createMockMessage();
      mockRequest.mockResolvedValue({ data: mockMessage });

      const result = await portalApi.sendMessage(request);

      expect(mockRequest).toHaveBeenCalledWith("/api/portal/messages", {
        method: "POST",
        body: JSON.stringify(request),
      });
      expect(result).toEqual(mockMessage);
    });
  });

  describe("markMessageRead", () => {
    it("should mark message as read successfully", async () => {
      mockRequest.mockResolvedValue({ data: undefined });

      await portalApi.markMessageRead(1);

      expect(mockRequest).toHaveBeenCalledWith("/api/portal/messages/1/read", {
        method: "POST",
      });
    });
  });

  // ============================================================================
  // Settings Tests
  // ============================================================================

  describe("getPreferences", () => {
    it("should fetch preferences successfully", async () => {
      const mockPreferences = createMockPreferences();
      mockRequest.mockResolvedValue({ data: mockPreferences });

      const result = await portalApi.getPreferences();

      expect(mockRequest).toHaveBeenCalledWith("/api/portal/settings", {
        method: "GET",
      });
      expect(result).toEqual(mockPreferences);
    });
  });

  describe("updatePreferences", () => {
    it("should update preferences successfully", async () => {
      const updates: Partial<PortalPreferences> = {
        emailNotifications: false,
      };

      const mockPreferences = createMockPreferences({
        emailNotifications: false,
      });
      mockRequest.mockResolvedValue({ data: mockPreferences });

      const result = await portalApi.updatePreferences(updates);

      expect(mockRequest).toHaveBeenCalledWith("/api/portal/settings", {
        method: "PATCH",
        body: JSON.stringify(updates),
      });
      expect(result).toEqual(mockPreferences);
    });
  });

  // ============================================================================
  // Invitation Flow Tests (Public endpoints)
  // ============================================================================

  describe("validateInviteToken", () => {
    it("should validate invite token successfully", async () => {
      const mockResponse: InviteValidationResponse = {
        valid: true,
        clientName: "Test Client",
        email: "test@example.com",
        message: "Valid token",
      };
      mockRequest.mockResolvedValue(mockResponse);

      const result = await portalApi.validateInviteToken("test-token");

      expect(mockRequest).toHaveBeenCalledWith(
        "/api/portal/invite/validate/test-token",
        {
          method: "GET",
        },
      );
      expect(result).toEqual(mockResponse);
    });

    it("should handle invalid token", async () => {
      const mockResponse: InviteValidationResponse = {
        valid: false,
        message: "Invalid or expired token",
      };
      mockRequest.mockResolvedValue(mockResponse);

      const result = await portalApi.validateInviteToken("invalid-token");

      expect(result.valid).toBe(false);
    });
  });

  describe("completeRegistration", () => {
    it("should complete registration successfully", async () => {
      const request: CompleteRegistrationRequest = {
        token: "test-token",
        pin: "1234",
      };

      const mockResponse = {
        success: true,
        message: "Registration completed",
      };
      mockRequest.mockResolvedValue(mockResponse);

      const result = await portalApi.completeRegistration(request);

      expect(mockRequest).toHaveBeenCalledWith("/api/portal/invite/complete", {
        method: "POST",
        body: JSON.stringify(request),
      });
      expect(result).toEqual(mockResponse);
    });
  });
});
