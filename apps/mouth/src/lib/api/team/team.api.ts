import { ApiClientBase } from '../client';
import type { ClockResponse, UserStatusResponse } from './team.types';

/**
 * Team Activity API methods
 */
export class TeamApi {
  constructor(private client: ApiClientBase) {}

  async clockIn(): Promise<ClockResponse> {
    const userProfile = this.client.getUserProfile();
    if (!userProfile) {
      throw new Error('User profile not loaded. Please login again.');
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (this.client as any).request('/api/team/clock-in', {
      method: 'POST',
      body: JSON.stringify({
        user_id: userProfile.id,
        email: userProfile.email,
      }),
    }) as Promise<ClockResponse>;
  }

  async clockOut(): Promise<ClockResponse> {
    const userProfile = this.client.getUserProfile();
    if (!userProfile) {
      throw new Error('User profile not loaded. Please login again.');
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (this.client as any).request('/api/team/clock-out', {
      method: 'POST',
      body: JSON.stringify({
        user_id: userProfile.id,
        email: userProfile.email,
      }),
    }) as Promise<ClockResponse>;
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
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const response = await (this.client as any).request(
        `/api/team/my-status?user_id=${encodeURIComponent(userProfile.id)}`
      ) as UserStatusResponse;

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

