/**
 * Portal API Client
 * Handles all client portal API calls
 */

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
  RegistrationResponse,
  PortalApiResponse,
} from './portal.types';

export class PortalApi {
  constructor(private client: ApiClientBase) {}

  // ============================================================================
  // Dashboard
  // ============================================================================

  async getDashboard(): Promise<PortalDashboard> {
    const response = await this.client.request<PortalApiResponse<PortalDashboard>>(
      '/api/portal/dashboard',
      { method: 'GET' }
    );
    return response.data!;
  }

  // ============================================================================
  // Profile
  // ============================================================================

  async getProfile(): Promise<PortalProfile> {
    const response = await this.client.request<PortalApiResponse<PortalProfile>>(
      '/api/portal/profile',
      { method: 'GET' }
    );
    return response.data!;
  }

  // ============================================================================
  // Visa & Immigration
  // ============================================================================

  async getVisaStatus(): Promise<VisaInfo> {
    const response = await this.client.request<PortalApiResponse<VisaInfo>>(
      '/api/portal/visa',
      { method: 'GET' }
    );
    return response.data!;
  }

  // ============================================================================
  // Companies
  // ============================================================================

  async getCompanies(): Promise<PortalCompany[]> {
    const response = await this.client.request<PortalApiResponse<PortalCompany[]>>(
      '/api/portal/companies',
      { method: 'GET' }
    );
    return response.data!;
  }

  async getCompanyDetail(companyId: number): Promise<PortalCompany> {
    const response = await this.client.request<PortalApiResponse<PortalCompany>>(
      `/api/portal/company/${companyId}`,
      { method: 'GET' }
    );
    return response.data!;
  }

  async setPrimaryCompany(companyId: number): Promise<void> {
    await this.client.request<PortalApiResponse<void>>(
      `/api/portal/company/${companyId}/select`,
      { method: 'POST' }
    );
  }

  // ============================================================================
  // Taxes
  // ============================================================================

  async getTaxOverview(): Promise<TaxOverview> {
    const response = await this.client.request<PortalApiResponse<TaxOverview>>(
      '/api/portal/taxes',
      { method: 'GET' }
    );
    return response.data!;
  }

  // ============================================================================
  // Documents
  // ============================================================================

  async getDocuments(documentType?: string): Promise<PortalDocument[]> {
    const params = documentType ? `?document_type=${encodeURIComponent(documentType)}` : '';
    const response = await this.client.request<PortalApiResponse<PortalDocument[]>>(
      `/api/portal/documents${params}`,
      { method: 'GET' }
    );
    return response.data!;
  }

  async uploadDocument(
    file: File,
    documentType: string,
    practiceId?: number
  ): Promise<PortalDocument> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('document_type', documentType);
    if (practiceId) {
      formData.append('practice_id', practiceId.toString());
    }

    const response = await this.client.request<PortalApiResponse<PortalDocument>>(
      '/api/portal/documents/upload',
      {
        method: 'POST',
        body: formData,
        // Don't set Content-Type - browser will set it with boundary for multipart
      }
    );
    return response.data!;
  }

  // ============================================================================
  // Messages
  // ============================================================================

  async getMessages(limit = 50, offset = 0): Promise<MessagesResponse> {
    const response = await this.client.request<PortalApiResponse<MessagesResponse>>(
      `/api/portal/messages?limit=${limit}&offset=${offset}`,
      { method: 'GET' }
    );
    return response.data!;
  }

  async sendMessage(request: SendMessageRequest): Promise<PortalMessage> {
    const response = await this.client.request<PortalApiResponse<PortalMessage>>(
      '/api/portal/messages',
      {
        method: 'POST',
        body: JSON.stringify(request),
      }
    );
    return response.data!;
  }

  async markMessageRead(messageId: number): Promise<void> {
    await this.client.request<PortalApiResponse<void>>(
      `/api/portal/messages/${messageId}/read`,
      { method: 'POST' }
    );
  }

  // ============================================================================
  // Settings
  // ============================================================================

  async getPreferences(): Promise<PortalPreferences> {
    const response = await this.client.request<PortalApiResponse<PortalPreferences>>(
      '/api/portal/settings',
      { method: 'GET' }
    );
    return response.data!;
  }

  async updatePreferences(preferences: Partial<PortalPreferences>): Promise<PortalPreferences> {
    const response = await this.client.request<PortalApiResponse<PortalPreferences>>(
      '/api/portal/settings',
      {
        method: 'PATCH',
        body: JSON.stringify(preferences),
      }
    );
    return response.data!;
  }

  // ============================================================================
  // Invitation Flow (Public endpoints)
  // ============================================================================

  async validateInviteToken(token: string): Promise<InviteValidationResponse> {
    // Public endpoint - no auth required (backend allows unauthenticated access)
    const response = await this.client.request<InviteValidationResponse>(
      `/api/portal/invite/validate/${token}`,
      { method: 'GET' }
    );
    return response;
  }

  async completeRegistration(request: CompleteRegistrationRequest): Promise<RegistrationResponse> {
    // Public endpoint - no auth required (backend allows unauthenticated access)
    const response = await this.client.request<RegistrationResponse>(
      '/api/portal/invite/complete',
      {
        method: 'POST',
        body: JSON.stringify(request),
      }
    );
    return response;
  }
}
