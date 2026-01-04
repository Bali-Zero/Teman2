import type { IApiClient } from '../types/api-client.types';
import type {
  Practice,
  Interaction,
  PracticeStats,
  InteractionStats,
  Client,
  CreateClientParams,
  CreatePracticeParams,
  RenewalAlert,
  AutoCRMStats,
  ClientSummary,
  ClientProfile,
  FamilyMember,
  FamilyMemberCreate,
  ClientDocument,
  DocumentCreate,
  DocumentCategory,
  ExpiryAlert,
  ExpiryAlertsSummary,
} from './crm.types';

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
   * Get all practices with optional filtering
   */
  async getPractices(params: {
    status?: string;
    assigned_to?: string;
    limit?: number;
    offset?: number;
  } = {}): Promise<Practice[]> {
    const queryParams = new URLSearchParams();
    if (params.status) queryParams.append('status', params.status);
    if (params.assigned_to) queryParams.append('assigned_to', params.assigned_to);
    if (params.limit) queryParams.append('limit', params.limit.toString());
    if (params.offset) queryParams.append('offset', params.offset.toString());

    const queryString = queryParams.toString();
    const url = `/api/crm/practices${queryString ? `?${queryString}` : ''}`;

    return this.client.request<Practice[]>(url);
  }

  /**
   * Get interactions (e.g. WhatsApp messages)
   */
  async getInteractions(params: {
    interaction_type?: string;
    limit?: number;
    offset?: number;
  } = {}): Promise<Interaction[]> {
    const queryParams = new URLSearchParams();
    if (params.interaction_type) queryParams.append('interaction_type', params.interaction_type);
    if (params.limit) queryParams.append('limit', params.limit.toString());
    if (params.offset) queryParams.append('offset', params.offset.toString());

    const queryString = queryParams.toString();
    const url = `/api/crm/interactions${queryString ? `?${queryString}` : ''}`;

    return this.client.request<Interaction[]>(url);
  }

  /**
   * Get practice statistics
   */
  async getPracticeStats(): Promise<PracticeStats> {
    return this.client.request<PracticeStats>('/api/crm/practices/stats/overview');
  }

  /**
   * Get interaction statistics
   */
  async getInteractionStats(): Promise<InteractionStats> {
    return this.client.request<InteractionStats>('/api/crm/interactions/stats/overview');
  }

  /**
   * Get upcoming renewals/critical deadlines
   */
  async getUpcomingRenewals(days: number = 90): Promise<RenewalAlert[]> {
    return this.client.request<RenewalAlert[]>(`/api/crm/practices/renewals/upcoming?days=${days}`);
  }

  /**
   * Get revenue growth statistics (monthly comparison)
   */
  async getRevenueGrowth(): Promise<RevenueGrowthResponse> {
    return this.client.request<RevenueGrowthResponse>('/api/crm/practices/stats/revenue-growth');
  }

  /**
   * Mark an interaction as read
   */
  async markInteractionRead(interactionId: number, readBy: string): Promise<MarkReadResponse> {
    return this.client.request<MarkReadResponse>(
      `/api/crm/interactions/${interactionId}/mark-read?read_by=${encodeURIComponent(readBy)}`,
      { method: 'PATCH' }
    );
  }

  /**
   * Mark multiple interactions as read (batch)
   */
  async markInteractionsReadBatch(interactionIds: number[], readBy: string): Promise<BatchMarkReadResponse> {
    const queryParams = new URLSearchParams();
    interactionIds.forEach(id => queryParams.append('interaction_ids', id.toString()));
    queryParams.append('read_by', readBy);

    return this.client.request<BatchMarkReadResponse>(
      `/api/crm/interactions/mark-read-batch?${queryParams.toString()}`,
      { method: 'PATCH' }
    );
  }

  /**
   * Delete an interaction
   */
  async deleteInteraction(interactionId: number, deletedBy: string): Promise<{ success: boolean }> {
    return this.client.request<{ success: boolean }>(
      `/api/crm/interactions/${interactionId}?deleted_by=${encodeURIComponent(deletedBy)}`,
      { method: 'DELETE' }
    );
  }

  /**
   * Get all clients with optional search and filtering
   */
  async getClients(params: {
    search?: string;
    limit?: number;
    offset?: number;
  } = {}): Promise<Client[]> {
    const queryParams = new URLSearchParams();
    if (params.search) queryParams.append('search', params.search);
    if (params.limit) queryParams.append('limit', params.limit.toString());
    if (params.offset) queryParams.append('offset', params.offset.toString());

    const queryString = queryParams.toString();
    const url = `/api/crm/clients${queryString ? `?${queryString}` : ''}`;

    return this.client.request<Client[]>(url);
  }

  /**
   * Create a new client
   */
  async createClient(data: CreateClientParams, createdBy: string): Promise<Client> {
    const queryParams = new URLSearchParams();
    queryParams.append('created_by', createdBy);

    return this.client.request<Client>(
      `/api/crm/clients?${queryParams.toString()}`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
      60000 // 60 second timeout for creation
    );
  }

  /**
   * Create a new practice/case
   */
  async createPractice(data: CreatePracticeParams, createdBy: string): Promise<Practice> {
    const queryParams = new URLSearchParams();
    queryParams.append('created_by', createdBy);

    // Note: trailing slash required to avoid 307 redirect which converts POST to GET
    return this.client.request<Practice>(
      `/api/crm/practices/?${queryParams.toString()}`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      },
      60000 // 60 second timeout for creation
    );
  }

  /**
   * Get AUTO CRM extraction statistics
   */
  async getAutoCRMStats(days: number = 7): Promise<AutoCRMStats> {
    return this.client.request<AutoCRMStats>(`/api/crm/auto/stats?days=${days}`);
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
    }>,
    updatedBy: string
  ): Promise<Practice> {
    const queryParams = new URLSearchParams();
    queryParams.append('updated_by', updatedBy);

    // Note: trailing slash required to avoid 307 redirect which converts PATCH to GET
    return this.client.request<Practice>(
      `/api/crm/practices/${practiceId}/?${queryParams.toString()}`,
      {
        method: 'PATCH',
        body: JSON.stringify(updates),
      },
      60000 // 60 second timeout
    );
  }

  /**
   * Get a single client by ID
   */
  async getClient(clientId: number): Promise<Client> {
    return this.client.request<Client>(`/api/crm/clients/${clientId}`);
  }

  /**
   * Get client by email address (returns null if not found)
   */
  async getClientByEmail(email: string): Promise<Client | null> {
    try {
      return await this.client.request<Client>(`/api/crm/clients/by-email/${encodeURIComponent(email)}`);
    } catch (error) {
      // 404 means client not found - return null instead of throwing
      if (error instanceof Error && error.message.includes('404')) {
        return null;
      }
      throw error;
    }
  }

  /**
   * Get full client summary with cases, interactions, renewals
   */
  async getClientSummary(clientId: number): Promise<ClientSummary> {
    return this.client.request<ClientSummary>(`/api/crm/clients/${clientId}/summary`);
  }

  /**
   * Get client interaction timeline
   */
  async getClientTimeline(clientId: number, limit: number = 50): Promise<Interaction[]> {
    // Backend returns {client_id, total_interactions, timeline: Interaction[]}
    const response = await this.client.request<{ timeline: Interaction[] }>(
      `/api/crm/interactions/client/${clientId}/timeline?limit=${limit}`
    );
    return response.timeline || [];
  }

  /**
   * Get practices for a specific client
   */
  async getClientPractices(clientId: number): Promise<Practice[]> {
    return this.client.request<Practice[]>(`/api/crm/practices/?client_id=${clientId}`);
  }

  // ============================================
  // CLIENT PROFILE (Enhanced)
  // ============================================

  /**
   * Get enhanced client profile with family, documents, alerts
   */
  async getClientProfile(clientId: number): Promise<ClientProfile> {
    return this.client.request<ClientProfile>(`/api/crm/clients/${clientId}/profile`);
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
    }>
  ): Promise<{ success: boolean }> {
    return this.client.request<{ success: boolean }>(
      `/api/crm/clients/${clientId}/profile`,
      {
        method: 'PATCH',
        body: JSON.stringify(updates),
      }
    );
  }

  // ============================================
  // FAMILY MEMBERS
  // ============================================

  /**
   * Get family members for a client
   */
  async getFamilyMembers(clientId: number): Promise<FamilyMember[]> {
    return this.client.request<FamilyMember[]>(`/api/crm/clients/${clientId}/family`);
  }

  /**
   * Add a family member
   */
  async createFamilyMember(clientId: number, data: FamilyMemberCreate): Promise<{ id: number; success: boolean }> {
    return this.client.request<{ id: number; success: boolean }>(
      `/api/crm/clients/${clientId}/family`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      }
    );
  }

  /**
   * Update a family member
   */
  async updateFamilyMember(
    clientId: number,
    memberId: number,
    updates: Partial<FamilyMemberCreate>
  ): Promise<{ success: boolean }> {
    return this.client.request<{ success: boolean }>(
      `/api/crm/clients/${clientId}/family/${memberId}`,
      {
        method: 'PATCH',
        body: JSON.stringify(updates),
      }
    );
  }

  /**
   * Delete a family member
   */
  async deleteFamilyMember(clientId: number, memberId: number): Promise<{ success: boolean }> {
    return this.client.request<{ success: boolean }>(
      `/api/crm/clients/${clientId}/family/${memberId}`,
      { method: 'DELETE' }
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
    includeArchived?: boolean
  ): Promise<ClientDocument[]> {
    const params = new URLSearchParams();
    if (category) params.append('category', category);
    if (includeArchived) params.append('include_archived', 'true');
    const query = params.toString();
    return this.client.request<ClientDocument[]>(
      `/api/crm/clients/${clientId}/documents${query ? `?${query}` : ''}`
    );
  }

  /**
   * Add a document
   */
  async createDocument(clientId: number, data: DocumentCreate): Promise<{ id: number; success: boolean }> {
    return this.client.request<{ id: number; success: boolean }>(
      `/api/crm/clients/${clientId}/documents`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      }
    );
  }

  /**
   * Update a document
   */
  async updateDocument(
    clientId: number,
    docId: number,
    updates: Partial<DocumentCreate & { status: string; is_archived: boolean }>
  ): Promise<{ success: boolean }> {
    return this.client.request<{ success: boolean }>(
      `/api/crm/clients/${clientId}/documents/${docId}`,
      {
        method: 'PATCH',
        body: JSON.stringify(updates),
      }
    );
  }

  /**
   * Archive or delete a document
   */
  async deleteDocument(
    clientId: number,
    docId: number,
    permanent?: boolean
  ): Promise<{ success: boolean; action: string }> {
    return this.client.request<{ success: boolean; action: string }>(
      `/api/crm/clients/${clientId}/documents/${docId}${permanent ? '?permanent=true' : ''}`,
      { method: 'DELETE' }
    );
  }

  /**
   * Get document categories for dropdowns
   */
  async getDocumentCategories(): Promise<DocumentCategory[]> {
    return this.client.request<DocumentCategory[]>('/api/crm/document-categories');
  }

  // ============================================
  // EXPIRY ALERTS
  // ============================================

  /**
   * Get all expiry alerts (for team dashboard)
   */
  async getExpiryAlerts(params?: {
    alertColor?: 'expired' | 'red' | 'yellow';
    assignedTo?: string;
    limit?: number;
  }): Promise<ExpiryAlert[]> {
    const queryParams = new URLSearchParams();
    if (params?.alertColor) queryParams.append('alert_color', params.alertColor);
    if (params?.assignedTo) queryParams.append('assigned_to', params.assignedTo);
    if (params?.limit) queryParams.append('limit', params.limit.toString());
    const query = queryParams.toString();
    return this.client.request<ExpiryAlert[]>(
      `/api/crm/expiry-alerts${query ? `?${query}` : ''}`
    );
  }

  /**
   * Get expiry alerts summary for dashboard
   */
  async getExpiryAlertsSummary(): Promise<ExpiryAlertsSummary> {
    return this.client.request<ExpiryAlertsSummary>('/api/crm/expiry-alerts/summary');
  }

  // ============================================
  // CLIENT MANAGEMENT
  // ============================================

  /**
   * Delete a client (soft delete - marks as inactive)
   * Only admins or authorized team members should call this
   */
  async deleteClient(clientId: number, deletedBy: string): Promise<{ success: boolean; message: string }> {
    return this.client.request<{ success: boolean; message: string }>(
      `/api/crm/clients/${clientId}?deleted_by=${encodeURIComponent(deletedBy)}`,
      { method: 'DELETE' }
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
    }>,
    updatedBy: string
  ): Promise<Client> {
    return this.client.request<Client>(
      `/api/crm/clients/${clientId}?updated_by=${encodeURIComponent(updatedBy)}`,
      {
        method: 'PATCH',
        body: JSON.stringify(updates),
      }
    );
  }

  /**
   * Delete a practice/case (soft delete - marks as cancelled)
   * Only admins or the client's lead can delete practices
   */
  async deletePractice(practiceId: number, deletedBy: string): Promise<{ success: boolean; message: string }> {
    return this.client.request<{ success: boolean; message: string }>(
      `/api/crm/practices/${practiceId}?deleted_by=${encodeURIComponent(deletedBy)}`,
      { method: 'DELETE' }
    );
  }

  /**
   * Create an interaction/note for a client
   */
  async createInteraction(data: {
    client_id: number;
    interaction_type: 'note' | 'chat' | 'email' | 'whatsapp' | 'call' | 'meeting';
    summary: string;
    subject?: string;
    team_member: string;
    direction?: 'inbound' | 'outbound';
    practice_id?: number;
  }): Promise<Interaction> {
    return this.client.request<Interaction>(
      '/api/crm/interactions/',
      {
        method: 'POST',
        body: JSON.stringify({
          ...data,
          direction: data.direction || 'outbound',
          channel: 'workspace',
        }),
      }
    );
  }
}
