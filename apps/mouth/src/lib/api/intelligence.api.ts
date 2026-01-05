import { api } from "@/lib/api";
import { logger } from "@/lib/logger";

export interface StagingItem {
  id: string;
  type: "visa" | "news";
  title: string;
  status: "pending" | "approved" | "rejected";
  detected_at: string;
  source: string;
  detection_type: "NEW" | "UPDATED";
  content?: string;
  is_critical?: boolean;
}

export interface StagingResponse {
  items: StagingItem[];
  count: number;
}

export interface ApproveResponse {
  success: boolean;
  message: string;
  id: string;
}

export interface PublishResponse {
  success: boolean;
  message: string;
  id: string;
  title: string;
  published_url: string;
  published_at: string;
  collection: string;
}

export const intelligenceApi = {
  /**
   * Get pending items from staging
   */
  getPendingItems: async (type: "all" | "visa" | "news" = "all"): Promise<StagingResponse> => {
    const endpoint = `/api/intel/staging/pending?type=${type}`;
    const startTime = performance.now();

    logger.apiCall(endpoint, 'GET', { itemType: type === 'all' ? undefined : type });

    try {
      const response = await api.request<StagingResponse>(endpoint);
      const responseTime = performance.now() - startTime;

      logger.apiSuccess(endpoint, responseTime, {
        itemType: type === 'all' ? undefined : type,
        metadata: { count: response.count },
      });

      return response;
    } catch (error) {
      logger.apiError(endpoint, error as Error, { itemType: type === 'all' ? undefined : type });
      throw error;
    }
  },

  /**
   * Get preview of staging item (full content)
   */
  getPreview: async (type: "visa" | "news", id: string): Promise<StagingItem> => {
    const endpoint = `/api/intel/staging/preview/${type}/${id}`;
    const startTime = performance.now();

    logger.apiCall(endpoint, 'GET', { itemType: type, itemId: id });

    try {
      const response = await api.request<StagingItem>(endpoint);
      const responseTime = performance.now() - startTime;

      logger.apiSuccess(endpoint, responseTime, {
        itemType: type,
        itemId: id,
        metadata: { title: response.title },
      });

      return response;
    } catch (error) {
      logger.apiError(endpoint, error as Error, { itemType: type, itemId: id });
      throw error;
    }
  },

  /**
   * Approve item and ingest to Qdrant
   */
  approveItem: async (type: "visa" | "news", id: string): Promise<ApproveResponse> => {
    const endpoint = `/api/intel/staging/approve/${type}/${id}`;
    const startTime = performance.now();

    logger.apiCall(endpoint, 'POST', { itemType: type, itemId: id, action: 'approve' });

    try {
      const response = await api.request<ApproveResponse>(endpoint, { method: "POST" });
      const responseTime = performance.now() - startTime;

      logger.apiSuccess(endpoint, responseTime, {
        itemType: type,
        itemId: id,
        action: 'approve',
        metadata: { success: response.success },
      });

      logger.userAction('approve_item', type, id);

      return response;
    } catch (error) {
      logger.apiError(endpoint, error as Error, { itemType: type, itemId: id, action: 'approve' });
      throw error;
    }
  },

  /**
   * Reject item and archive
   */
  rejectItem: async (type: "visa" | "news", id: string): Promise<ApproveResponse> => {
    const endpoint = `/api/intel/staging/reject/${type}/${id}`;
    const startTime = performance.now();

    logger.apiCall(endpoint, 'POST', { itemType: type, itemId: id, action: 'reject' });

    try {
      const response = await api.request<ApproveResponse>(endpoint, { method: "POST" });
      const responseTime = performance.now() - startTime;

      logger.apiSuccess(endpoint, responseTime, {
        itemType: type,
        itemId: id,
        action: 'reject',
        metadata: { success: response.success },
      });

      logger.userAction('reject_item', type, id);

      return response;
    } catch (error) {
      logger.apiError(endpoint, error as Error, { itemType: type, itemId: id, action: 'reject' });
      throw error;
    }
  },

  /**
   * Publish item to knowledge base and register in anti-duplicate system
   */
  publishItem: async (type: "visa" | "news", id: string): Promise<PublishResponse> => {
    const endpoint = `/api/intel/staging/publish/${type}/${id}`;
    const startTime = performance.now();

    logger.apiCall(endpoint, 'POST', { itemType: type, itemId: id, action: 'publish' });

    try {
      const response = await api.request<PublishResponse>(endpoint, { method: "POST" });
      const responseTime = performance.now() - startTime;

      logger.apiSuccess(endpoint, responseTime, {
        itemType: type,
        itemId: id,
        action: 'publish',
        metadata: {
          success: response.success,
          published_url: response.published_url,
          collection: response.collection,
        },
      });

      logger.userAction('publish_item', type, id);

      return response;
    } catch (error) {
      logger.apiError(endpoint, error as Error, { itemType: type, itemId: id, action: 'publish' });
      throw error;
    }
  },
};
