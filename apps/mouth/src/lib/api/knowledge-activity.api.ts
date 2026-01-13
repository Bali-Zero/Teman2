import type { IApiClient } from './types/api-client.types';

export type KBActionType = 'view' | 'download';

interface KBActivityPayload {
  action_type: KBActionType;
  resource_type: string;
  resource_id?: string;
  resource_title?: string;
  resource_category?: string;
}

/**
 * Knowledge Base Activity Tracking API
 * Logs views and downloads of KB content
 */
export class KnowledgeActivityApi {
  constructor(private client: IApiClient) {}

  /**
   * Log a knowledge base activity (view or download)
   * This is fire-and-forget - failures are silently ignored
   */
  async logActivity(payload: KBActivityPayload): Promise<void> {
    try {
      await this.client.request('/api/knowledge/activity/log', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    } catch (error) {
      // Silently ignore errors - logging is non-critical
      console.debug('KB activity log failed (non-critical):', error);
    }
  }

  /**
   * Log a page view
   */
  logView(resourceType: string, resourceId?: string, resourceTitle?: string, resourceCategory?: string): void {
    this.logActivity({
      action_type: 'view',
      resource_type: resourceType,
      resource_id: resourceId,
      resource_title: resourceTitle,
      resource_category: resourceCategory,
    });
  }

  /**
   * Log a download
   */
  logDownload(resourceType: string, resourceId?: string, resourceTitle?: string, resourceCategory?: string): void {
    this.logActivity({
      action_type: 'download',
      resource_type: resourceType,
      resource_id: resourceId,
      resource_title: resourceTitle,
      resource_category: resourceCategory,
    });
  }
}
