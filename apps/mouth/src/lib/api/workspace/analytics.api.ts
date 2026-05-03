/**
 * Workspace Analytics API — funnel attribution dashboard.
 */
import { api } from "@/lib/api";

export interface FunnelBucket {
  funnel: string;
  count: number;
}

export interface FunnelViewResponse {
  sessions: FunnelBucket[];
  conversions: FunnelBucket[];
}

export const analyticsApi = {
  async funnelView(): Promise<FunnelViewResponse> {
    return api.get<FunnelViewResponse>(`/api/workspace/analytics/funnel`);
  },
};
