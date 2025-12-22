import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AdminApi } from './admin.api';
import { ApiClientBase } from '../client';

describe('AdminApi', () => {
  let adminApi: AdminApi;
  let mockClient: ApiClientBase;
  let mockRequest: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    mockRequest = vi.fn();
    mockClient = {
      request: mockRequest,
      getAdminHeaders: vi.fn(() => ({ 'X-User-Email': 'admin@example.com' })),
      getToken: vi.fn(() => 'admin-token'),
      getBaseUrl: vi.fn(() => 'https://api.test.com'),
    } as any;
    adminApi = new AdminApi(mockClient);
  });

  describe('getTeamStatus', () => {
    it('should get team status', async () => {
      const mockResponse = [
        {
          user_id: '1',
          email: 'user1@example.com',
          is_online: true,
          last_action: '2024-01-01T00:00:00Z',
          last_action_type: 'clock_in',
        },
      ];

      mockRequest.mockResolvedValueOnce(mockResponse);

      const result = await adminApi.getTeamStatus();

      expect(mockRequest).toHaveBeenCalledWith('/api/team/status', {
        headers: { 'X-User-Email': 'admin@example.com' },
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe('getDailyHours', () => {
    it('should get daily hours without date', async () => {
      const mockResponse = [
        {
          user_id: '1',
          email: 'user1@example.com',
          date: '2024-01-01',
          clock_in: '2024-01-01T08:00:00Z',
          clock_out: '2024-01-01T16:00:00Z',
          hours_worked: 8,
        },
      ];

      mockRequest.mockResolvedValueOnce(mockResponse);

      const result = await adminApi.getDailyHours();

      expect(mockRequest).toHaveBeenCalledWith('/api/team/hours?', {
        headers: { 'X-User-Email': 'admin@example.com' },
      });
      expect(result).toEqual(mockResponse);
    });

    it('should get daily hours with date', async () => {
      const mockResponse: any[] = [];
      mockRequest.mockResolvedValueOnce(mockResponse);

      await adminApi.getDailyHours('2024-01-01');

      expect(mockRequest).toHaveBeenCalledWith('/api/team/hours?date=2024-01-01', {
        headers: { 'X-User-Email': 'admin@example.com' },
      });
    });
  });

  describe('getWeeklySummary', () => {
    it('should get weekly summary without weekStart', async () => {
      const mockResponse = [
        {
          user_id: '1',
          email: 'user1@example.com',
          week_start: '2024-01-01',
          days_worked: 5,
          total_hours: 40,
          avg_hours_per_day: 8,
        },
      ];

      mockRequest.mockResolvedValueOnce(mockResponse);

      const result = await adminApi.getWeeklySummary();

      expect(mockRequest).toHaveBeenCalledWith('/api/team/activity/weekly?', {
        headers: { 'X-User-Email': 'admin@example.com' },
      });
      expect(result).toEqual(mockResponse);
    });

    it('should get weekly summary with weekStart', async () => {
      const mockResponse: any[] = [];
      mockRequest.mockResolvedValueOnce(mockResponse);

      await adminApi.getWeeklySummary('2024-01-01');

      expect(mockRequest).toHaveBeenCalledWith('/api/team/activity/weekly?week_start=2024-01-01', {
        headers: { 'X-User-Email': 'admin@example.com' },
      });
    });
  });

  describe('getMonthlySummary', () => {
    it('should get monthly summary without monthStart', async () => {
      const mockResponse = [
        {
          user_id: '1',
          email: 'user1@example.com',
          month_start: '2024-01-01',
          days_worked: 20,
          total_hours: 160,
          avg_hours_per_day: 8,
        },
      ];

      mockRequest.mockResolvedValueOnce(mockResponse);

      const result = await adminApi.getMonthlySummary();

      expect(mockRequest).toHaveBeenCalledWith('/api/team/activity/monthly?', {
        headers: { 'X-User-Email': 'admin@example.com' },
      });
      expect(result).toEqual(mockResponse);
    });

    it('should get monthly summary with monthStart', async () => {
      const mockResponse: any[] = [];
      mockRequest.mockResolvedValueOnce(mockResponse);

      await adminApi.getMonthlySummary('2024-01-01');

      expect(mockRequest).toHaveBeenCalledWith('/api/team/activity/monthly?month_start=2024-01-01', {
        headers: { 'X-User-Email': 'admin@example.com' },
      });
    });
  });

  describe('exportTimesheet', () => {
    beforeEach(() => {
      global.fetch = vi.fn();
    });

    it('should export timesheet as CSV', async () => {
      const mockBlob = new Blob(['csv,data'], { type: 'text/csv' });
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        blob: async () => mockBlob,
      });

      const result = await adminApi.exportTimesheet('2024-01-01', '2024-01-31');

      expect(global.fetch).toHaveBeenCalledWith(
        'https://api.test.com/api/team/export?start_date=2024-01-01&end_date=2024-01-31&format=csv',
        {
          headers: {
            'X-User-Email': 'admin@example.com',
            Authorization: 'Bearer admin-token',
          },
          credentials: 'include',
        }
      );
      expect(result).toBe(mockBlob);
    });

    it('should throw error on failed export', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        statusText: 'Internal Server Error',
      });

      await expect(adminApi.exportTimesheet('2024-01-01', '2024-01-31')).rejects.toThrow(
        'Failed to export timesheet'
      );
    });
  });
});
