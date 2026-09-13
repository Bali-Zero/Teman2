/**
 * Dashboard API client for the new aggregated endpoint
 */

import { api } from "@/lib/api";

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
        "inquiry" | "completed" | "in_progress" | "quotation" | "documents";
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

// ── Portal Champion challenge (14–29 Sept 2026, WITA) ──────
// Hand-typed against the backend contract until /api/dashboard/portal-challenge
// ships schema.d.ts types — GET /api/dashboard/portal-challenge is being built
// in parallel and is not deployed yet, so this widget must degrade quietly
// (see usePortalChallenge.ts) rather than assume the shape below is final.
export type PortalChallengeStatus = "upcoming" | "live" | "closed";
export type PortalChallengeAwardTier = 1 | 2 | 3;

export interface PortalChallengeTier {
  tier: PortalChallengeAwardTier;
  threshold: number;
  prize_idr: number;
}

export interface PortalChallengeTaxRules {
  podium_super_bonus_idr: number;
  best_tax_fallback_idr: number;
  best_tax_fallback_threshold: number;
}

export interface PortalChallengeEntry {
  member: string;
  display_name: string;
  department: string | null;
  is_tax: boolean;
  is_me: boolean;
  rank: number;
  activations: number;
  invited: number;
  last_activation_at: string | null;
  award_tier: PortalChallengeAwardTier | null;
  prize_idr: number;
  tax_bonus_idr: number;
  total_prize_idr: number;
  next_tier_threshold: number | null;
  to_next_tier: number | null;
}

export interface PortalChallengeRecentActivation {
  display_name: string;
  at: string;
}

export interface PortalChallengeResponse {
  status: PortalChallengeStatus;
  window_start: string;
  window_end: string;
  timezone: "Asia/Makassar";
  generated_at: string;
  tiers: PortalChallengeTier[];
  tax_rules: PortalChallengeTaxRules;
  team_total_activations: number;
  entries: PortalChallengeEntry[];
  recent_activations: PortalChallengeRecentActivation[];
}

export const dashboardApi = {
  /**
   * Get aggregated dashboard data in a single call
   */
  async getDashboardSummary(): Promise<DashboardData> {
    return api.request<DashboardData>("/api/dashboard/summary");
  },

  /**
   * Live standing for the "Portal Champion" client-activation challenge.
   * Throws (ApiError, 404 while the backend isn't deployed yet) — the caller
   * hook is responsible for turning that into a quiet placeholder.
   */
  async getPortalChallenge(): Promise<PortalChallengeResponse> {
    return api.request<PortalChallengeResponse>(
      "/api/dashboard/portal-challenge",
    );
  },
};
