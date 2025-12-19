import { ApiClientBase } from '../client';
import type { KnowledgeSearchResponse, TierLevel } from './knowledge.types';

/**
 * Knowledge Search API methods
 */
export class KnowledgeApi {
  constructor(private client: ApiClientBase) {}

  async searchDocs(params: {
    query: string;
    level?: number;
    limit?: number;
    collection?: string | null;
    tier_filter?: TierLevel[] | null;
  }): Promise<KnowledgeSearchResponse> {
    const {
      query,
      level = this.client.isAdmin() ? 3 : 1,
      limit = 8,
      collection = null,
      tier_filter,
    } = params;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (this.client as any).request('/api/search/', {
      method: 'POST',
      body: JSON.stringify({
        query,
        level: Math.min(3, Math.max(0, level)),
        limit: Math.max(1, Math.min(50, limit)),
        collection,
        tier_filter: tier_filter ?? null,
      }),
    }) as Promise<KnowledgeSearchResponse>;
  }
}

