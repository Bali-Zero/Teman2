import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { PortalApi } from './portal.api';
import type { ApiClientBase } from '../client';
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
} from './portal.types';
import type { TimelineResponse } from '../../types/timeline.types';

// Mock ApiClientBase
const createMockClient = (): ApiClientBase => {
  const mockRequest = vi.fn();
  return {
    request: mockRequest,
  } as unknown as ApiClientBase;
};

describe('PortalApi', () => {
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

  describe('getDashboard', () => {
    it('should fetch dashboard data successfully', async () => {
      const mockDashboard: PortalDashboard = {
        visa: { status: 'active', type: 'KITAS', expiryDate: '2025-12-31' },
        company: { status: 'active', primaryCompanyName: 'Test Co', totalCompanies: 1 },
        taxes: { status: 'compliant', nextDeadline: null, daysToDeadline: null },
        documents: [],
        messages: [],
        actions: [],
      };

      mockRequest.mockResolvedValue({ data: mockDashboard });

      const result = await portalApi.getDashboard();

      expect(mockRequest).toHaveBeenCalledWith('/api/portal/dashboard', { method: 'GET' });
      expect(result).toEqual(mockDashboard);
    });

    it('should handle API errors gracefully', async () => {
      mockRequest.mockRejectedValue(new Error('API Error'));

      await expect(portalApi.getDashboard()).rejects.toThrow('API Error');
    });
  });

  describe('getTimeline', () => {
    it('should fetch timeline with default limit', async () => {
      const mockTimeline: TimelineResponse = {
        entries: [],
        total: 0,
      };

      mockRequest.mockResolvedValue({ data: mockTimeline });

      const result = await portalApi.getTimeline();

      expect(mockRequest).toHaveBeenCalledWith('/api/portal/timeline?limit=50', { method: 'GET' });
      expect(result).toEqual(mockTimeline);
    });

    it('should fetch timeline with custom limit', async () => {
      const mockTimeline: TimelineResponse = {
        entries: [],
        total: 0,
      };

      mockRequest.mockResolvedValue({ data: mockTimeline });

      await portalApi.getTimeline(20);

      expect(mockRequest).toHaveBeenCalledWith('/api/portal/timeline?limit=20', { method: 'GET' });
    });
  });

  // ============================================================================
  // Profile Tests
  // ============================================================================

  describe('getProfile', () => {
    it('should fetch profile data successfully', async () => {
      const mockProfile: PortalProfile = {
        id: 1,
        email: 'test@example.com',
        fullName: 'Test User',
        avatar: null,
        phone: null,
      };

      mockRequest.mockResolvedValue({ data: mockProfile });

      const result = await portalApi.getProfile();

      expect(mockRequest).toHaveBeenCalledWith('/api/portal/profile', { method: 'GET' });
      expect(result).toEqual(mockProfile);
    });
  });

  // ============================================================================
  // Visa Tests
  // ============================================================================

  describe('getVisaStatus', () => {
    it('should fetch visa status successfully', async () => {
      const mockVisa: VisaInfo = {
        status: 'active',
        type: 'KITAS',
        expiryDate: '2025-12-31',
        daysUntilExpiry: 365,
      };

      mockRequest.mockResolvedValue({ data: mockVisa });

      const result = await portalApi.getVisaStatus();

      expect(mockRequest).toHaveBeenCalledWith('/api/portal/visa', { method: 'GET' });
      expect(result).toEqual(mockVisa);
    });
  });

  // ============================================================================
  // Companies Tests
  // ============================================================================

  describe('getCompanies', () => {
    it('should fetch companies list successfully', async () => {
      const mockCompanies: PortalCompany[] = [
        {
          id: 1,
          name: 'Test Company',
          registrationNumber: '12345',
          isPrimary: true,
          status: 'active',
        },
      ];

      mockRequest.mockResolvedValue({ data: mockCompanies });

      const result = await portalApi.getCompanies();

      expect(mockRequest).toHaveBeenCalledWith('/api/portal/companies', { method: 'GET' });
      expect(result).toEqual(mockCompanies);
    });
  });

  describe('getCompanyDetail', () => {
    it('should fetch company detail successfully', async () => {
      const mockCompany: PortalCompany = {
        id: 1,
        name: 'Test Company',
        registrationNumber: '12345',
        isPrimary: true,
        status: 'active',
      };

      mockRequest.mockResolvedValue({ data: mockCompany });

      const result = await portalApi.getCompanyDetail(1);

      expect(mockRequest).toHaveBeenCalledWith('/api/portal/company/1', { method: 'GET' });
      expect(result).toEqual(mockCompany);
    });
  });

  describe('setPrimaryCompany', () => {
    it('should set primary company successfully', async () => {
      mockRequest.mockResolvedValue({ data: undefined });

      await portalApi.setPrimaryCompany(1);

      expect(mockRequest).toHaveBeenCalledWith('/api/portal/company/1/select', { method: 'POST' });
    });
  });

  // ============================================================================
  // Taxes Tests
  // ============================================================================

  describe('getTaxOverview', () => {
    it('should fetch tax overview successfully', async () => {
      const mockTaxes: TaxOverview = {
        status: 'compliant',
        nextDeadline: null,
        daysToDeadline: null,
        recentFilings: [],
      };

      mockRequest.mockResolvedValue({ data: mockTaxes });

      const result = await portalApi.getTaxOverview();

      expect(mockRequest).toHaveBeenCalledWith('/api/portal/taxes', { method: 'GET' });
      expect(result).toEqual(mockTaxes);
    });
  });

  // ============================================================================
  // Documents Tests
  // ============================================================================

  describe('getDocuments', () => {
    it('should fetch all documents when no type specified', async () => {
      const mockDocuments: PortalDocument[] = [];

      mockRequest.mockResolvedValue({ data: mockDocuments });

      await portalApi.getDocuments();

      expect(mockRequest).toHaveBeenCalledWith('/api/portal/documents', { method: 'GET' });
    });

    it('should fetch documents filtered by type', async () => {
      const mockDocuments: PortalDocument[] = [];

      mockRequest.mockResolvedValue({ data: mockDocuments });

      await portalApi.getDocuments('passport');

      expect(mockRequest).toHaveBeenCalledWith('/api/portal/documents?document_type=passport', {
        method: 'GET',
      });
    });

    it('should URL encode document type correctly', async () => {
      const mockDocuments: PortalDocument[] = [];

      mockRequest.mockResolvedValue({ data: mockDocuments });

      await portalApi.getDocuments('passport copy');

      expect(mockRequest).toHaveBeenCalledWith(
        '/api/portal/documents?document_type=passport%20copy',
        { method: 'GET' }
      );
    });
  });

  describe('uploadDocument', () => {
    it('should upload document successfully', async () => {
      const file = new File(['test'], 'test.pdf', { type: 'application/pdf' });
      const mockDocument: PortalDocument = {
        id: 1,
        name: 'test.pdf',
        type: 'passport',
        uploadedAt: new Date().toISOString(),
        url: '/documents/1',
      };

      mockRequest.mockResolvedValue({ data: mockDocument });

      const result = await portalApi.uploadDocument(file, 'passport');

      expect(mockRequest).toHaveBeenCalledWith('/api/portal/documents/upload', {
        method: 'POST',
        body: expect.any(FormData),
      });

      // Verify FormData contents
      const formDataCall = mockRequest.mock.calls.find(
        (call) => call[0] === '/api/portal/documents/upload'
      );
      expect(formDataCall).toBeDefined();
      expect(result).toEqual(mockDocument);
    });

    it('should upload document with practice ID', async () => {
      const file = new File(['test'], 'test.pdf', { type: 'application/pdf' });
      const mockDocument: PortalDocument = {
        id: 1,
        name: 'test.pdf',
        type: 'passport',
        uploadedAt: new Date().toISOString(),
        url: '/documents/1',
      };

      mockRequest.mockResolvedValue({ data: mockDocument });

      await portalApi.uploadDocument(file, 'passport', 123);

      expect(mockRequest).toHaveBeenCalledWith('/api/portal/documents/upload', {
        method: 'POST',
        body: expect.any(FormData),
      });
    });
  });

  // ============================================================================
  // Messages Tests
  // ============================================================================

  describe('getMessages', () => {
    it('should fetch messages with default pagination', async () => {
      const mockMessages: MessagesResponse = {
        messages: [],
        total: 0,
        unreadCount: 0,
      };

      mockRequest.mockResolvedValue({ data: mockMessages });

      const result = await portalApi.getMessages();

      expect(mockRequest).toHaveBeenCalledWith('/api/portal/messages?limit=50&offset=0', {
        method: 'GET',
      });
      expect(result).toEqual(mockMessages);
    });

    it('should fetch messages with custom pagination', async () => {
      const mockMessages: MessagesResponse = {
        messages: [],
        total: 0,
        unreadCount: 0,
      };

      mockRequest.mockResolvedValue({ data: mockMessages });

      await portalApi.getMessages(20, 10);

      expect(mockRequest).toHaveBeenCalledWith('/api/portal/messages?limit=20&offset=10', {
        method: 'GET',
      });
    });
  });

  describe('sendMessage', () => {
    it('should send message successfully', async () => {
      const request: SendMessageRequest = {
        subject: 'Test',
        body: 'Test message',
        practiceId: 1,
      };

      const mockMessage: PortalMessage = {
        id: 1,
        subject: 'Test',
        body: 'Test message',
        from: 'client',
        to: 'team',
        sentAt: new Date().toISOString(),
        readAt: null,
      };

      mockRequest.mockResolvedValue({ data: mockMessage });

      const result = await portalApi.sendMessage(request);

      expect(mockRequest).toHaveBeenCalledWith('/api/portal/messages', {
        method: 'POST',
        body: JSON.stringify(request),
      });
      expect(result).toEqual(mockMessage);
    });
  });

  describe('markMessageRead', () => {
    it('should mark message as read successfully', async () => {
      mockRequest.mockResolvedValue({ data: undefined });

      await portalApi.markMessageRead(1);

      expect(mockRequest).toHaveBeenCalledWith('/api/portal/messages/1/read', {
        method: 'POST',
      });
    });
  });

  // ============================================================================
  // Settings Tests
  // ============================================================================

  describe('getPreferences', () => {
    it('should fetch preferences successfully', async () => {
      const mockPreferences: PortalPreferences = {
        emailNotifications: true,
        smsNotifications: false,
        language: 'en',
      };

      mockRequest.mockResolvedValue({ data: mockPreferences });

      const result = await portalApi.getPreferences();

      expect(mockRequest).toHaveBeenCalledWith('/api/portal/settings', { method: 'GET' });
      expect(result).toEqual(mockPreferences);
    });
  });

  describe('updatePreferences', () => {
    it('should update preferences successfully', async () => {
      const updates: Partial<PortalPreferences> = {
        emailNotifications: false,
      };

      const mockPreferences: PortalPreferences = {
        emailNotifications: false,
        smsNotifications: false,
        language: 'en',
      };

      mockRequest.mockResolvedValue({ data: mockPreferences });

      const result = await portalApi.updatePreferences(updates);

      expect(mockRequest).toHaveBeenCalledWith('/api/portal/settings', {
        method: 'PATCH',
        body: JSON.stringify(updates),
      });
      expect(result).toEqual(mockPreferences);
    });
  });

  // ============================================================================
  // Invitation Flow Tests (Public endpoints)
  // ============================================================================

  describe('validateInviteToken', () => {
    it('should validate invite token successfully', async () => {
      const mockResponse: InviteValidationResponse = {
        valid: true,
        clientName: 'Test Client',
        email: 'test@example.com',
        message: 'Valid token',
      };

      mockRequest.mockResolvedValue(mockResponse);

      const result = await portalApi.validateInviteToken('test-token');

      expect(mockRequest).toHaveBeenCalledWith('/api/portal/invite/validate/test-token', {
        method: 'GET',
      });
      expect(result).toEqual(mockResponse);
    });

    it('should handle invalid token', async () => {
      const mockResponse: InviteValidationResponse = {
        valid: false,
        message: 'Invalid or expired token',
      };

      mockRequest.mockResolvedValue(mockResponse);

      const result = await portalApi.validateInviteToken('invalid-token');

      expect(result.valid).toBe(false);
    });
  });

  describe('completeRegistration', () => {
    it('should complete registration successfully', async () => {
      const request: CompleteRegistrationRequest = {
        token: 'test-token',
        pin: '1234',
      };

      const mockResponse = {
        success: true,
        message: 'Registration completed',
      };

      mockRequest.mockResolvedValue(mockResponse);

      const result = await portalApi.completeRegistration(request);

      expect(mockRequest).toHaveBeenCalledWith('/api/portal/invite/complete', {
        method: 'POST',
        body: JSON.stringify(request),
      });
      expect(result).toEqual(mockResponse);
    });
  });
});
