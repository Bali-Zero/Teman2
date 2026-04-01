import type { IApiClient } from "../types/api-client.types";
import type {
  Practice,
  Interaction,
  PracticeStats,
  InteractionStats,
  Client,
  CreateClientParams,
  CreatePracticeParams,
  RenewalAlert,
  ClientSummary,
  ClientProfile,
  FamilyMember,
  FamilyMemberCreate,
  ClientDocument,
  DocumentCreate,
  DocumentCategory,
  ExpiryAlert,
  ExpiryAlertsSummary,
  Company,
  ClientCompanyLink,
  CompanyDocument,
  TaxRecord,
  PortalMessageThread,
} from "./crm.types";
import type {
  RequiredDocument,
  RequiredDocumentCreate,
  RequiredDocumentUpdate,
  ClientDocumentUpload,
  ClientRequiredDocument,
} from "@/lib/types/required-documents";

/**
 * Revenue growth statistics response
 */
interface RevenueGrowthResponse {
  current_month: {
    total_revenue: number;
    paid_revenue: number;
    outstanding_revenue: number;
  };
  previous_month: {
    total_revenue: number;
    paid_revenue: number;
    outstanding_revenue: number;
  };
  growth_percentage: number;
  monthly_breakdown: Array<{
    month: string;
    total_revenue: number;
    paid_revenue: number;
    outstanding_revenue: number;
    practice_count: number;
  }>;
}

/**
 * Mark interaction read response
 */
interface MarkReadResponse {
  success: boolean;
  interaction_id: number;
  read_receipt: boolean;
  read_at: string;
  read_by: string;
}

/**
 * Batch mark read response
 */
interface BatchMarkReadResponse {
  success: boolean;
  updated_count: number;
  read_by: string;
}

export class CrmApi {
  constructor(private client: IApiClient) {}

  /**
   * Generic request passthrough for admin/notification endpoints
   */
  async request<T = unknown>(
    url: string,
    options?: Parameters<IApiClient["request"]>[1],
  ): Promise<T> {
    return this.client.request<T>(url, options);
  }

  /**
   * Get all practices with optional filtering
   */
  async getPractices(
    params: {
      status?: string;
      assigned_to?: string;
      limit?: number;
      offset?: number;
      month?: string;
      include_history?: boolean;
    } = {},
  ): Promise<Practice[]> {
    const queryParams = new URLSearchParams();
    if (params.status) queryParams.append("status", params.status);
    if (params.assigned_to)
      queryParams.append("assigned_to", params.assigned_to);
    if (params.limit) queryParams.append("limit", params.limit.toString());
    if (params.offset) queryParams.append("offset", params.offset.toString());
    if (params.month) queryParams.append("month", params.month);
    if (params.include_history) queryParams.append("include_history", "true");

    const queryString = queryParams.toString();
    const url = `/api/crm/practices${queryString ? `?${queryString}` : ""}`;

    return this.client.request<Practice[]>(url);
  }

  /**
   * Get a single practice by ID
   *
   * Backend endpoint: GET /api/crm/practices/{id}
   * Returns practice with full client and type info joined.
   */
  async getPractice(id: number): Promise<Practice> {
    return this.client.request<Practice>(`/api/crm/practices/${id}`);
  }

  /**
   * Get interactions (e.g. WhatsApp messages)
   */
  async getInteractions(
    params: {
      interaction_type?: string;
      limit?: number;
      offset?: number;
    } = {},
  ): Promise<Interaction[]> {
    const queryParams = new URLSearchParams();
    if (params.interaction_type)
      queryParams.append("interaction_type", params.interaction_type);
    if (params.limit) queryParams.append("limit", params.limit.toString());
    if (params.offset) queryParams.append("offset", params.offset.toString());

    const queryString = queryParams.toString();
    const url = `/api/crm/interactions${queryString ? `?${queryString}` : ""}`;

    return this.client.request<Interaction[]>(url);
  }

