import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { NotificationsResponse } from "@/lib/api/portal/portal.types";

export function usePortalNotifications() {
  const queryClient = useQueryClient();

  const query = useQuery<NotificationsResponse>({
    queryKey: ["portal", "notifications"],
    queryFn: () => api.portal.getNotifications(50),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });

  const markRead = useMutation({
    mutationFn: (id: number) => api.portal.markNotificationRead(id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["portal", "notifications"] }),
  });

  const markAllRead = useMutation({
    mutationFn: () => api.portal.markAllNotificationsRead(),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["portal", "notifications"] }),
  });

  return {
    notifications: query.data?.notifications ?? [],
    unreadCount: query.data?.unread_count ?? 0,
    isLoading: query.isLoading,
    markRead: markRead.mutate,
    markAllRead: markAllRead.mutate,
  };
}
