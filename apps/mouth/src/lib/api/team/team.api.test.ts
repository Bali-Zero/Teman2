import { describe, it, expect, vi, beforeEach } from 'vitest';
import { TeamApi } from './team.api';
import { ApiClientBase } from '../client';
import type { ClockResponse, UserStatusResponse } from './team.types';

describe('TeamApi', () => {
  let teamApi: TeamApi;
  let mockClient: ApiClientBase;
  let mockRequest: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    mockRequest = vi.fn();
    mockClient = {
      request: mockRequest,
      getUserProfile: vi.fn(),
    } as any;
    teamApi = new TeamApi(mockClient);
  });

  describe('clockIn', () => {
    it('should clock in successfully', async () => {
      const mockProfile = {
        id: '123',
        email: 'test@example.com',
      };
      const mockResponse: ClockResponse = {
        success: true,
        action: 'clock_in',
        timestamp: '2024-01-01T00:00:00Z',
        bali_time: '2024-01-01T08:00:00+08:00',
        message: 'Clocked in successfully',
      };

      (mockClient.getUserProfile as any).mockReturnValue(mockProfile);
      mockRequest.mockResolvedValueOnce(mockResponse);

      const result = await teamApi.clockIn();

      expect(mockRequest).toHaveBeenCalledWith('/api/team/clock-in', {
        method: 'POST',
        body: JSON.stringify({
          user_id: '123',
          email: 'test@example.com',
        }),
      });
      expect(result).toEqual(mockResponse);
    });

    it('should throw error if user profile not loaded', async () => {
      (mockClient.getUserProfile as any).mockReturnValue(null);

      await expect(teamApi.clockIn()).rejects.toThrow(
        'User profile not loaded. Please login again.'
      );
    });
  });

  describe('clockOut', () => {
    it('should clock out successfully', async () => {
      const mockProfile = {
        id: '123',
        email: 'test@example.com',
      };
      const mockResponse: ClockResponse = {
        success: true,
        action: 'clock_out',
        timestamp: '2024-01-01T08:00:00Z',
        bali_time: '2024-01-01T16:00:00+08:00',
        message: 'Clocked out successfully',
        hours_worked: 8,
      };

      (mockClient.getUserProfile as any).mockReturnValue(mockProfile);
      mockRequest.mockResolvedValueOnce(mockResponse);

      const result = await teamApi.clockOut();

      expect(mockRequest).toHaveBeenCalledWith('/api/team/clock-out', {
        method: 'POST',
        body: JSON.stringify({
          user_id: '123',
          email: 'test@example.com',
        }),
      });
      expect(result).toEqual(mockResponse);
    });

    it('should throw error if user profile not loaded', async () => {
      (mockClient.getUserProfile as any).mockReturnValue(null);

      await expect(teamApi.clockOut()).rejects.toThrow(
        'User profile not loaded. Please login again.'
      );
    });
  });

  describe('getClockStatus', () => {
    it('should return clock status successfully', async () => {
      const mockProfile = {
        id: '123',
        email: 'test@example.com',
      };
      const mockResponse: UserStatusResponse = {
        user_id: '123',
        is_online: true,
        last_action: '2024-01-01T08:00:00Z',
        last_action_type: 'clock_in',
        today_hours: 4.5,
        week_hours: 32.0,
        week_days: 4,
      };

      (mockClient.getUserProfile as any).mockReturnValue(mockProfile);
      mockRequest.mockResolvedValueOnce(mockResponse);

      const result = await teamApi.getClockStatus();

      expect(result).toEqual({
        is_clocked_in: true,
        today_hours: 4.5,
        week_hours: 32.0,
      });
    });

    it('should return default values if user profile not loaded', async () => {
      (mockClient.getUserProfile as any).mockReturnValue(null);

      const result = await teamApi.getClockStatus();

      expect(result).toEqual({
        is_clocked_in: false,
        today_hours: 0,
        week_hours: 0,
      });
    });

    it('should return default values on error', async () => {
      const mockProfile = {
        id: '123',
        email: 'test@example.com',
      };

      (mockClient.getUserProfile as any).mockReturnValue(mockProfile);
      mockRequest.mockRejectedValueOnce(new Error('Service unavailable'));

      const result = await teamApi.getClockStatus();

      expect(result).toEqual({
        is_clocked_in: false,
        today_hours: 0,
        week_hours: 0,
      });
    });
  });
});
