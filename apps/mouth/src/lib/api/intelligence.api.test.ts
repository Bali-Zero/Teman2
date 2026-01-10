import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { intelligenceApi, StagingResponse, StagingItem, ApproveResponse, SystemMetrics, PublishResponse } from './intelligence.api';
import { api } from '@/lib/api';
import { logger } from '@/lib/logger';

vi.mock('@/lib/api');
vi.mock('@/lib/logger');

describe('intelligence.api', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(performance, 'now').mockReturnValue(1000);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('getPendingItems', () => {
    it('should fetch all pending items successfully', async () => {
      const mockResponse: StagingResponse = {
        items: [
          { id: '1', type: 'visa', title: 'Visa Update', status: 'pending', detected_at: '2025-01-01', source: 'http://test.com', detection_type: 'NEW' },
          { id: '2', type: 'news', title: 'News Item', status: 'pending', detected_at: '2025-01-02', source: 'http://test2.com', detection_type: 'UPDATED' }
        ],
        count: 2,
      };

      vi.mocked(api.request).mockResolvedValue(mockResponse);

      const result = await intelligenceApi.getPendingItems('all');

      expect(api.request).toHaveBeenCalledWith('/api/intel/staging/pending?type=all');
      expect(logger.apiCall).toHaveBeenCalledWith('/api/intel/staging/pending?type=all', 'GET', { itemType: undefined });
      expect(logger.apiSuccess).toHaveBeenCalledWith(
        '/api/intel/staging/pending?type=all',
        0,
        expect.objectContaining({ metadata: { count: 2 } })
      );
      expect(result).toEqual(mockResponse);
    });

    it('should fetch visa-only items successfully', async () => {
      const mockResponse: StagingResponse = {
        items: [{ id: '1', type: 'visa', title: 'Visa Update', status: 'pending', detected_at: '2025-01-01', source: 'http://test.com', detection_type: 'NEW' }],
        count: 1,
      };

      vi.mocked(api.request).mockResolvedValue(mockResponse);

      const result = await intelligenceApi.getPendingItems('visa');

      expect(api.request).toHaveBeenCalledWith('/api/intel/staging/pending?type=visa');
      expect(logger.apiCall).toHaveBeenCalledWith('/api/intel/staging/pending?type=visa', 'GET', { itemType: 'visa' });
      expect(result).toEqual(mockResponse);
    });

    it('should fetch news-only items successfully', async () => {
      const mockResponse: StagingResponse = {
        items: [{ id: '2', type: 'news', title: 'News Item', status: 'pending', detected_at: '2025-01-02', source: 'http://test2.com', detection_type: 'UPDATED' }],
        count: 1,
      };

      vi.mocked(api.request).mockResolvedValue(mockResponse);

      const result = await intelligenceApi.getPendingItems('news');

      expect(api.request).toHaveBeenCalledWith('/api/intel/staging/pending?type=news');
      expect(logger.apiCall).toHaveBeenCalledWith('/api/intel/staging/pending?type=news', 'GET', { itemType: 'news' });
      expect(result).toEqual(mockResponse);
    });

    it('should log performance timing correctly', async () => {
      vi.spyOn(performance, 'now')
        .mockReturnValueOnce(1000) // start
        .mockReturnValueOnce(1250); // end

      const mockResponse: StagingResponse = { items: [], count: 0 };
      vi.mocked(api.request).mockResolvedValue(mockResponse);

      await intelligenceApi.getPendingItems('all');

      expect(logger.apiSuccess).toHaveBeenCalledWith(
        '/api/intel/staging/pending?type=all',
        250, // 1250 - 1000
        expect.any(Object)
      );
    });

    it('should handle and log errors', async () => {
      const mockError = new Error('Network error');
      vi.mocked(api.request).mockRejectedValue(mockError);

      await expect(intelligenceApi.getPendingItems('all')).rejects.toThrow('Network error');

      expect(logger.apiCall).toHaveBeenCalled();
      expect(logger.apiError).toHaveBeenCalledWith(
        '/api/intel/staging/pending?type=all',
        mockError,
        { itemType: undefined }
      );
    });
  });

  describe('getPreview', () => {
    it('should fetch preview for visa item successfully', async () => {
      const mockItem: StagingItem = {
        id: 'visa-123',
        type: 'visa',
        title: 'Visa Preview',
        status: 'pending',
        detected_at: '2025-01-01',
        source: 'http://test.com',
        detection_type: 'NEW',
        content: 'Full content here',
      };

      vi.mocked(api.request).mockResolvedValue(mockItem);

      const result = await intelligenceApi.getPreview('visa', 'visa-123');

      expect(api.request).toHaveBeenCalledWith('/api/intel/staging/preview/visa/visa-123');
      expect(logger.apiCall).toHaveBeenCalledWith('/api/intel/staging/preview/visa/visa-123', 'GET', { itemType: 'visa', itemId: 'visa-123' });
      expect(logger.apiSuccess).toHaveBeenCalledWith(
        '/api/intel/staging/preview/visa/visa-123',
        0,
        expect.objectContaining({ metadata: { title: 'Visa Preview' } })
      );
      expect(result).toEqual(mockItem);
    });

    it('should fetch preview for news item successfully', async () => {
      const mockItem: StagingItem = {
        id: 'news-456',
        type: 'news',
        title: 'News Preview',
        status: 'pending',
        detected_at: '2025-01-02',
        source: 'http://test2.com',
        detection_type: 'UPDATED',
        content: 'Full news content',
      };

      vi.mocked(api.request).mockResolvedValue(mockItem);

      const result = await intelligenceApi.getPreview('news', 'news-456');

      expect(api.request).toHaveBeenCalledWith('/api/intel/staging/preview/news/news-456');
      expect(logger.apiCall).toHaveBeenCalledWith('/api/intel/staging/preview/news/news-456', 'GET', { itemType: 'news', itemId: 'news-456' });
      expect(result).toEqual(mockItem);
    });

    it('should handle and log errors', async () => {
      const mockError = new Error('Preview not found');
      vi.mocked(api.request).mockRejectedValue(mockError);

      await expect(intelligenceApi.getPreview('visa', 'invalid-id')).rejects.toThrow('Preview not found');

      expect(logger.apiError).toHaveBeenCalledWith(
        '/api/intel/staging/preview/visa/invalid-id',
        mockError,
        { itemType: 'visa', itemId: 'invalid-id' }
      );
    });
  });

  describe('approveItem', () => {
    it('should approve visa item successfully', async () => {
      const mockResponse: ApproveResponse = {
        success: true,
        message: 'Item approved and ingested',
        id: 'visa-123',
      };

      vi.mocked(api.request).mockResolvedValue(mockResponse);

      const result = await intelligenceApi.approveItem('visa', 'visa-123');

      expect(api.request).toHaveBeenCalledWith('/api/intel/staging/approve/visa/visa-123', { method: 'POST' });
      expect(logger.apiCall).toHaveBeenCalledWith('/api/intel/staging/approve/visa/visa-123', 'POST', { itemType: 'visa', itemId: 'visa-123', action: 'approve' });
      expect(logger.apiSuccess).toHaveBeenCalled();
      expect(logger.userAction).toHaveBeenCalledWith('approve_item', 'visa', 'visa-123');
      expect(result).toEqual(mockResponse);
    });

    it('should approve news item successfully', async () => {
      const mockResponse: ApproveResponse = {
        success: true,
        message: 'Item approved and ingested',
        id: 'news-456',
      };

      vi.mocked(api.request).mockResolvedValue(mockResponse);

      const result = await intelligenceApi.approveItem('news', 'news-456');

      expect(api.request).toHaveBeenCalledWith('/api/intel/staging/approve/news/news-456', { method: 'POST' });
      expect(logger.userAction).toHaveBeenCalledWith('approve_item', 'news', 'news-456');
      expect(result).toEqual(mockResponse);
    });

    it('should log user action on approval', async () => {
      const mockResponse: ApproveResponse = {
        success: true,
        message: 'Item approved',
        id: 'test-id',
      };

      vi.mocked(api.request).mockResolvedValue(mockResponse);

      await intelligenceApi.approveItem('visa', 'test-id');

      expect(logger.userAction).toHaveBeenCalledWith('approve_item', 'visa', 'test-id');
    });

    it('should handle and log errors', async () => {
      const mockError = new Error('Approval failed');
      vi.mocked(api.request).mockRejectedValue(mockError);

      await expect(intelligenceApi.approveItem('visa', 'fail-id')).rejects.toThrow('Approval failed');

      expect(logger.apiError).toHaveBeenCalledWith(
        '/api/intel/staging/approve/visa/fail-id',
        mockError,
        { itemType: 'visa', itemId: 'fail-id', action: 'approve' }
      );
    });
  });

  describe('rejectItem', () => {
    it('should reject visa item successfully', async () => {
      const mockResponse: ApproveResponse = {
        success: true,
        message: 'Item rejected and archived',
        id: 'visa-789',
      };

      vi.mocked(api.request).mockResolvedValue(mockResponse);

      const result = await intelligenceApi.rejectItem('visa', 'visa-789');

      expect(api.request).toHaveBeenCalledWith('/api/intel/staging/reject/visa/visa-789', { method: 'POST' });
      expect(logger.apiCall).toHaveBeenCalledWith('/api/intel/staging/reject/visa/visa-789', 'POST', { itemType: 'visa', itemId: 'visa-789', action: 'reject' });
      expect(logger.userAction).toHaveBeenCalledWith('reject_item', 'visa', 'visa-789');
      expect(result).toEqual(mockResponse);
    });

    it('should reject news item successfully', async () => {
      const mockResponse: ApproveResponse = {
        success: true,
        message: 'Item rejected and archived',
        id: 'news-999',
      };

      vi.mocked(api.request).mockResolvedValue(mockResponse);

      const result = await intelligenceApi.rejectItem('news', 'news-999');

      expect(api.request).toHaveBeenCalledWith('/api/intel/staging/reject/news/news-999', { method: 'POST' });
      expect(logger.userAction).toHaveBeenCalledWith('reject_item', 'news', 'news-999');
      expect(result).toEqual(mockResponse);
    });

    it('should handle and log errors', async () => {
      const mockError = new Error('Rejection failed');
      vi.mocked(api.request).mockRejectedValue(mockError);

      await expect(intelligenceApi.rejectItem('news', 'fail-reject')).rejects.toThrow('Rejection failed');

      expect(logger.apiError).toHaveBeenCalledWith(
        '/api/intel/staging/reject/news/fail-reject',
        mockError,
        { itemType: 'news', itemId: 'fail-reject', action: 'reject' }
      );
    });
  });

  describe('publishItem', () => {
    it('should publish visa item successfully', async () => {
      const mockResponse: PublishResponse = {
        success: true,
        message: 'Item published',
        id: 'visa-123',
        title: 'Visa Update',
        published_url: 'https://example.com/visa-123',
        published_at: '2025-01-01T10:00:00Z',
        collection: 'visa_oracle',
      };

      vi.mocked(api.request).mockResolvedValue(mockResponse);

      const result = await intelligenceApi.publishItem('visa', 'visa-123');

      expect(api.request).toHaveBeenCalledWith('/api/intel/staging/publish/visa/visa-123', { method: 'POST' });
      expect(logger.apiCall).toHaveBeenCalledWith('/api/intel/staging/publish/visa/visa-123', 'POST', { itemType: 'visa', itemId: 'visa-123', action: 'publish' });
      expect(logger.userAction).toHaveBeenCalledWith('publish_item', 'visa', 'visa-123');
      expect(result).toEqual(mockResponse);
    });

    it('should publish news item successfully', async () => {
      const mockResponse: PublishResponse = {
        success: true,
        message: 'Item published',
        id: 'news-456',
        title: 'News Item',
        published_url: 'https://example.com/news-456',
        published_at: '2025-01-02T11:00:00Z',
        collection: 'news_collection',
      };

      vi.mocked(api.request).mockResolvedValue(mockResponse);

      const result = await intelligenceApi.publishItem('news', 'news-456');

      expect(api.request).toHaveBeenCalledWith('/api/intel/staging/publish/news/news-456', { method: 'POST' });
      expect(logger.userAction).toHaveBeenCalledWith('publish_item', 'news', 'news-456');
      expect(result).toEqual(mockResponse);
    });

    it('should handle and log errors', async () => {
      const mockError = new Error('Publish failed');
      vi.mocked(api.request).mockRejectedValue(mockError);

      await expect(intelligenceApi.publishItem('visa', 'fail-publish')).rejects.toThrow('Publish failed');

      expect(logger.apiError).toHaveBeenCalledWith(
        '/api/intel/staging/publish/visa/fail-publish',
        mockError,
        { itemType: 'visa', itemId: 'fail-publish', action: 'publish' }
      );
    });
  });

  describe('getMetrics', () => {
    it('should fetch system metrics successfully', async () => {
      const mockMetrics: SystemMetrics = {
        agent_status: 'active',
        last_run: '2025-01-05T10:30:00Z',
        items_processed_today: 15,
        avg_response_time_ms: 2500,
        qdrant_health: 'healthy',
        next_scheduled_run: '2025-01-05T12:00:00Z',
        uptime_percentage: 99.8,
      };

      vi.mocked(api.request).mockResolvedValue(mockMetrics);

      const result = await intelligenceApi.getMetrics();

      expect(api.request).toHaveBeenCalledWith('/api/intel/metrics');
      expect(logger.apiCall).toHaveBeenCalledWith('/api/intel/metrics', 'GET', { action: 'get_metrics' });
      expect(logger.apiSuccess).toHaveBeenCalledWith(
        '/api/intel/metrics',
        0,
        expect.objectContaining({
          metadata: expect.objectContaining({
            agent_status: 'active',
            qdrant_health: 'healthy',
            items_processed: 15,
          }),
        })
      );
      expect(result).toEqual(mockMetrics);
    });

    it('should handle null values in metrics', async () => {
      const mockMetrics: SystemMetrics = {
        agent_status: 'idle',
        last_run: null,
        items_processed_today: 0,
        avg_response_time_ms: 0,
        qdrant_health: 'degraded',
        next_scheduled_run: null,
        uptime_percentage: 0,
      };

      vi.mocked(api.request).mockResolvedValue(mockMetrics);

      const result = await intelligenceApi.getMetrics();

      expect(result).toEqual(mockMetrics);
      expect(result.last_run).toBeNull();
      expect(result.next_scheduled_run).toBeNull();
    });

    it('should handle and log errors', async () => {
      const mockError = new Error('Metrics unavailable');
      vi.mocked(api.request).mockRejectedValue(mockError);

      await expect(intelligenceApi.getMetrics()).rejects.toThrow('Metrics unavailable');

      expect(logger.apiError).toHaveBeenCalledWith(
        '/api/intel/metrics',
        mockError,
        { action: 'get_metrics' }
      );
    });
  });

  describe('getAnalytics', () => {
    it('should fetch analytics successfully', async () => {
      const mockAnalytics: IntelligenceAnalytics = {
        period_days: 30,
        summary: {
          total_processed: 150,
          total_approved: 120,
          total_rejected: 30,
          total_published: 45,
          approval_rate: 80.0,
          rejection_rate: 20.0,
        },
        daily_trends: [
          { date: '2025-01-01', processed: 5, approved: 4, rejected: 1, published: 2 },
        ],
        type_breakdown: {
          visa: { processed: 100, approved: 80, rejected: 20 },
          news: { processed: 50, approved: 40, rejected: 10, published: 45 },
        },
        detection_type_breakdown: {
          NEW: 90,
          UPDATED: 60,
        },
      };

      vi.mocked(api.request).mockResolvedValue(mockAnalytics);

      const result = await intelligenceApi.getAnalytics(30);

      expect(api.request).toHaveBeenCalledWith('/api/intel/analytics?days=30');
      expect(logger.apiCall).toHaveBeenCalledWith('/api/intel/analytics?days=30', 'GET', { action: 'get_analytics', days: 30 });
      expect(logger.apiSuccess).toHaveBeenCalledWith(
        '/api/intel/analytics?days=30',
        0,
        expect.objectContaining({
          metadata: expect.objectContaining({
            total_processed: 150,
            approval_rate: 80.0,
          }),
        })
      );
      expect(result).toEqual(mockAnalytics);
    });

    it('should handle different period days', async () => {
      const mockAnalytics: IntelligenceAnalytics = {
        period_days: 7,
        summary: {
          total_processed: 50,
          total_approved: 40,
          total_rejected: 10,
          total_published: 15,
          approval_rate: 80.0,
          rejection_rate: 20.0,
        },
        daily_trends: [],
        type_breakdown: {
          visa: { processed: 30, approved: 25, rejected: 5 },
          news: { processed: 20, approved: 15, rejected: 5, published: 15 },
        },
        detection_type_breakdown: {
          NEW: 30,
          UPDATED: 20,
        },
      };

      vi.mocked(api.request).mockResolvedValue(mockAnalytics);

      const result = await intelligenceApi.getAnalytics(7);

      expect(api.request).toHaveBeenCalledWith('/api/intel/analytics?days=7');
      expect(result.period_days).toBe(7);
    });

    it('should handle and log errors', async () => {
      const mockError = new Error('Analytics unavailable');
      vi.mocked(api.request).mockRejectedValue(mockError);

      await expect(intelligenceApi.getAnalytics(30)).rejects.toThrow('Analytics unavailable');

      expect(logger.apiError).toHaveBeenCalledWith(
        '/api/intel/analytics?days=30',
        mockError,
        { action: 'get_analytics', days: 30 }
      );
    });
  });
});
