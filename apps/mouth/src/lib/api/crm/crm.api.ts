import { ApiClientBase } from '../client';
import type { Practice, Interaction, PracticeStats, InteractionStats, Client, CreateClientParams, CreatePracticeParams, RenewalAlert } from './crm.types';

export class CrmApi {
  constructor(private client: ApiClientBase) {}

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

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (this.client as any).request(url) as Promise<Practice[]>;
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

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (this.client as any).request(url) as Promise<Interaction[]>;
  }

  /**
   * Get practice statistics
   */
  async getPracticeStats(): Promise<PracticeStats> {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (this.client as any).request('/api/crm/practices/stats/overview') as Promise<PracticeStats>;
  }

  /**
   * Get interaction statistics
   */
  async getInteractionStats(): Promise<InteractionStats> {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (this.client as any).request('/api/crm/interactions/stats/overview') as Promise<InteractionStats>;
  }

  /**
   * Get upcoming renewals/critical deadlines
   */
  async getUpcomingRenewals(days: number = 90): Promise<RenewalAlert[]> {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (this.client as any).request(`/api/crm/practices/renewals/upcoming?days=${days}`) as Promise<RenewalAlert[]>;
  }

  /**
   * Get revenue growth statistics (monthly comparison)
   */
  async getRevenueGrowth(): Promise<{
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
  }> {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (this.client as any).request('/api/crm/practices/stats/revenue-growth') as Promise<any>;
  }

  /**
   * Mark an interaction as read
   */
  async markInteractionRead(interactionId: number, readBy: string): Promise<{
    success: boolean;
    interaction_id: number;
    read_receipt: boolean;
    read_at: string;
    read_by: string;
  }> {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (this.client as any).request(`/api/crm/interactions/${interactionId}/mark-read?read_by=${encodeURIComponent(readBy)}`, {
      method: 'PATCH',
    }) as Promise<any>;
  }

  /**
   * Mark multiple interactions as read (batch)
   */
  async markInteractionsReadBatch(interactionIds: number[], readBy: string): Promise<{
    success: boolean;
    updated_count: number;
    read_by: string;
  }> {
    const queryParams = new URLSearchParams();
    interactionIds.forEach(id => queryParams.append('interaction_ids', id.toString()));
    queryParams.append('read_by', readBy);
    
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (this.client as any).request(`/api/crm/interactions/mark-read-batch?${queryParams.toString()}`, {
      method: 'PATCH',
    }) as Promise<any>;
  }
  /**
   * Create a new client
   */
  async createClient(data: CreateClientParams, createdBy: string): Promise<Client> {
    const queryParams = new URLSearchParams();
    queryParams.append('created_by', createdBy);
    
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (this.client as any).request(`/api/crm/clients?${queryParams.toString()}`, {
      method: 'POST',
      body: JSON.stringify(data),
    }) as Promise<Client>;
  }

  /**
   * Create a new practice/case
   */
  async createPractice(data: CreatePracticeParams, createdBy: string): Promise<Practice> {
    const queryParams = new URLSearchParams();
    queryParams.append('created_by', createdBy);

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (this.client as any).request(`/api/crm/practices?${queryParams.toString()}`, {
       method: 'POST',
       body: JSON.stringify(data),
    }) as Promise<Practice>;
  }
}
