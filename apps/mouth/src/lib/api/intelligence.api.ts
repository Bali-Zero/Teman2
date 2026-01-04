import { api } from "@/lib/api";

export interface StagingItem {
  id: string;
  type: "visa" | "news";
  title: string;
  status: "pending" | "approved" | "rejected";
  detected_at: string;
  source: string;
  detection_type: "NEW" | "UPDATED";
  content?: string;
}

export const intelligenceApi = {
  getPendingItems: async (type: "all" | "visa" | "news" = "all") => {
    return api.request<{ items: StagingItem[]; count: number }>(
      `/api/intel/staging/pending?type=${type}`
    );
  },

  getPreview: async (type: "visa" | "news", id: string) => {
    return api.request<StagingItem>(`/api/intel/staging/preview/${type}/${id}`);
  },

  approveItem: async (type: "visa" | "news", id: string) => {
    return api.request<{ success: boolean; id: string }>(
      `/api/intel/staging/approve/${type}/${id}`,
      { method: "POST" }
    );
  },

  rejectItem: async (type: "visa" | "news", id: string) => {
    return api.request<{ success: boolean; id: string }>(
      `/api/intel/staging/reject/${type}/${id}`,
      { method: "POST" }
    );
  },
};