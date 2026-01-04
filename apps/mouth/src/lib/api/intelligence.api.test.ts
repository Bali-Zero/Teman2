import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { intelligenceApi, StagingResponse, StagingItem, ApproveResponse } from './intelligence.api';
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
});
