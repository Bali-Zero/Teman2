/**
 * Portal API Client
 * Handles all client portal API calls
 */

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
  RegistrationResponse,
  PortalApiResponse,
  LKPMDraftSummary,
  LKPMDraft,
} from "./portal.types";
import type { TimelineResponse } from "../types/timeline.types";

export class PortalApi {
  constructor(private client: ApiClientBase) {}

  // ============================================================================
  // Dashboard
  // ============================================================================

  async getDashboard(): Promise<PortalDashboard> {
    const response = await this.client.request<
      PortalApiResponse<PortalDashboard>
    >("/api/portal/dashboard", { method: "GET" });
    return response.data!;
  }

  async getTimeline(limit: number = 50): Promise<TimelineResponse> {
    const response = await this.client.request<
      PortalApiResponse<TimelineResponse>
    >(`/api/portal/timeline?limit=${limit}`, { method: "GET" });
    return response.data!;
  }

  // ============================================================================
  // Profile
  // ============================================================================

  async getProfile(): Promise<PortalProfile> {
    const response = await this.client.request<PortalApiResponse<any>>(
      "/api/portal/profile",
      { method: "GET" },
    );

    // Map snake_case backend response to camelCase frontend types
    const data = response.data!;
    return {
      id: data.id,
      fullName: data.full_name,
      email: data.email,
      phone: data.phone,
      whatsapp: data.whatsapp,
      nationality: data.nationality,
      passportNumber: data.passport_number,
      passportExpiry: data.passport_expiry,
      dateOfBirth: data.date_of_birth,
      gender: data.gender,
      address: data.address,
      memberSince: data.member_since,
      assignedTo: data.assigned_to
        ? {
            email: data.assigned_to.email,
            name: data.assigned_to.name,
            avatarUrl: data.assigned_to.avatar_url,
          }
        : undefined,
    };
  }

  // ============================================================================
  // Visa & Immigration
  // ============================================================================

  async getVisaStatus(): Promise<VisaInfo> {
    const response = await this.client.request<PortalApiResponse<VisaInfo>>(
      "/api/portal/visa",
      {
        method: "GET",
      },
    );
    return response.data!;
  }

  // ============================================================================
  // Companies
  // ============================================================================

  async getCompanies(): Promise<PortalCompany[]> {
    const response = await this.client.request<
      PortalApiResponse<PortalCompany[]>
    >("/api/portal/companies", { method: "GET" });
    return response.data!;
  }

  async getCompanyDetail(companyId: number): Promise<PortalCompany> {
    const response = await this.client.request<
      PortalApiResponse<PortalCompany>
    >(`/api/portal/company/${companyId}`, { method: "GET" });
    return response.data!;
  }

  async setPrimaryCompany(companyId: number): Promise<void> {
    await this.client.request<PortalApiResponse<void>>(
      `/api/portal/company/${companyId}/select`,
      {
        method: "POST",
      },
    );
  }

  // ============================================================================
  // Taxes
  // ============================================================================

  async getTaxOverview(): Promise<TaxOverview> {
    const response = await this.client.request<PortalApiResponse<TaxOverview>>(
      "/api/portal/taxes",
      { method: "GET" },
    );
    return response.data!;
  }

  // ============================================================================
  // Documents
  // ============================================================================

  async getDocuments(documentType?: string): Promise<PortalDocument[]> {
    const params = documentType
      ? `?document_type=${encodeURIComponent(documentType)}`
      : "";
    const response = await this.client.request<
      PortalApiResponse<PortalDocument[]>
    >(`/api/portal/documents${params}`, { method: "GET" });
    return response.data!;
  }

  async uploadDocument(
    file: File,
    documentType: string,
    practiceId?: number,
  ): Promise<PortalDocument> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("document_type", documentType);
    if (practiceId) {
      formData.append("practice_id", practiceId.toString());
    }