  /**
   * Get practice statistics
   */
  async getPracticeStats(): Promise<PracticeStats> {
    return this.client.request<PracticeStats>(
      "/api/crm/practices/stats/overview",
    );
  }

  /**
   * Get client team assignees (emails with client count)
   */
  async getClientAssignees(): Promise<
    Array<{ assigned_to: string; count: number }>
  > {
    const stats = await this.client.request<{
      by_team_member: Array<{ assigned_to: string; count: number }>;
    }>("/api/crm/clients/stats/overview");
    return stats.by_team_member || [];
  }

  /**
   * Get interaction statistics
   */
  async getInteractionStats(): Promise<InteractionStats> {
    return this.client.request<InteractionStats>(
      "/api/crm/interactions/stats/overview",
    );
  }

  /**
   * Get upcoming renewals/critical deadlines
   */
  async getUpcomingRenewals(days: number = 90): Promise<RenewalAlert[]> {
    return this.client.request<RenewalAlert[]>(
      `/api/crm/practices/renewals/upcoming?days=${days}`,
    );
  }

  /**
   * Get revenue growth statistics (monthly comparison)
   */
  async getRevenueGrowth(): Promise<RevenueGrowthResponse> {
    return this.client.request<RevenueGrowthResponse>(
      "/api/crm/practices/stats/revenue-growth",
    );
  }

  /**
   * Mark an interaction as read
   */
  async markInteractionRead(
    interactionId: number,
    readBy: string,
  ): Promise<MarkReadResponse> {
    return this.client.request<MarkReadResponse>(
      `/api/crm/interactions/${interactionId}/mark-read?read_by=${encodeURIComponent(readBy)}`,
      { method: "PATCH" },
    );
  }

  /**
   * Mark multiple interactions as read (batch)
   */
  async markInteractionsReadBatch(
    interactionIds: number[],
    readBy: string,
  ): Promise<BatchMarkReadResponse> {
    const queryParams = new URLSearchParams();
    interactionIds.forEach((id) =>
      queryParams.append("interaction_ids", id.toString()),
    );
    queryParams.append("read_by", readBy);

    return this.client.request<BatchMarkReadResponse>(
      `/api/crm/interactions/mark-read-batch?${queryParams.toString()}`,
      { method: "PATCH" },
    );
  }

  /**
   * Delete an interaction
   */
  async deleteInteraction(
    interactionId: number,
    deletedBy: string,
  ): Promise<{ success: boolean }> {
    return this.client.request<{ success: boolean }>(
      `/api/crm/interactions/${interactionId}?deleted_by=${encodeURIComponent(deletedBy)}`,
      { method: "DELETE" },
    );
  }

  /**
   * Get all clients with optional search and filtering
   */
  async getClients(
    params: {
      search?: string;
      status?: string;
      assigned_to?: string;
      nationality?: string;
      passport_expiring_days?: number;
      limit?: number;
      offset?: number;
    } = {},
  ): Promise<Client[]> {
    const queryParams = new URLSearchParams();
    if (params.search) queryParams.append("search", params.search);
    if (params.status) queryParams.append("status", params.status);
    if (params.assigned_to)
      queryParams.append("assigned_to", params.assigned_to);
    if (params.nationality)
      queryParams.append("nationality", params.nationality);
    if (params.passport_expiring_days !== undefined)
      queryParams.append(
        "passport_expiring_days",
        params.passport_expiring_days.toString(),
      );
    if (params.limit) queryParams.append("limit", params.limit.toString());
    if (params.offset) queryParams.append("offset", params.offset.toString());

    const queryString = queryParams.toString();
    const url = `/api/crm/clients${queryString ? `?${queryString}` : ""}`;

    return this.client.request<Client[]>(url, undefined, 10000);
  }

