/**
 * Workspace Inbox API — omnichannel unified feed.
 */
import { api } from "@/lib/api";

export type InboxChannel = "whatsapp" | "telegram" | "instagram" | "web" | "email";
export type InboxDirection = "inbound" | "outbound";

export interface InboxItem {
  id: number;
  channel: string;
  direction: InboxDirection;
  content: string;
  created_at: string | null;
  client_id: number | null;
  client_name: string | null;
  client_email: string | null;
}

export interface InboxFeedResponse {
  items: InboxItem[];
  count: number;
}

export interface InboxStatsResponse {
  by_channel: Array<{ channel: string; count: number }>;
}

export interface InboxFilters {
  channel?: InboxChannel | "";
  direction?: InboxDirection;
  client_id?: number;
  limit?: number;
}

export const inboxApi = {
  async feed(filters: InboxFilters = {}): Promise<InboxFeedResponse> {
    const params = new URLSearchParams();
    if (filters.channel) params.set("channel", filters.channel);
    if (filters.direction) params.set("direction", filters.direction);
    if (filters.client_id != null) params.set("client_id", String(filters.client_id));
    if (filters.limit != null) params.set("limit", String(filters.limit));
    const qs = params.toString();
    return api.get<InboxFeedResponse>(`/api/workspace/inbox${qs ? `?${qs}` : ""}`);
  },

  async stats(): Promise<InboxStatsResponse> {
    return api.get<InboxStatsResponse>(`/api/workspace/inbox/stats`);
  },
};