    const response = await this.client.request<
      PortalApiResponse<PortalDocument>
    >("/api/portal/documents/upload", {
      method: "POST",
      body: formData,
      // Don't set Content-Type - browser will set it with boundary for multipart
    });
    return response.data!;
  }

  // ============================================================================
  // Messages
  // ============================================================================

  async getMessages(limit = 50, offset = 0): Promise<MessagesResponse> {
    const response = await this.client.request<
      PortalApiResponse<MessagesResponse>
    >(`/api/portal/messages?limit=${limit}&offset=${offset}`, {
      method: "GET",
    });
    return response.data!;
  }

  async sendMessage(request: SendMessageRequest): Promise<PortalMessage> {
    const response = await this.client.request<
      PortalApiResponse<PortalMessage>
    >("/api/portal/messages", {
      method: "POST",
      body: JSON.stringify(request),
    });
    return response.data!;
  }

  async markMessageRead(messageId: number): Promise<void> {
    await this.client.request<PortalApiResponse<void>>(
      `/api/portal/messages/${messageId}/read`,
      {
        method: "POST",
      },
    );
  }

  // ============================================================================
  // Settings
  // ============================================================================

  async getPreferences(): Promise<PortalPreferences> {
    const response = await this.client.request<
      PortalApiResponse<PortalPreferences>
    >("/api/portal/settings", { method: "GET" });
    return response.data!;
  }

  async updatePreferences(
    preferences: Partial<PortalPreferences>,
  ): Promise<PortalPreferences> {
    const response = await this.client.request<
      PortalApiResponse<PortalPreferences>
    >("/api/portal/settings", {
      method: "PATCH",
      body: JSON.stringify(preferences),
    });
    return response.data!;
  }

  // ============================================================================
  // LKPM (Investment Reports)
  // ============================================================================

  async getLKPMHistory(clientId: number): Promise<LKPMDraftSummary[]> {
    const response = await this.client.request<
      PortalApiResponse<{ items: LKPMDraftSummary[] }>
    >(`/api/v1/lkpm/history/${clientId}`, { method: "GET" });
    return response.data?.items ?? [];
  }

  async getLKPMDraft(
    clientId: number,
    quarter: string,
    year: number,
  ): Promise<LKPMDraft> {
    const response = await this.client.request<
      PortalApiResponse<{ draft: LKPMDraft }>
    >(`/api/v1/lkpm/draft/${clientId}/${quarter}?year=${year}`, {
      method: "GET",
    });
    return response.data!.draft;
  }

  async submitLKPMData(data: {
    client_id: number;
    quarter: string;
    year: number;
    investment: Record<string, number>;
    employment: { tki: number; tka: number };
    revenue_quarterly?: number;
    revenue_annual?: number;
    obstacles?: string;
    plans?: string;
  }): Promise<{
    draft_id: number;
    quarter: string;
    year: number;
    realized_total: number;
  }> {
    const response = await this.client.request<
      PortalApiResponse<{
        draft_id: number;
        quarter: string;
        year: number;
        realized_total: number;
      }>
    >("/api/v1/lkpm/submit-data", {
      method: "POST",
      body: JSON.stringify(data),
    });
    return response.data!;
  }

  async approveLKPMDraft(draftId: number): Promise<{ success: boolean }> {
    const response = await this.client.request<PortalApiResponse<void>>(
      `/api/v1/lkpm/approve/${draftId}`,
      { method: "POST" },
    );
    return { success: response.success };
  }

  // ============================================================================
  // Invitation Flow (Public endpoints)
  // ============================================================================

  async validateInviteToken(token: string): Promise<InviteValidationResponse> {
    // Public endpoint - no auth required (backend allows unauthenticated access)
    const response = await this.client.request<InviteValidationResponse>(
      `/api/portal/invite/validate/${token}`,
      { method: "GET" },
    );
    return response;
  }

  async completeRegistration(
    request: CompleteRegistrationRequest,
  ): Promise<RegistrationResponse> {
    // Public endpoint - no auth required (backend allows unauthenticated access)
    const response = await this.client.request<RegistrationResponse>(
      "/api/portal/invite/complete",
      {
        method: "POST",
        body: JSON.stringify(request),
      },
    );
    return response;
  }
}