  /**
   * Create a new client
   */
  async createClient(
    data: CreateClientParams,
    createdBy: string,
  ): Promise<Client> {
    const queryParams = new URLSearchParams();
    queryParams.append("created_by", createdBy);

    return this.client.request<Client>(
      `/api/crm/clients?${queryParams.toString()}`,
      {
        method: "POST",
        body: JSON.stringify(data),
      },
      60000, // 60 second timeout for creation
    );
  }

  /**
   * Get practice types catalog grouped by category (for process creation form)
   */
  async getPracticeTypesCatalog(): Promise<{
    categories: Array<{
      code: string;
      label: string;
      services: Array<{
        code: string;
        name: string;
        description: string | null;
        base_price: number | null;
        typical_duration_days: number | null;
      }>;
    }>;
    total_services: number;
  }> {
    return this.client.request(`/api/crm/practices/types/catalog`);
  }

  /**
   * Create a new practice/case
   */
  async createPractice(data: CreatePracticeParams): Promise<Practice> {
    // Note: trailing slash required to avoid 307 redirect which converts POST to GET
    return this.client.request<Practice>(
      `/api/crm/practices/`,
      {
        method: "POST",
        body: JSON.stringify(data),
      },
      60000, // 60 second timeout for creation
    );
  }

  /**
   * Update a practice/case (status, priority, notes, etc.)
   */
  async updatePractice(
    practiceId: number,
    updates: Partial<{
      status: string;
      priority: string;
      quoted_price: number;
      actual_price: number;
      payment_status: string;
      assigned_to: string;
      notes: string;
      start_date: string;
    }>,
  ): Promise<Practice> {
    // Note: trailing slash required to avoid 307 redirect which converts PATCH to GET
    return this.client.request<Practice>(
      `/api/crm/practices/${practiceId}/`,
      {
        method: "PATCH",
        body: JSON.stringify(updates),
      },
      60000, // 60 second timeout
    );
  }

  /**
   * Get a single client by ID
   */
  async getClient(clientId: number): Promise<Client> {
    return this.client.request<Client>(
      `/api/crm/clients/${clientId}`,
      undefined,
      10000,
    );
  }

  /**
   * Get client by email address (returns null if not found)
   */
  async getClientByEmail(email: string): Promise<Client | null> {
    try {
      return await this.client.request<Client>(
        `/api/crm/clients/by-email/${encodeURIComponent(email)}`,
      );
    } catch (error) {
      // 404 means client not found - return null instead of throwing
      if (error instanceof Error && error.message.includes("404")) {
        return null;
      }
      throw error;
    }
  }

  /**
   * Get full client summary with cases, interactions, renewals
   */
  async getClientSummary(clientId: number): Promise<ClientSummary> {
    return this.client.request<ClientSummary>(
      `/api/crm/clients/${clientId}/summary`,
      undefined,
      10000,
    );
  }

  /**
   * Get client interaction timeline
   */
  async getClientTimeline(
    clientId: number,
    limit: number = 50,
  ): Promise<Interaction[]> {
    // Backend returns {client_id, total_interactions, timeline: Interaction[]}
    const response = await this.client.request<{ timeline: Interaction[] }>(
      `/api/crm/interactions/client/${clientId}/timeline?limit=${limit}`,
      undefined,
      10000,
    );
    return Array.isArray(response.timeline) ? response.timeline : [];
  }

  /**
   * Get practices for a specific client
   */
  async getClientPractices(clientId: number): Promise<Practice[]> {
    return this.client.request<Practice[]>(
      `/api/crm/practices/?client_id=${clientId}`,
    );
  }

  // ============================================
  // CLIENT PROFILE (Enhanced)
  // ============================================

  /**
   * Get enhanced client profile with family, documents, alerts
   */
  async getClientProfile(clientId: number): Promise<ClientProfile> {
    return this.client.request<ClientProfile>(
      `/api/crm/clients/${clientId}/profile`,
    );
  }

