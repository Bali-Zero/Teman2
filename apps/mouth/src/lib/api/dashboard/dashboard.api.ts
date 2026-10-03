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
// Round 2 «Lascia o raddoppia» (Sep 30 – Oct 30 2026 WITA) — see
// scratchpad/portal-champion-round2-spec.md §4 for the payload contract.
export type PortalChallengeRound = 1 | 2;
export type PortalChallengeSeptemberChoice = "carry" | "prize";
export type PortalChallengeEventKind =
  | "registration"
  | "first_document"
  | "unanswered_request"
  | "unreviewed_document"
  | "asya_bonus";

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

export interface PortalChallengeRankPrize {
  rank: number;
  prize_idr: number;
  /** Minimum score for this slot; absent on payloads older than the 2026-09-30 ruling. */
  min_points?: number;
}

export interface PortalChallengeScoringRules {
  registration: number;
  first_document: number;
  unanswered_request: number;
  unreviewed_document: number;
  response_working_hours: number;
  review_working_hours: number;
  service_hours: string;
}

export interface PortalChallengeEntry {
  member: string;
  display_name: string;
  avatar_url?: string | null;
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
  // Round 2 only — optional so a round-1 payload (or an older cached one)
  // still satisfies this type. Zero/null in round 1.
  points?: number;
  carry_points?: number;
  registrations?: number;
  document_bonuses?: number;
  unanswered_requests?: number;
  unreviewed_documents?: number;
  penalty_points?: number;
  september_choice?: PortalChallengeSeptemberChoice | null;
  last_event_at?: string | null;
  /** Prize slot actually won after slide-down; null = no prize. */
  prize_slot?: number | null;
  /** September rank of a prize-taker; null for everyone else. */
  september_rank?: number | null;
  /** Tied on a prize slot: no prize until the play-off decides it. */
  playoff_pending?: boolean;
}

export interface PortalChallengeRecentActivation {
  display_name: string;
  at: string;
}

export interface PortalChallengeRecentEvent {
  kind: PortalChallengeEventKind;
  display_name: string;
  points: number;
  at: string;
}

export interface PortalChallengeSeptemberEntry {
  member: string;
  display_name: string;
  avatar_url?: string | null;
  is_tax: boolean;
  rank: number;
  activations: number;
  invited: number;
  award_tier: PortalChallengeAwardTier | null;
  prize_idr: number;
  tax_bonus_idr: number;
  total_prize_idr: number;
  september_choice: PortalChallengeSeptemberChoice | null;
}

export interface PortalChallengeSeptemberSummary {
  status: PortalChallengeStatus;
  window_start: string;
  window_end: string;
  team_total_activations: number;
  entries: PortalChallengeSeptemberEntry[];
}

export interface PortalChallengeAsyaMission {
  member: string;
  display_name: string;
  avatar_url?: string | null;
  target_points: number;
  prize_idr: number;
  bonus_points: number;
  mission_bonuses: number;
  unanswered_requests: number;
  unreviewed_documents: number;
  penalty_points: number;
  points: number;
  reached: boolean;
  is_me: boolean;
}

export interface PortalChallengeResponse {
  status: PortalChallengeStatus;
  round?: PortalChallengeRound;
  campaign?: string | null;
  window_start: string;
  window_end: string;
  timezone: "Asia/Makassar";
  generated_at: string;
  tiers: PortalChallengeTier[];
  tax_rules: PortalChallengeTaxRules;
  rank_prizes?: PortalChallengeRankPrize[];
  scoring?: PortalChallengeScoringRules | null;
  team_total_activations: number;
  team_total_points?: number;
  entries: PortalChallengeEntry[];
  recent_activations: PortalChallengeRecentActivation[];
  recent_events?: PortalChallengeRecentEvent[];
  september?: PortalChallengeSeptemberSummary | null;
  asya_mission?: PortalChallengeAsyaMission | null;
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
      "/api/dashboard/portal-challenge?fresh=true",
    );
  },
};
