import type { IApiClient } from '../types/api-client.types';
import type { SystemHealthReport, TableDataResponse, QdrantCollectionsResponse, QdrantPointsResponse } from './admin.types';

/**
 * Team member status
 */
interface TeamMemberStatus {
  user_id: string;
  email: string;
  is_online: boolean;
  last_action: string;
  last_action_type: string;
}

/**
 * Daily hours entry
 */
interface DailyHoursEntry {
  user_id: string;
  email: string;
  date: string;
  clock_in: string;
  clock_out: string;
  hours_worked: number;
}

/**
 * Weekly summary entry
 */
interface WeeklySummaryEntry {
  user_id: string;
  email: string;
  week_start: string;
  days_worked: number;
  total_hours: number;
  avg_hours_per_day: number;
}

/**
 * Monthly summary entry
 */
interface MonthlySummaryEntry {
  user_id: string;
  email: string;
  month_start: string;
  days_worked: number;
  total_hours: number;
  avg_hours_per_day: number;
}

/**
 * Admin-Only API methods (require admin role)
 */
export class AdminApi {
  constructor(private client: IApiClient) {}

  // Get current online status of all team members
  async getTeamStatus(): Promise<TeamMemberStatus[]> {
    return this.client.request<TeamMemberStatus[]>('/api/team/status', {
      headers: this.client.getAdminHeaders(),
    });
  }

  // Get work hours for a specific date
  async getDailyHours(date?: string): Promise<DailyHoursEntry[]> {
    const params = new URLSearchParams();
    if (date) params.append('date', date);

    return this.client.request<DailyHoursEntry[]>(`/api/team/hours?${params.toString()}`, {
      headers: this.client.getAdminHeaders(),
    });
  }

  // Get weekly work summary
  async getWeeklySummary(weekStart?: string): Promise<WeeklySummaryEntry[]> {
    const params = new URLSearchParams();
    if (weekStart) params.append('week_start', weekStart);

    return this.client.request<WeeklySummaryEntry[]>(`/api/team/activity/weekly?${params.toString()}`, {
      headers: this.client.getAdminHeaders(),
    });
  }

  // Get monthly work summary
  async getMonthlySummary(monthStart?: string): Promise<MonthlySummaryEntry[]> {
    const params = new URLSearchParams();
    if (monthStart) params.append('month_start', monthStart);

    return this.client.request<MonthlySummaryEntry[]>(`/api/team/activity/monthly?${params.toString()}`, {
      headers: this.client.getAdminHeaders(),
    });
  }

  // Export timesheet as CSV
  async exportTimesheet(startDate: string, endDate: string): Promise<Blob> {
    const headers = this.client.getAdminHeaders();
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
  async getSystemHealth(): Promise<SystemHealthReport> {
    return this.client.request<SystemHealthReport>('/api/admin/system-health', {
      headers: this.client.getAdminHeaders(),
    });
  }

  // ============================================================================
  // Data Explorer
  // ============================================================================

  async getPostgresTables(): Promise<string[]> {
    return this.client.request<string[]>('/api/admin/postgres/tables', {
      headers: this.client.getAdminHeaders(),
    });
  }

  async getTableData(table: string, limit = 50, offset = 0): Promise<TableDataResponse> {
    return this.client.request<TableDataResponse>(
      `/api/admin/postgres/data?table=${table}&limit=${limit}&offset=${offset}`,
      { headers: this.client.getAdminHeaders() }
    );
  }

  async getQdrantCollections(): Promise<QdrantCollectionsResponse> {
    return this.client.request<QdrantCollectionsResponse>('/api/admin/qdrant/collections', {
      headers: this.client.getAdminHeaders(),
    });
  }

  async getQdrantPoints(collection: string, limit = 20, offset?: string): Promise<QdrantPointsResponse> {
    let url = `/api/admin/qdrant/points?collection=${collection}&limit=${limit}`;
    if (offset) url += `&offset=${offset}`;

    return this.client.request<QdrantPointsResponse>(url, {
      headers: this.client.getAdminHeaders(),
    });
  }
}