  /**
   * Update client profile (avatar, Google Drive folder, etc.)
   */
  async updateClientProfile(
    clientId: number,
    updates: Partial<{
      avatar_url: string;
      google_drive_folder_id: string;
      date_of_birth: string;
      passport_expiry: string;
      company_name: string;
    }>,
  ): Promise<{ success: boolean }> {
    return this.client.request<{ success: boolean }>(
      `/api/crm/clients/${clientId}/profile`,
      {
        method: "PATCH",
        body: JSON.stringify(updates),
      },
    );
  }

  // ============================================
  // FAMILY MEMBERS
  // ============================================

  /**
   * Get family members for a client
   */
  async getFamilyMembers(clientId: number): Promise<FamilyMember[]> {
    return this.client.request<FamilyMember[]>(
      `/api/crm/clients/${clientId}/family`,
    );
  }

  /**
   * Add a family member
   */
  async createFamilyMember(
    clientId: number,
    data: FamilyMemberCreate,
  ): Promise<{ id: number; success: boolean }> {
    return this.client.request<{ id: number; success: boolean }>(
      `/api/crm/clients/${clientId}/family`,
      {
        method: "POST",
        body: JSON.stringify(data),
      },
    );
  }

  /**
   * Update a family member
   */
  async updateFamilyMember(
    clientId: number,
    memberId: number,
    updates: Partial<FamilyMemberCreate>,
  ): Promise<{ success: boolean }> {
    return this.client.request<{ success: boolean }>(
      `/api/crm/clients/${clientId}/family/${memberId}`,
      {
        method: "PATCH",
        body: JSON.stringify(updates),
      },
    );
  }

  /**
   * Delete a family member
   */
  async deleteFamilyMember(
    clientId: number,
    memberId: number,
  ): Promise<{ success: boolean }> {
    return this.client.request<{ success: boolean }>(
      `/api/crm/clients/${clientId}/family/${memberId}`,
      { method: "DELETE" },
    );
  }

  // ============================================
  // DOCUMENTS
  // ============================================

  /**
   * Get documents for a client
   */
  async getClientDocuments(
    clientId: number,
    category?: string,
    includeArchived?: boolean,
  ): Promise<ClientDocument[]> {
    const params = new URLSearchParams();
    if (category) params.append("category", category);
    if (includeArchived) params.append("include_archived", "true");
    const query = params.toString();
    return this.client.request<ClientDocument[]>(
      `/api/crm/clients/${clientId}/documents${query ? `?${query}` : ""}`,
    );
  }

  /**
   * Add a document
   */
  async createDocument(
    clientId: number,
    data: DocumentCreate,
  ): Promise<{ id: number; success: boolean }> {
    return this.client.request<{ id: number; success: boolean }>(
      `/api/crm/clients/${clientId}/documents`,
      {
        method: "POST",
        body: JSON.stringify(data),
      },
    );
  }

