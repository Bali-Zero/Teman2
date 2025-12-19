import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ApiClient } from '../api-client';
import { UserProfile } from '@/types';

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
  };
})();

Object.defineProperty(window, 'localStorage', { value: localStorageMock });

describe('Admin Workflow Integration Tests', () => {
  let api: ApiClient;
  const baseUrl = 'https://api.test.com';

  beforeEach(() => {
    localStorageMock.clear();
    vi.clearAllMocks();
    api = new ApiClient(baseUrl);

    const adminProfile: UserProfile = {
      id: 'admin-123',
      email: 'admin@example.com',
      name: 'Admin User',
      role: 'admin',
    };
    api.setUserProfile(adminProfile);
    api.setToken('admin-token');
  });

  describe('Team Management Workflow', () => {
    it('should get team status, daily hours, and weekly summary', async () => {
      // Get team status
      const teamStatusResponse = [
        {
          user_id: '1',
          email: 'user1@example.com',
          is_online: true,
          last_action: '2024-01-01T08:00:00Z',
          last_action_type: 'clock_in',
        },
        {
          user_id: '2',
          email: 'user2@example.com',
          is_online: false,
          last_action: '2024-01-01T16:00:00Z',
          last_action_type: 'clock_out',
        },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => teamStatusResponse,
      });

      const teamStatus = await api.getTeamStatus();
      expect(teamStatus).toHaveLength(2);
      expect(teamStatus[0].is_online).toBe(true);

      // Get daily hours
      const dailyHoursResponse = [
        {
          user_id: '1',
          email: 'user1@example.com',
          date: '2024-01-01',
          clock_in: '2024-01-01T08:00:00Z',
          clock_out: '2024-01-01T16:00:00Z',
          hours_worked: 8,
        },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => dailyHoursResponse,
      });

      const dailyHours = await api.getDailyHours('2024-01-01');
      expect(dailyHours).toHaveLength(1);
      expect(dailyHours[0].hours_worked).toBe(8);

      // Get weekly summary
      const weeklySummaryResponse = [
        {
          user_id: '1',
          email: 'user1@example.com',
          week_start: '2024-01-01',
          days_worked: 5,
          total_hours: 40,
          avg_hours_per_day: 8,
        },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => weeklySummaryResponse,
      });

      const weeklySummary = await api.getWeeklySummary('2024-01-01');
      expect(weeklySummary).toHaveLength(1);
      expect(weeklySummary[0].total_hours).toBe(40);
    });

    it('should export timesheet as CSV', async () => {
      const mockBlob = new Blob(['csv,data'], { type: 'text/csv' });

      mockFetch.mockResolvedValueOnce({
        ok: true,
        blob: async () => mockBlob,
      });

      const blob = await api.exportTimesheet('2024-01-01', '2024-01-31');

      expect(blob).toBe(mockBlob);
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('start_date=2024-01-01'),
        expect.objectContaining({
          headers: expect.objectContaining({
            'X-User-Email': 'admin@example.com',
          }),
        })
      );
    });
  });
});

