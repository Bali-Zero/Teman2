/** Omnichannel API client — threads, messages, CRM context. */

import type { IApiClient } from '../types/api-client.types';
import type {
  CRMContext,
  OmnichannelStats,
  ThreadDetail,
  ThreadFilter,
  ThreadListResponse,
} from './omnichannel.types';

export class OmnichannelApi {
  constructor(private client: IApiClient) {}

  async getThreads(filters: ThreadFilter = {}): Promise<ThreadListResponse> {
    const params = new URLSearchParams();
    if (filters.status) params.set('status', filters.status);
    if (filters.priority) params.set('priority', filters.priority);
    if (filters.assigned_to) params.set('assigned_to', filters.assigned_to);
    if (filters.channel) params.set('channel', filters.channel);
    if (filters.search) params.set('search', filters.search);
    params.set('limit', String(filters.limit ?? 50));
    params.set('offset', String(filters.offset ?? 0));

    return this.client.request<ThreadListResponse>(`/api/omnichannel/threads?${params.toString()}`);
  }

  async getThread(threadId: string, messageLimit = 100): Promise<ThreadDetail> {
    return this.client.request<ThreadDetail>(
      `/api/omnichannel/threads/${threadId}?message_limit=${messageLimit}`
    );
  }

  async updateThread(
    threadId: string,
    update: { status?: string; priority?: string; assigned_to?: string }
  ): Promise<{ status: string }> {
    return this.client.request<{ status: string }>(`/api/omnichannel/threads/${threadId}`, {
      method: 'PATCH',
      body: JSON.stringify(update),
    });
  }

  async sendMessage(
    threadId: string,
    content: string,
    options: { channel?: string; is_internal_note?: boolean } = {}
  ): Promise<{ status: string; message_id: number }> {
    return this.client.request<{ status: string; message_id: number }>(
      `/api/omnichannel/threads/${threadId}/messages`,
      {
        method: 'POST',
        body: JSON.stringify({
          content,
          channel: options.channel,
          is_internal_note: options.is_internal_note ?? false,
        }),
      }
    );
  }

  async assignThread(threadId: string, assignee: string): Promise<{ status: string }> {
    return this.client.request<{ status: string }>(`/api/omnichannel/threads/${threadId}/assign`, {
      method: 'POST',
      body: JSON.stringify({ assignee }),
    });
  }

  async getContext(threadId: string): Promise<CRMContext> {
    return this.client.request<CRMContext>(`/api/omnichannel/threads/${threadId}/context`);
  }

  async getStats(): Promise<OmnichannelStats> {
    return this.client.request<OmnichannelStats>('/api/omnichannel/stats');
  }
}
