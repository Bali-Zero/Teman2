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
  TaxObligation,
  PortalDocument,
  MessagesResponse,
  PortalMessage,
  SendMessageRequest,
  PortalPreferences,
  PortalProfile,
  UpdateProfileRequest,
  InviteValidationResponse,
  CompleteRegistrationRequest,
  RegistrationResponse,
  PortalApiResponse,
  LKPMDraftSummary,
  LKPMDraft,
  ProcessTimeline,
  DriveFilesResponse,
  BillingResponse,
  NotificationsResponse,
  DashboardSummary,
  PortalMatter,
  PortalMatterDetail,
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

  async getDashboardSummary(): Promise<DashboardSummary> {
    return this.client.request<DashboardSummary>(
      "/api/portal/dashboard/summary",
      { method: "GET" },
    );
  }

  async listMatters(): Promise<{ matters: PortalMatter[] }> {
    return this.client.request<{ matters: PortalMatter[] }>(
      "/api/portal/matters",
      { method: "GET" },
    );
  }

  async getMatterDetail(matterId: number): Promise<PortalMatterDetail> {
    const response = await this.client.request<{ matter: PortalMatterDetail }>(
      `/api/portal/matters/${matterId}`,
      { method: "GET" },
    );
    return response.matter;
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
  // Profile Update
  // ============================================================================

  async updateProfile(data: UpdateProfileRequest): Promise<PortalProfile> {
    const response = await this.client.request<PortalApiResponse<any>>(
      "/api/portal/profile",
      { method: "PATCH", body: JSON.stringify(data) },
    );
    const d = response.data!;
    return {
      id: d.id,
      fullName: d.full_name,
      email: d.email,
      phone: d.phone,
      whatsapp: d.whatsapp,
      nationality: d.nationality,
      passportNumber: d.passport_number,
      passportExpiry: d.passport_expiry,
      dateOfBirth: d.date_of_birth,
      gender: d.gender,
      address: d.address,
      memberSince: d.member_since,
      assignedTo: d.assigned_to
        ? {
            email: d.assigned_to.email,
            name: d.assigned_to.name,
            avatarUrl: d.assigned_to.avatar_url,
          }
        : undefined,
    };
  }

  // ============================================================================
  // Visa & Immigration
  // ============================================================================

  async getVisaStatus(): Promise<VisaInfo> {
    // Backend may return {success, data: {current, history, documents}} or
    // the legacy {summary, current_visa, history} shape. Accept both.
    const response = await this.client.request<any>("/api/portal/visa", {
      method: "GET",
    });

    const raw = response.data ?? response;
    const visa = raw.current ?? raw.current_visa ?? null;

    return {
      current: visa
        ? {
            type: visa.visa_type ?? visa.type ?? "",
            status: visa.status ?? "expired",
            issueDate: visa.issue_date ?? visa.issueDate ?? "",
            expiryDate: visa.expiry_date ?? visa.expiryDate ?? "",
            daysRemaining:
              raw.summary?.days_until_expiry ??
              visa.days_remaining ??
              visa.daysRemaining ??
              0,
            permitNumber:
              visa.visa_number ?? visa.permit_number ?? visa.permitNumber ?? "",
            sponsor: visa.sponsor_name ?? visa.sponsor ?? "",
          }
        : null,
      history: (raw.history ?? []).map((h: Record<string, unknown>) => ({
        id: String(h.id ?? ""),
        type: (h.visa_type as string) ?? (h.type as string) ?? "",
        period: `${h.issue_date ?? h.issueDate ?? ""} — ${h.expiry_date ?? h.expiryDate ?? ""}`,
        status: h.status === "active" ? "completed" : "expired",
      })),
      documents: (raw.documents ?? []).map((d: Record<string, unknown>) => ({
        id: String(d.id ?? ""),
        name: (d.name as string) ?? "",
        type: (d.type as string) ?? "",
        category: (d.category as string) ?? "",
        status: (d.status as string) ?? "",
        uploadDate: (d.uploadDate as string) ?? (d.upload_date as string) ?? "",
        expiryDate: (d.expiryDate as string) ?? (d.expiry_date as string) ?? "",
        size: (d.size as string) ?? "",
        downloadUrl:
          (d.downloadUrl as string) ?? (d.download_url as string) ?? "",
      })),
    };
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
    const response = await this.client.request<
      PortalApiResponse<Record<string, unknown>>
    >("/api/portal/taxes", { method: "GET" });
    const raw = (response.data ?? {}) as Record<string, unknown>;
    const summary = (raw.summary ?? {}) as Record<string, unknown>;
    const obligations = (raw.obligations ?? []) as Record<string, unknown>[];
    // Backend currently emits camelCase keys (totalDue, nextDeadline,
    // daysToDeadline, dueDate, type, period). Older builds used snake_case
    // (total_due, next_deadline…). Accept either so a silent backend schema
    // drift doesn't wipe out the UI again.
    const pick = <T>(
      obj: Record<string, unknown>,
      keys: string[],
    ): T | undefined => {
      for (const k of keys) {
        const v = obj[k];
        if (v !== undefined && v !== null) return v as T;
      }
      return undefined;
    };
    return {
      summary: {
        status:
          pick<TaxOverview["summary"]["status"]>(summary, ["status"]) ?? "ok",
        totalDue: pick<number>(summary, ["totalDue", "total_due"]) ?? 0,
        nextDeadline:
          pick<string>(summary, ["nextDeadline", "next_deadline"]) ?? null,
        daysToDeadline:
          pick<number>(summary, [
            "daysToDeadline",
            "days_until_deadline",
            "days_to_deadline",
          ]) ?? null,
        pendingCount:
          pick<number>(summary, ["pendingCount", "pending_count"]) ?? 0,
        overdueCount:
          pick<number>(summary, ["overdueCount", "overdue_count"]) ?? 0,
      },
      obligations: obligations.map((o) => ({
        id: String(o.id ?? o.uuid ?? ""),
        name: pick<string>(o, ["name"]) ?? "",
        type: pick<string>(o, ["type", "tax_type"]) ?? "",
        period:
          pick<string>(o, ["period"]) ??
          `${o.period_start ?? ""} — ${o.period_end ?? ""}`,
        dueDate: pick<string>(o, ["dueDate", "due_date"]) ?? "",
        status: pick<TaxObligation["status"]>(o, ["status"]) ?? "pending",
        amount: pick<number>(o, ["amount", "amount_due"]),
      })),
    };
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
    // Backend returns {success: true, draft: {...}} (no data envelope),
    // unlike most portal endpoints. Cast accordingly.
    const response = await this.client.request<{
      success: boolean;
      draft: LKPMDraft;
    }>(`/api/v1/lkpm/draft/${clientId}/${quarter}?year=${year}`, {
      method: "GET",
    });
    return response.draft;
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

  // ============================================================================
  // Process Timeline
  // ============================================================================

  async getProcessTimeline(practiceId: number): Promise<ProcessTimeline> {
    const response = await this.client.request<
      PortalApiResponse<ProcessTimeline>
    >(`/api/portal/process/${practiceId}/timeline`, { method: "GET" });
    return response.data!;
  }

  /**
   * Portal-scoped list of required documents across the caller's active
   * practices. The workspace uses /api/crm/clients/client/{id}/required-documents
   * which 403s for plain client JWTs — this route resolves client_id from
   * the JWT (or ?as_client= for superusers).
   */
  async getMyRequiredDocuments(): Promise<unknown[]> {
    const response = await this.client.request<PortalApiResponse<unknown[]>>(
      "/api/portal/process/required-documents",
      { method: "GET" },
    );
    return response.data ?? [];
  }

  // ============================================================================
  // Drive Files
  // ============================================================================

  async getDriveFiles(): Promise<DriveFilesResponse> {
    const response = await this.client.request<
      PortalApiResponse<DriveFilesResponse>
    >("/api/portal/drive/files", { method: "GET" });
    return response.data!;
  }

  async getDriveSubfolderFiles(folderId: string): Promise<DriveFilesResponse> {
    const response = await this.client.request<
      PortalApiResponse<DriveFilesResponse>
    >(`/api/portal/drive/files/${folderId}/list`, { method: "GET" });
    return response.data!;
  }

  // ============================================================================
  // Billing
  // ============================================================================

  async getBilling(): Promise<BillingResponse> {
    const response = await this.client.request<
      PortalApiResponse<BillingResponse>
    >("/api/portal/billing", { method: "GET" });
    return response.data!;
  }

  async getInvoicePdfUrl(
    invoiceId: number,
  ): Promise<{ download_url: string }> {
    const response = await this.client.request<
      PortalApiResponse<{ download_url: string }>
    >(`/api/portal/billing/${invoiceId}/pdf-url`, { method: "GET" });
    return response.data!;
  }

  // ============================================================================
  // Notifications
  // ============================================================================

  async getNotifications(limit = 50): Promise<NotificationsResponse> {
    const response = await this.client.request<
      PortalApiResponse<NotificationsResponse>
    >(`/api/portal/notifications?limit=${limit}`, { method: "GET" });
    return response.data!;
  }

  async markNotificationRead(notificationId: number): Promise<void> {
    await this.client.request<PortalApiResponse<void>>(
      `/api/portal/notifications/${notificationId}/read`,
      { method: "POST" },
    );
  }

  async markAllNotificationsRead(): Promise<void> {
    await this.client.request<PortalApiResponse<void>>(
      "/api/portal/notifications/read-all",
      { method: "POST" },
    );
  }
}