  /**
   * Upload a document via base64 with optional subfolder hint for visa rotation
   */
  async uploadDocumentBase64(
    clientId: number,
    data: {
      file: string;
      file_name: string;
      document_type: string;
      mime_type?: string;
      notes?: string;
      subfolder_hint?: string;
      document_category?: string;
      expiry_date?: string;
      family_member_id?: number;
    },
  ): Promise<{
    success: boolean;
    document_id?: number;
    file_url?: string;
    ocr_triggered?: boolean;
  }> {
    return this.client.request<{
      success: boolean;
      document_id?: number;
      file_url?: string;
      ocr_triggered?: boolean;
    }>(`/api/crm/clients/${clientId}/documents/upload`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  /**
   * Update a document
   */
  async updateDocument(
    clientId: number,
    docId: number,
    updates: Partial<DocumentCreate & { status: string; is_archived: boolean }>,
  ): Promise<{ success: boolean }> {
    return this.client.request<{ success: boolean }>(
      `/api/crm/clients/${clientId}/documents/${docId}`,
      {
        method: "PATCH",
        body: JSON.stringify(updates),
      },
    );
  }

  /**
   * Archive or delete a document
   */
  async deleteDocument(
    clientId: number,
    docId: number,
    permanent?: boolean,
  ): Promise<{ success: boolean; action: string }> {
    return this.client.request<{ success: boolean; action: string }>(
      `/api/crm/clients/${clientId}/documents/${docId}${permanent ? "?permanent=true" : ""}`,
      { method: "DELETE" },
    );
  }

  /**
   * Get document categories for dropdowns
   */
  async getDocumentCategories(): Promise<DocumentCategory[]> {
    return this.client.request<DocumentCategory[]>(
      "/api/crm/document-categories",
    );
  }

  // ============================================
  // EXPIRY ALERTS
  // ============================================

  /**
   * Get all expiry alerts (for team dashboard)
   */
  async getExpiryAlerts(params?: {
    alertColor?: "expired" | "red" | "yellow";
    assignedTo?: string;
    limit?: number;
  }): Promise<ExpiryAlert[]> {
    const queryParams = new URLSearchParams();
    if (params?.alertColor)
      queryParams.append("alert_color", params.alertColor);
    if (params?.assignedTo)
      queryParams.append("assigned_to", params.assignedTo);
    if (params?.limit) queryParams.append("limit", params.limit.toString());
    const query = queryParams.toString();
    return this.client.request<ExpiryAlert[]>(
      `/api/crm/expiry-alerts${query ? `?${query}` : ""}`,
    );
  }

  /**
   * Get expiry alerts summary for dashboard
   */
  async getExpiryAlertsSummary(): Promise<ExpiryAlertsSummary> {
    return this.client.request<ExpiryAlertsSummary>(
      "/api/crm/expiry-alerts/summary",
    );
  }

  // ============================================
  // CLIENT MANAGEMENT
  // ============================================

  /**
   * Delete a client (soft delete - marks as inactive)
   * Only admins or authorized team members should call this
   */
  async deleteClient(
    clientId: number,
    deletedBy: string,
  ): Promise<{ success: boolean; message: string }> {
    return this.client.request<{ success: boolean; message: string }>(
      `/api/crm/clients/${clientId}?deleted_by=${encodeURIComponent(deletedBy)}`,
      { method: "DELETE" },
    );
  }

  /**
   * Update a client's basic information
   */
  async updateClient(
    clientId: number,
    updates: Partial<{
      full_name: string;
      email: string;
      phone: string;
      whatsapp: string;
      nationality: string;
      passport_number: string;
      status: string;
      client_type: string;
      assigned_to: string;
      address: string;
      notes: string;
      tags: string[];
      google_drive_folder_id: string;
      avatar_url: string;
      passport_expiry: string;
      date_of_birth: string;
      company_name: string;
    }>,
    updatedBy: string,
  ): Promise<Client> {
    return this.client.request<Client>(
      `/api/crm/clients/${clientId}?updated_by=${encodeURIComponent(updatedBy)}`,
      {
        method: "PATCH",
        body: JSON.stringify(updates),
      },
    );
  }

  /**
   * Delete a practice/case (soft delete - marks as cancelled)
   * Only admins or the client's lead can delete practices
   */
  async deletePractice(
    practiceId: number,
    deletedBy: string,
  ): Promise<{ success: boolean; message: string }> {
    return this.client.request<{ success: boolean; message: string }>(
      `/api/crm/practices/${practiceId}?deleted_by=${encodeURIComponent(deletedBy)}`,
      { method: "DELETE" },
    );
  }

  /**
   * Create an interaction/note for a client
   */
  async createInteraction(data: {
    client_id: number;
    interaction_type:
      | "note"
      | "chat"
      | "email"
      | "whatsapp"
      | "call"
      | "meeting";
    summary: string;
    subject?: string;
    team_member: string;
    direction?: "inbound" | "outbound";
    practice_id?: number;
  }): Promise<Interaction> {
    return this.client.request<Interaction>("/api/crm/interactions/", {
      method: "POST",
      body: JSON.stringify({
        ...data,
        direction: data.direction || "outbound",
        channel: "in_person",
      }),
    });
  }

  /**
   * Google Drive Folder Management
   */

  /**
   * Create standardized Google Drive folder structure for a client
   */
  async createDriveFolder(clientId: number): Promise<{
    success: boolean;
    root_folder_id: string;
    root_folder_url: string;
    root_folder_name: string;
    folders: Record<string, { id: string; url: string }>;
    created_count: number;
  }> {
    return this.client.request(`/api/clients/${clientId}/create-drive-folder`, {
      method: "POST",
    });
  }

  /**
   * Get Google Drive folder information for a client
   */
  async getDriveFolder(clientId: number): Promise<{
    client_id: number;
    folder_id: string | null;
    folder_url: string | null;
    exists: boolean;
    message?: string;
  }> {
    return this.client.request(`/api/clients/${clientId}/drive-folder`);
  }

  /**
   * Unlink Google Drive folder from client (does NOT delete the folder)
   */
  async unlinkDriveFolder(clientId: number): Promise<{
    success: boolean;
    message: string;
    note: string;
  }> {
    return this.client.request(`/api/clients/${clientId}/drive-folder`, {
      method: "DELETE",
    });
  }

  /**
   * Get complete folder structure with file counts
   */
  async getDriveFolderStructure(clientId: number): Promise<{
    root_folder_id: string;
    folders: Array<{
      name: string;
      id: string;
      file_count: number;
      total_size_bytes: number;
      last_modified: string | null;
    }>;
    total_files: number;
    total_size_bytes: number;
  }> {
    return this.client.request(
      `/api/clients/${clientId}/drive-folder/structure`,
    );
  }

  /**
   * List files in a subfolder
   */
  async listFolderFiles(
    clientId: number,
    folderName: string,
    options?: {
      limit?: number;
      offset?: number;
      search?: string;
    },
  ): Promise<{
    folder_name: string;
    folder_id: string;
    files: Array<{
      id: string;
      name: string;
      mime_type: string;
      size_bytes: number | null;
      created_time: string;
      modified_time: string;
      thumbnail_url: string | null;
      download_url: string;
      is_folder: boolean;
    }>;
    total: number;
    limit: number;
    offset: number;
    has_more: boolean;
  }> {
    const params = new URLSearchParams();
    if (options?.limit) params.append("limit", options.limit.toString());
    if (options?.offset) params.append("offset", options.offset.toString());
    if (options?.search) params.append("search", options.search);

    const query = params.toString();
    return this.client.request(
      `/api/clients/${clientId}/drive-folder/${folderName}/files${query ? `?${query}` : ""}`,
    );
  }

  /**
   * Upload file to a subfolder
   */
  async uploadFileToFolder(
    clientId: number,
    folderName: string,
    file: File,
  ): Promise<{
    success: boolean;
    folder_name: string;
    folder_id: string;
    file_id: string;
    file_name: string;
    size_bytes: number;
    download_url: string;
  }> {
    const formData = new FormData();
    formData.append("file", file);

    // Client now handles FormData correctly (no Content-Type header)
    return this.client.request(
      `/api/clients/${clientId}/drive-folder/${folderName}/upload`,
      {
        method: "POST",
        body: formData,
        // Headers will be set by client (CSRF token, etc.)
        // Content-Type will NOT be set for FormData
      },
    );
  }

  /**
   * Get folder statistics
   */
  async getDriveFolderStats(clientId: number): Promise<{
    total_files: number;
    total_size_bytes: number;
    total_size_mb: number;
    last_synced: string;
    by_category: Record<
      string,
      {
        files: number;
        size_bytes: number;
        size_mb: number;
      }
    >;
  }> {
    return this.client.request(`/api/clients/${clientId}/drive-folder/stats`);
  }

  // ============================================
  // COMPANIES (Company-Centric CRM)
  // ============================================

  /**
   * Search for a company by name (ILIKE match, returns first match with associates)
   */
  async searchCompanyByName(name: string): Promise<
    | (Company & {
        associates: Array<{
          link_id: number;
          client_id: number;
          client_name: string;
          role: string;
          is_primary: boolean;
          ownership_percentage?: number;
          shares_count?: number;
          share_nominal_value?: number;
          start_date?: string;
          status: string;
        }>;
      })
    | null
  > {
    return this.client.request(
      `/api/crm/companies/by-name?name=${encodeURIComponent(name)}`,
    );
  }

  /**
   * Get all companies for a client
   */
  async getClientCompanies(clientId: number): Promise<ClientCompanyLink[]> {
    return this.client.request<ClientCompanyLink[]>(
      `/api/crm/companies/by-client/${clientId}`,
    );
  }

  /**
   * Create a new company
   */
  async createCompany(data: {
    company_name: string;
    company_type?: string;
    kbli_code?: string;
    nib?: string;
    npwp_company?: string;
    registered_address?: string;
    city?: string;
    province?: string;
    company_email?: string;
    company_phone?: string;
  }): Promise<{
    id: number;
    uuid: string;
    company_name: string;
    status: string;
    message: string;
  }> {
    return this.client.request<{
      id: number;
      uuid: string;
      company_name: string;
      status: string;
      message: string;
    }>("/api/crm/companies", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  /**
   * Link a client to a company
   */
  async linkClientToCompany(
    clientId: number,
    companyId: number,
    data: {
      role?: string;
      is_primary?: boolean;
      ownership_percentage?: number;
      shares_count?: number;
      start_date?: string;
    },
  ): Promise<{ link_id: number; message: string }> {
    return this.client.request<{ link_id: number; message: string }>(
      `/api/crm/companies/${companyId}/clients/${clientId}/link`,
      {
        method: "POST",
        body: JSON.stringify(data),
      },
    );
  }

  /**
   * Unlink a client from a company
   */
  async unlinkClientFromCompany(
    clientId: number,
    companyId: number,
  ): Promise<{ message: string }> {
    return this.client.request<{ message: string }>(
      `/api/crm/companies/${companyId}/clients/${clientId}/link`,
      { method: "DELETE" },
    );
  }

  /**
   * Get company details
   */
  async getCompany(companyId: number): Promise<
    Company & {
      associates: ClientCompanyLink[];
      documents: CompanyDocument[];
      tax_record?: TaxRecord;
    }
  > {
    return this.client.request<
      Company & {
        associates: ClientCompanyLink[];
        documents: CompanyDocument[];
        tax_record?: TaxRecord;
      }
    >(`/api/crm/companies/${companyId}`);
  }

  /**
   * Get company documents
   */
  async getCompanyDocuments(
    companyId: number,
    docType?: string,
  ): Promise<CompanyDocument[]> {
    const params = new URLSearchParams();
    if (docType) params.append("doc_type", docType);
    const query = params.toString();
    return this.client.request<CompanyDocument[]>(
      `/api/crm/companies/${companyId}/documents${query ? `?${query}` : ""}`,
    );
  }

  /**
   * Update company details
   */
  async updateCompany(
    companyId: number,
    data: Partial<{
      company_name: string;
      company_type: string;
      kbli_code: string;
      nib: string;
      npwp_company: string;
      akta_pendirian_no: string;
      akta_pendirian_date: string;
      akta_perubahan_no: string;
      akta_perubahan_date: string;
      sk_menhumkam_no: string;
      sk_menhumkam_date: string;
      registered_address: string;
      office_address: string;
      city: string;
      province: string;
      postal_code: string;
      company_phone: string;
      company_email: string;
      status: string;
    }>,
  ): Promise<{ id: number; company_name: string; message: string }> {
    return this.client.request<{
      id: number;
      company_name: string;
      message: string;
    }>(`/api/crm/companies/${companyId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }

  /**
   * Get company tax record
   */
  async getCompanyTax(companyId: number): Promise<TaxRecord> {
    return this.client.request<TaxRecord>(
      `/api/crm/companies/${companyId}/tax`,
    );
  }

  // ============================================
  // REQUIRED DOCUMENTS
  // ============================================

  /**
   * Get required documents for a practice (CRM view)
   */
  async getRequiredDocuments(practiceId: number): Promise<RequiredDocument[]> {
    return this.client.request<RequiredDocument[]>(
      `/api/crm/practices/${practiceId}/required-documents`,
    );
  }

  /**
   * Add a required document to a practice
   */
  async addRequiredDocument(
    practiceId: number,
    data: RequiredDocumentCreate,
  ): Promise<RequiredDocument> {
    return this.client.request<RequiredDocument>(
      `/api/crm/practices/${practiceId}/required-documents`,
      {
        method: "POST",
        body: JSON.stringify(data),
      },
    );
  }

  /**
   * Update a required document (team member review)
   */
  async updateRequiredDocument(
    practiceId: number,
    docId: number,
    data: RequiredDocumentUpdate,
  ): Promise<RequiredDocument> {
    return this.client.request<RequiredDocument>(
      `/api/crm/practices/${practiceId}/required-documents/${docId}`,
      {
        method: "PATCH",
        body: JSON.stringify(data),
      },
    );
  }

  /**
   * Delete a required document
   */
  async deleteRequiredDocument(
    practiceId: number,
    docId: number,
  ): Promise<{ success: boolean; message: string }> {
    return this.client.request<{ success: boolean; message: string }>(
      `/api/crm/practices/${practiceId}/required-documents/${docId}`,
      { method: "DELETE" },
    );
  }

  /**
   * Client: Get required documents across all practices (Portal view)
   */
  async getClientRequiredDocuments(
    clientId: number,
  ): Promise<ClientRequiredDocument[]> {
    return this.client.request<ClientRequiredDocument[]>(
      `/api/crm/clients/client/${clientId}/required-documents`,
    );
  }

  /**
   * Client: Upload a document for a required field
   */
  async uploadClientDocument(
    practiceId: number,
    data: ClientDocumentUpload,
  ): Promise<{ success: boolean; document_id: number; message: string }> {
    return this.client.request<{
      success: boolean;
      document_id: number;
      message: string;
    }>(`/api/crm/practices/${practiceId}/upload-client-document`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  // ============================================================================
  // Portal Messages (team ↔ client messaging bridge)
  // ============================================================================

  async getPortalMessages(
    clientId: number,
    limit = 50,
    offset = 0,
  ): Promise<{ messages: PortalMessageThread[]; total: number }> {
    const resp = await this.client.request<{
      success: boolean;
      data: { messages: PortalMessageThread[]; total: number };
    }>(
      `/api/crm/portal/clients/${clientId}/messages?limit=${limit}&offset=${offset}`,
    );
    return resp.data;
  }

  async sendPortalMessage(
    clientId: number,
    content: string,
    subject?: string,
    practiceId?: number,
  ): Promise<PortalMessageThread> {
    const resp = await this.client.request<{
      success: boolean;
      data: PortalMessageThread;
    }>(`/api/crm/portal/clients/${clientId}/messages`, {
      method: "POST",
      body: JSON.stringify({ content, subject, practice_id: practiceId }),
    });
    return resp.data;
  }

  async markPortalMessageRead(
    clientId: number,
    messageId: number,
  ): Promise<void> {
    await this.client.request(
      `/api/crm/portal/clients/${clientId}/messages/${messageId}/read`,
      { method: "POST" },
    );
  }

  async getPortalUnreadCount(): Promise<{
    total_unread: number;
    by_client: {
      client_id: number;
      client_name: string;
      unread_count: number;
    }[];
  }> {
    const resp = await this.client.request<{
      success: boolean;
      data: {
        total_unread: number;
        by_client: {
          client_id: number;
          client_name: string;
          unread_count: number;
        }[];
      };
    }>("/api/crm/portal/messages/unread-count");
    return resp.data;
  }
}
