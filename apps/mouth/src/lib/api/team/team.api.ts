import type { IApiClient } from '../types/api-client.types';
import type { ClockResponse, UserStatusResponse } from './team.types';

/**
 * Team Activity API methods
 */
export class TeamApi {
  constructor(private client: IApiClient) {}

  async clockIn(): Promise<ClockResponse> {
    const userProfile = this.client.getUserProfile();
    if (!userProfile) {
      throw new Error('User profile not loaded. Please login again.');
    }

    return this.client.request<ClockResponse>('/api/team/clock-in', {
      method: 'POST',
      body: JSON.stringify({
        user_id: userProfile.id,
        email: userProfile.email,
      }),
    });
  }

  async clockOut(): Promise<ClockResponse> {
    const userProfile = this.client.getUserProfile();
    if (!userProfile) {
      throw new Error('User profile not loaded. Please login again.');
    }

    return this.client.request<ClockResponse>('/api/team/clock-out', {
      method: 'POST',
      body: JSON.stringify({
        user_id: userProfile.id,
        email: userProfile.email,
      }),
    });
  }

  async getClockStatus(): Promise<{
    is_clocked_in: boolean;
    today_hours: number;
    week_hours: number;
  }> {
    const userProfile = this.client.getUserProfile();
    if (!userProfile) {
      return { is_clocked_in: false, today_hours: 0, week_hours: 0 };
    }

    try {
      const response = await this.client.request<UserStatusResponse>(
        `/api/team/my-status?user_id=${encodeURIComponent(userProfile.id)}`
      );

      return {
        is_clocked_in: response.is_online,
        today_hours: response.today_hours,
        week_hours: response.week_hours,
      };
    } catch {
      // Service might be unavailable
      return { is_clocked_in: false, today_hours: 0, week_hours: 0 };
    }
  }
}

