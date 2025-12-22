import { describe, it, expect, beforeEach, vi } from 'vitest';
import { CrmApi } from './crm.api';
import { ApiClientBase } from '../client';
import type { Practice, Interaction, RenewalAlert } from './crm.types';

describe('CrmApi', () => {
  let crmApi: CrmApi;
  let mockClient: { request: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    mockClient = {
      request: vi.fn(),
    } as any;
    crmApi = new CrmApi(mockClient as unknown as ApiClientBase);
  });

  describe('getUpcomingRenewals', () => {
    it('should fetch upcoming renewals with default 90 days', async () => {
      const mockRenewals: RenewalAlert[] = [
        {
          id: 1,
          practice_id: 1,
          client_id: 1,
          alert_type: 'renewal_due',
          description: 'Practice renewal due soon',
          target_date: '2025-01-15',
          alert_date: '2025-01-01',
          status: 'pending',
        },
      ];

      mockClient.request.mockResolvedValue(mockRenewals);

      const result = await crmApi.getUpcomingRenewals();

      expect(mockClient.request).toHaveBeenCalledWith('/api/crm/practices/renewals/upcoming?days=90');
      expect(result).toEqual(mockRenewals);
    });

    it('should fetch upcoming renewals with custom days', async () => {
      const mockRenewals: RenewalAlert[] = [];
      mockClient.request.mockResolvedValue(mockRenewals);

      await crmApi.getUpcomingRenewals(30);

      expect(mockClient.request).toHaveBeenCalledWith('/api/crm/practices/renewals/upcoming?days=30');
    });
  });

  describe('getRevenueGrowth', () => {
    it('should fetch revenue growth data', async () => {
      const mockGrowth = {
        current_month: {
          total_revenue: 50000000,
          paid_revenue: 30000000,
          outstanding_revenue: 20000000,
        },
        previous_month: {
          total_revenue: 40000000,
          paid_revenue: 25000000,
          outstanding_revenue: 15000000,
        },
        growth_percentage: 25.0,
        monthly_breakdown: [],
      };

      (mockClient.request as ReturnType<typeof vi.fn>).mockResolvedValue(mockGrowth);

      const result = await crmApi.getRevenueGrowth();

      expect(mockClient.request).toHaveBeenCalledWith('/api/crm/practices/stats/revenue-growth');
      expect(result).toEqual(mockGrowth);
      expect(result.growth_percentage).toBe(25.0);
    });
  });

  describe('markInteractionRead', () => {
    it('should mark interaction as read', async () => {
      const mockResponse = {
        success: true,
        interaction_id: 1,
        read_receipt: true,
        read_at: '2025-01-01T10:00:00Z',
        read_by: 'zero@balizero.com',
      };

      (mockClient.request as ReturnType<typeof vi.fn>).mockResolvedValue(mockResponse);

      const result = await crmApi.markInteractionRead(1, 'zero@balizero.com');

      expect(mockClient.request).toHaveBeenCalledWith(
        '/api/crm/interactions/1/mark-read?read_by=zero%40balizero.com',
        { method: 'PATCH' }
      );
      expect(result.success).toBe(true);
      expect(result.read_receipt).toBe(true);
    });
  });

  describe('markInteractionsReadBatch', () => {
    it('should mark multiple interactions as read', async () => {
      const mockResponse = {
        success: true,
        updated_count: 3,
        read_by: 'zero@balizero.com',
      };

      (mockClient.request as ReturnType<typeof vi.fn>).mockResolvedValue(mockResponse);

      const result = await crmApi.markInteractionsReadBatch([1, 2, 3], 'zero@balizero.com');

      expect(mockClient.request).toHaveBeenCalledWith(
        expect.stringContaining('/api/crm/interactions/mark-read-batch'),
        { method: 'PATCH' }
      );
      expect(result.success).toBe(true);
      expect(result.updated_count).toBe(3);
    });
  });
});

