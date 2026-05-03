import type { IApiClient } from "../types/api-client.types";
import type {
  SystemHealthReport,
  TableDataResponse,
  QdrantCollectionsResponse,
  QdrantPointsResponse,
} from "./admin.types";

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
    return this.client.request<TeamMemberStatus[]>("/api/team/status", {
      headers: this.client.getAdminHeaders(),
    });
  }

  // Get work hours for a specific date
  async getDailyHours(date?: string): Promise<DailyHoursEntry[]> {
    const params = new URLSearchParams();
    if (date) params.append("date", date);

    return this.client.request<DailyHoursEntry[]>(
      `/api/team/hours?${params.toString()}`,
      {
        headers: this.client.getAdminHeaders(),
      },
    );
  }

  // Get weekly work summary
  async getWeeklySummary(weekStart?: string): Promise<WeeklySummaryEntry[]> {
    const params = new URLSearchParams();
    if (weekStart) params.append("week_start", weekStart);

    return this.client.request<WeeklySummaryEntry[]>(
      `/api/team/activity/weekly?${params.toString()}`,
      {
        headers: this.client.getAdminHeaders(),
      },
    );
  }

  // Get monthly work summary
  async getMonthlySummary(monthStart?: string): Promise<MonthlySummaryEntry[]> {
    const params = new URLSearchParams();
    if (monthStart) params.append("month_start", monthStart);

    return this.client.request<MonthlySummaryEntry[]>(
      `/api/team/activity/monthly?${params.toString()}`,
      {
        headers: this.client.getAdminHeaders(),
      },
    );
  }

  // Export timesheet as CSV
  async exportTimesheet(startDate: string, endDate: string): Promise<Blob> {
    const headers = this.client.getAdminHeaders();
    const baseUrl = this.client.getBaseUrl();

    // Keep Authorization header for backward compatibility
    const token = this.client.getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(
      `${baseUrl}/api/team/export?start_date=${startDate}&end_date=${endDate}&format=csv`,
      {
        headers,
        credentials: "include", // Send httpOnly cookies
      },
    );

    if (!response.ok) {
      throw new Error("Failed to export timesheet");
    }

    return response.blob();
  }

  // Get system health report
  async getSystemHealth(): Promise<SystemHealthReport> {
    return this.client.request<SystemHealthReport>("/api/admin/system-health", {
      headers: this.client.getAdminHeaders(),
    });
  }

  // ============================================================================
  // Data Explorer
  // ============================================================================

  async getPostgresTables(): Promise<string[]> {
    return this.client.request<string[]>("/api/admin/postgres/tables", {
      headers: this.client.getAdminHeaders(),
    });
  }

  async getTableData(
    table: string,
    limit = 50,
    offset = 0,
  ): Promise<TableDataResponse> {
    return this.client.request<TableDataResponse>(
      `/api/admin/postgres/data?table=${table}&limit=${limit}&offset=${offset}`,
      { headers: this.client.getAdminHeaders() },
    );
  }

  async getQdrantCollections(): Promise<QdrantCollectionsResponse> {
    return this.client.request<QdrantCollectionsResponse>(
      "/api/admin/qdrant/collections",
      {
        headers: this.client.getAdminHeaders(),
      },
    );
  }

  async getQdrantPoints(
    collection: string,
    limit = 20,
    offset?: string,
  ): Promise<QdrantPointsResponse> {
    let url = `/api/admin/qdrant/points?collection=${collection}&limit=${limit}`;
    if (offset) url += `&offset=${offset}`;

    return this.client.request<QdrantPointsResponse>(url, {
      headers: this.client.getAdminHeaders(),
    });
  }

  // ============================================================================
  // Team Activity Dashboard
  // ============================================================================

  async getTeamActivityOverview(
    startDate?: string,
  ): Promise<TeamActivityOverview> {
    const url = startDate
      ? `/api/admin/team-activity/overview?start_date=${startDate}`
      : "/api/admin/team-activity/overview";
    return this.client.request<TeamActivityOverview>(url, {
      headers: this.client.getAdminHeaders(),
    });
  }

  async getTeamActivityMessages(params: {
    user_id?: string;
    role?: string;
    search?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<MessagesResponse> {
    const searchParams = new URLSearchParams();
    if (params.user_id) searchParams.append("user_id", params.user_id);
    if (params.role) searchParams.append("role", params.role);
    if (params.search) searchParams.append("search", params.search);
    if (params.date_from) searchParams.append("date_from", params.date_from);
    if (params.date_to) searchParams.append("date_to", params.date_to);
    if (params.limit) searchParams.append("limit", params.limit.toString());
    if (params.offset) searchParams.append("offset", params.offset.toString());

    return this.client.request<MessagesResponse>(
      `/api/admin/team-activity/messages?${searchParams.toString()}`,
      { headers: this.client.getAdminHeaders() },
    );
  }

  async getTeamStats(
    days = 30,
    startDate?: string,
  ): Promise<TeamStatsResponse> {
    const url = startDate
      ? `/api/admin/team-activity/team-stats?start_date=${startDate}`
      : `/api/admin/team-activity/team-stats?days=${days}`;
    return this.client.request<TeamStatsResponse>(url, {
      headers: this.client.getAdminHeaders(),
    });
  }

  async getTeamTimesheet(params: {
    email?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<TimesheetResponse> {
    const searchParams = new URLSearchParams();
    if (params.email) searchParams.append("email", params.email);
    if (params.date_from) searchParams.append("date_from", params.date_from);
    if (params.date_to) searchParams.append("date_to", params.date_to);
    if (params.limit) searchParams.append("limit", params.limit.toString());
    if (params.offset) searchParams.append("offset", params.offset.toString());

    return this.client.request<TimesheetResponse>(
      `/api/admin/team-activity/timesheet?${searchParams.toString()}`,
      { headers: this.client.getAdminHeaders() },
    );
  }

  async getPracticeStats(): Promise<PracticeStatsResponse> {
    return this.client.request<PracticeStatsResponse>(
      "/api/admin/team-activity/practice-stats",
      { headers: this.client.getAdminHeaders() },
    );
  }

  async getCrmActions(params: {
    email?: string;
    action?: string;
    entity_type?: string;
    limit?: number;
    offset?: number;
  }): Promise<CrmActionsResponse> {
    const searchParams = new URLSearchParams();
    if (params.email) searchParams.append("email", params.email);
    if (params.action) searchParams.append("action", params.action);
    if (params.entity_type)
      searchParams.append("entity_type", params.entity_type);
    if (params.limit) searchParams.append("limit", params.limit.toString());
    if (params.offset) searchParams.append("offset", params.offset.toString());

    return this.client.request<CrmActionsResponse>(
      `/api/admin/team-activity/crm-actions?${searchParams.toString()}`,
      { headers: this.client.getAdminHeaders() },
    );
  }

  async exportMessages(params: {
    user_id?: string;
    date_from?: string;
    date_to?: string;
  }): Promise<Blob> {
    const searchParams = new URLSearchParams();
    if (params.user_id) searchParams.append("user_id", params.user_id);
    if (params.date_from) searchParams.append("date_from", params.date_from);
    if (params.date_to) searchParams.append("date_to", params.date_to);

    const headers = this.client.getAdminHeaders();
    const baseUrl = this.client.getBaseUrl();
    const token = this.client.getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(
      `${baseUrl}/api/admin/team-activity/export/messages?${searchParams.toString()}`,
      { headers, credentials: "include" },
    );

    if (!response.ok) {
      throw new Error("Failed to export messages");
    }

    return response.blob();
  }
}

// ============================================================================
// Types for Team Activity
// ============================================================================

interface TeamActivityOverview {
  success: boolean;
  stats: {
    total_conversations: number;
    total_messages: number;
    total_team_members: number;
    active_today: number;
    messages_today: number;
  };
  top_users: Array<{ user_id: string; msg_count: number }>;
}

interface MessageItem {
  conversation_id: number;
  user_id: string | null;
  role: string | null;
  content: string | null;
  message_timestamp: string | null;
  content_length: number | null;
  conversation_started: string;
}

interface MessagesResponse {
  success: boolean;
  total: number;
  limit: number;
  offset: number;
  messages: MessageItem[];
}

interface TeamMemberStat {
  email: string;
  name: string | null;
  role: string | null;
  department: string | null;
  conversations: number;
  messages: number;
  days_worked: number;
  crm_actions: number;
  emails_sent: number;
  emails_received: number;
  kb_views: number;
  kb_downloads: number;
  last_activity: string | null;
}

interface TeamStatsResponse {
  success: boolean;
  period_days: number;
  team_stats: TeamMemberStat[];
}

interface TimesheetRecord {
  id: number;
  email: string;
  action_type: string;
  timestamp: string;
  notes: string | null;
}

interface TimesheetResponse {
  success: boolean;
  total: number;
  limit: number;
  offset: number;
  records: TimesheetRecord[];
}

interface CrmAction {
  id: number;
  performed_by: string;
  action: string;
  entity_type: string;
  entity_id: number;
  description: string | null;
  performed_at: string;
}

interface CrmActionsResponse {
  success: boolean;
  total: number;
  limit: number;
  offset: number;
  actions: CrmAction[];
}

interface PracticeStatItem {
  email: string;
  completed: number;
  active: number;
  revenue: number;
}

interface PracticeStatsResponse {
  success: boolean;
  practice_stats: PracticeStatItem[];
}
