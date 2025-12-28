import type { IApiClient } from '../types/api-client.types';
import type { Practice, Interaction, PracticeStats, InteractionStats, Client, CreateClientParams, CreatePracticeParams, RenewalAlert, AutoCRMStats } from './crm.types';

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

    return this.client.request<Practice>(
      `/api/crm/practices?${queryParams.toString()}`,
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
}
