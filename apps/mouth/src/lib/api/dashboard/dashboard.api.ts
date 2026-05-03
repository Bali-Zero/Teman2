/**
 * Dashboard API client for the new aggregated endpoint
 */

import { api } from "@/lib/api";
import type { TimelineResponse } from "@/lib/api/types/timeline.types";

export interface DashboardStats {
  activeCases: number;
  criticalDeadlines: number;
  pendingInvoices: number;
  whatsappUnread: number;
  emailUnread: number;
  hoursWorked: string;
}

export interface DashboardUser {
  email: string;
  role: string;
  is_admin: boolean;
}

export interface DashboardData {
  user: DashboardUser;
  stats: DashboardStats;
  data: {
    practices: Array<{
      id: number;
      title: string;
      client: string;
      status:
        | "inquiry"
        | "completed"
        | "in_progress"
        | "quotation"
        | "documents";
      daysRemaining?: number;
    }>;
    interactions: Array<{
      id: string;
      contactName: string;
      message: string;
      timestamp: string;
      isRead: boolean;
      hasAiSuggestion: boolean;
      practiceId?: number;
    }>;
    email: {
      connected: boolean;
      unread_count: number;
    };
  };
  system_status: "healthy" | "degraded";
  last_updated: number;
  // Admin-only fields
  revenue?: {
    total_revenue: number;
    paid_revenue: number;
    outstanding_revenue: number;
  };
  revenue_growth?: number;
  total_clients?: number;
  total_practices?: number;
}

export const dashboardApi = {
  /**
   * Get aggregated dashboard data in a single call
   */
  async getDashboardSummary(): Promise<DashboardData> {
    return api.request<DashboardData>("/api/dashboard/summary");
  },

  async getTimeline(limit: number = 50): Promise<TimelineResponse> {
    return api.request<TimelineResponse>(
      `/api/dashboard/timeline?limit=${limit}`,
    );
  },
};
