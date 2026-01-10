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
  cover_image?: string;
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

export interface SystemMetrics {
  agent_status: "active" | "idle" | "error";
  last_run: string | null;
  items_processed_today: number;
  avg_response_time_ms: number;
  qdrant_health: "healthy" | "degraded" | "down";
  next_scheduled_run: string | null;
  uptime_percentage: number;
}

export interface IntelligenceAnalytics {
  period_days: number;
  summary: {
    total_processed: number;
    total_approved: number;
    total_rejected: number;
    total_published: number;
    approval_rate: number;
    rejection_rate: number;
  };
  daily_trends: Array<{
    date: string;
    processed: number;
    approved: number;
    rejected: number;
    published: number;
  }>;
  type_breakdown: {
    visa: { processed: number; approved: number; rejected: number };
    news: { processed: number; approved: number; rejected: number; published: number };
  };
  detection_type_breakdown: {
    NEW: number;
    UPDATED: number;
  };
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

  /**
   * Get system metrics for System Pulse dashboard
   */
  getMetrics: async (): Promise<SystemMetrics> => {
    const endpoint = `/api/intel/metrics`;
    const startTime = performance.now();

    logger.apiCall(endpoint, 'GET', { action: 'get_metrics' });

    try {
      const response = await api.request<SystemMetrics>(endpoint);
      const responseTime = performance.now() - startTime;

      logger.apiSuccess(endpoint, responseTime, {
        action: 'get_metrics',
        metadata: {
          agent_status: response.agent_status,
          qdrant_health: response.qdrant_health,
          items_processed: response.items_processed_today,
        },
      });

      return response;
    } catch (error) {
      logger.apiError(endpoint, error as Error, { action: 'get_metrics' });
      throw error;
    }
  },

  /**
   * Get historical analytics and trends
   */
  getAnalytics: async (days: number = 30): Promise<IntelligenceAnalytics> => {
    const endpoint = `/api/intel/analytics?days=${days}`;
    const startTime = performance.now();

    logger.apiCall(endpoint, 'GET', { action: 'get_analytics', metadata: { days } });

    try {
      const response = await api.request<IntelligenceAnalytics>(endpoint);
      const responseTime = performance.now() - startTime;

      logger.apiSuccess(endpoint, responseTime, {
        action: 'get_analytics',
        metadata: {
          days,
          total_processed: response.summary.total_processed,
          approval_rate: response.summary.approval_rate,
        },
      });

      return response;
    } catch (error) {
      logger.apiError(endpoint, error as Error, { action: 'get_analytics', metadata: { days } });
      throw error;
    }
  },
};
