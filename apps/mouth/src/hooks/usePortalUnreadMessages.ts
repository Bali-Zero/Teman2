"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export const portalUnreadKey = ["portal", "unread-messages"] as const;
export const teamPortalUnreadKey = ["crm", "portal-unread-messages"] as const;

const freshness = {
  refetchInterval: 30_000,
  refetchIntervalInBackground: false,
  refetchOnWindowFocus: "always" as const,
  refetchOnMount: true,
  staleTime: 15_000,
  gcTime: 0,
  retry: false,
};

export function usePortalUnreadMessages(enabled = true) {
  return useQuery({
    queryKey: [
      ...portalUnreadKey,
      api.getUserProfile()?.id ?? "cookie-session",
      api.getPortalImpersonation(),
    ],
    // The server's unreadCount covers the entire thread, not this one-row page.
    queryFn: async () => (await api.portal.getMessages(1, 0)).unreadCount,
    enabled,
    ...freshness,
  });
}

export function useTeamPortalUnreadMessages() {
  return useQuery({
    queryKey: [
      ...teamPortalUnreadKey,
      api.getUserProfile()?.id ?? "cookie-session",
    ],
    queryFn: () => api.crm.getPortalUnreadCount(),
    ...freshness,
  });
}
