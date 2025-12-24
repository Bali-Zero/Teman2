import { ApiClientBase } from '../client';

/**
 * Admin-Only API methods (require admin role)
 */
export class AdminApi {
  constructor(private client: ApiClientBase) {}

  // Get current online status of all team members
  async getTeamStatus(): Promise<
    Array<{
      user_id: string;
      email: string;
      is_online: boolean;
      last_action: string;
      last_action_type: string;
    }>
  > {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (this.client as any).request('/api/team/status', {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      headers: (this.client as any).getAdminHeaders(),
    });
  }

  // Get work hours for a specific date
  async getDailyHours(date?: string): Promise<
    Array<{
      user_id: string;
      email: string;
      date: string;
      clock_in: string;
      clock_out: string;
      hours_worked: number;
    }>
  > {
    const params = new URLSearchParams();
    if (date) params.append('date', date);

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (this.client as any).request(`/api/team/hours?${params.toString()}`, {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      headers: (this.client as any).getAdminHeaders(),
    });
  }

  // Get weekly work summary
  async getWeeklySummary(weekStart?: string): Promise<
    Array<{
      user_id: string;
      email: string;
      week_start: string;
      days_worked: number;
      total_hours: number;
      avg_hours_per_day: number;
    }>
  > {
    const params = new URLSearchParams();
    if (weekStart) params.append('week_start', weekStart);

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (this.client as any).request(`/api/team/activity/weekly?${params.toString()}`, {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      headers: (this.client as any).getAdminHeaders(),
    });
  }

  // Get monthly work summary
  async getMonthlySummary(monthStart?: string): Promise<
    Array<{
      user_id: string;
      email: string;
      month_start: string;
      days_worked: number;
      total_hours: number;
      avg_hours_per_day: number;
    }>
  > {
    const params = new URLSearchParams();
    if (monthStart) params.append('month_start', monthStart);

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (this.client as any).request(`/api/team/activity/monthly?${params.toString()}`, {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      headers: (this.client as any).getAdminHeaders(),
    });
  }

  // Export timesheet as CSV
  async exportTimesheet(startDate: string, endDate: string): Promise<Blob> {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const headers = (this.client as any).getAdminHeaders();
    const baseUrl = this.client.getBaseUrl();

    // Keep Authorization header for backward compatibility
    const token = this.client.getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(
      `${baseUrl}/api/team/export?start_date=${startDate}&end_date=${endDate}&format=csv`,
      {
        headers,
        credentials: 'include', // Send httpOnly cookies
      }
    );

    if (!response.ok) {
      throw new Error('Failed to export timesheet');
    }

    return response.blob();
  }

  // Get system health report
  async getSystemHealth(): Promise<import('./admin.types').SystemHealthReport> {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (this.client as any).request('/api/admin/system-health', {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      headers: (this.client as any).getAdminHeaders(),
    });
  }

  // ============================================================================
  // Data Explorer
  // ============================================================================

  async getPostgresTables(): Promise<string[]> {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (this.client as any).request('/api/admin/postgres/tables', {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      headers: (this.client as any).getAdminHeaders(),
    });
  }

  async getTableData(table: string, limit = 50, offset = 0): Promise<import('./admin.types').TableDataResponse> {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (this.client as any).request(`/api/admin/postgres/data?table=${table}&limit=${limit}&offset=${offset}`, {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      headers: (this.client as any).getAdminHeaders(),
    });
  }

  async getQdrantCollections(): Promise<import('./admin.types').QdrantCollectionsResponse> {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (this.client as any).request('/api/admin/qdrant/collections', {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      headers: (this.client as any).getAdminHeaders(),
    });
  }

  async getQdrantPoints(collection: string, limit = 20, offset?: string): Promise<import('./admin.types').QdrantPointsResponse> {
    let url = `/api/admin/qdrant/points?collection=${collection}&limit=${limit}`;
    if (offset) url += `&offset=${offset}`;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (this.client as any).request(url, {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      headers: (this.client as any).getAdminHeaders(),
    });
  }
}

