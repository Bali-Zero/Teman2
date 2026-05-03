/**
 * useCrmNotifications Hook
 *
 * Hook per notifiche e alert del CRM:
 * - Documenti in scadenza
 * - Pratiche da completare
 * - Passaporti in scadenza
 * - Nuovi clienti
 */

import { useCallback, useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  ExpiryAlert,
  Practice,
  RenewalAlert,
  Interaction,
} from "@/lib/api/crm/crm.types";

interface Notification {
  id: string;
  type: "expiry" | "overdue" | "new_client" | "status_change" | "portal_upload";
  title: string;
  message: string;
  severity: "low" | "medium" | "high" | "critical";
  createdAt: string;
  read: boolean;
  actionUrl?: string;
  metadata?: Record<string, any>;
}

interface CrmAlert {
  id: number;
  client_id: number;
  alert_type: string;
  status: string;
  message: string | null;
  email_subject: string | null;
  created_at: string;
  sent_at: string | null;
}

interface UseCrmNotificationsOptions {
  unreadOnly?: boolean;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

const NOTIFICATION_ICONS = {
  expiry: "Calendar",
  overdue: "AlertTriangle",
  new_client: "UserPlus",
  status_change: "RefreshCw",
  portal_upload: "Upload",
} as const;

const NOTIFICATION_COLORS = {
  low: "blue",
  medium: "yellow",
  high: "orange",
  critical: "red",
} as const;

/**
 * Hook per expiry alerts come notifiche
 */
export function useCrmNotifications(options: UseCrmNotificationsOptions = {}) {
  const {
    unreadOnly = false,
    autoRefresh = true,
    refreshInterval = 5 * 60 * 1000, // 5 minutes
  } = options;

  const queryClient = useQueryClient();
  const [unreadCount, setUnreadCount] = useState(0);

  // Use expiry alerts + portal upload alerts as notifications
  const query = useQuery({
    queryKey: ["crm", "notifications", "all", { unreadOnly }],
    queryFn: async (): Promise<Notification[]> => {
      const [alerts, portalAlerts] = await Promise.all([
        api.crm.getExpiryAlerts({ limit: 50 }),
        api.crm
          .request<CrmAlert[]>("/api/crm/notifications?limit=20")
          .catch(() => [] as CrmAlert[]),
      ]);

      // Map expiry alerts to notifications
      const expiryNotifs: Notification[] = alerts.map(
        (alert: ExpiryAlert): Notification => ({
          id: `expiry-${alert.entity_id}-${alert.document_type}`,
          type: "expiry",
          title: `${alert.entity_name} - ${alert.document_type}`,
          message:
            alert.days_until_expiry <= 0
              ? `Expired on ${alert.expiry_date}`
              : `Expires in ${alert.days_until_expiry} days`,
          severity:
            alert.alert_color === "expired"
              ? "critical"
              : alert.alert_color === "red"
                ? "high"
                : alert.alert_color === "yellow"
                  ? "medium"
                  : "low",
          createdAt: new Date().toISOString(),
          read: false,
          actionUrl: `/clients/${alert.client_id}`,
          metadata: {
            clientId: alert.client_id,
            entityId: alert.entity_id,
            daysUntilExpiry: alert.days_until_expiry,
          },
        }),
      );

      // Map portal upload alerts to notifications
      const portalNotifs: Notification[] = (portalAlerts || []).map(
        (alert: CrmAlert): Notification => ({
          id: `portal-${alert.id}`,
          type: "portal_upload",
          title: (alert as any).client_name
            ? `${(alert as any).client_name} uploaded a document`
            : "Portal Document Upload",
          message: alert.message || "Client uploaded a document via portal",
          severity: "medium",
          createdAt: alert.created_at,
          read: alert.status !== "pending",
          actionUrl: `/clients/${alert.client_id}`,
          metadata: { clientId: alert.client_id },
        }),
      );

      // Merge and sort by date (newest first)
      return [...expiryNotifs, ...portalNotifs].sort(
        (a, b) =>
          new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
      );
    },
    refetchInterval: autoRefresh ? refreshInterval : false,
    staleTime: 60 * 1000, // 1 minute
  });

  // Update unread count
  useEffect(() => {
    if (query.data) {
      setUnreadCount(query.data.filter((n) => !n.read).length);
    }
  }, [query.data]);

  // Mark as read (mock - just removes from count)
  const markAsRead = useCallback((notificationId: string) => {
    setUnreadCount((prev) => Math.max(0, prev - 1));
  }, []);

  // Mark all as read
  const markAllAsRead = useCallback(() => {
    setUnreadCount(0);
  }, []);

  return {
    notifications: query.data || [],
    unreadCount,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    markAsRead,
    markAllAsRead,
  };
}

/**
 * Hook per alert scadenze
 */
export function useExpiryAlerts(params?: {
  alertColor?: "expired" | "red" | "yellow";
  assignedTo?: string;
  limit?: number;
}) {
  return useQuery({
    queryKey: ["crm", "alerts", "expiry", params],
    queryFn: async (): Promise<ExpiryAlert[]> => {
      return api.crm.getExpiryAlerts(params);
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Hook per expiry alerts summary
 */
export function useExpiryAlertsSummary() {
  return useQuery({
    queryKey: ["crm", "alerts", "expiry-summary"],
    queryFn: async () => {
      return api.crm.getExpiryAlertsSummary();
    },
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Hook per pratiche in scadenza
 */
export function useUpcomingRenewals(days: number = 90) {
  return useQuery({
    queryKey: ["crm", "alerts", "renewals", days],
    queryFn: async (): Promise<Practice[]> => {
      const renewals = await api.crm.getUpcomingRenewals(days);
      // Map renewals to practices (they share many fields)
      return renewals.map(
        (r: RenewalAlert) =>
          ({
            id: r.practice_id, // Use practice_id, not alert id
            client_id: r.client_id,
            status: r.status,
            expiry_date: r.target_date,
            practice_type_code: r.alert_type,
            created_at: r.alert_date,
            updated_at: r.alert_date,
            priority: "high",
            payment_status: "pending",
          }) as Practice,
      );
    },
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Hook per dashboard stats
 */
export function useDashboardStats() {
  return useQuery({
    queryKey: ["crm", "dashboard"],
    queryFn: async () => {
      const [practiceStats, revenueGrowth, expirySummary] = await Promise.all([
        api.crm.getPracticeStats(),
        api.crm.getRevenueGrowth(),
        api.crm.getExpiryAlertsSummary(),
      ]);

      return {
        totalClients: practiceStats.total_practices,
        newThisMonth: 0, // Not available in current API
        activePractices: practiceStats.active_practices,
        overduePractices: 0, // Not available in current API
        expiryAlerts:
          expirySummary.counts.red +
          expirySummary.counts.yellow +
          expirySummary.counts.expired,
        revenue: {
          total: practiceStats.revenue.total_revenue,
          paid: practiceStats.revenue.paid_revenue,
          outstanding: practiceStats.revenue.outstanding_revenue,
        },
        byStatus: practiceStats.by_status,
        recentActivity: [], // Not available in current API
        revenueGrowth,
        expirySummary,
      };
    },
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}

/**
 * Hook per attività recenti (usando interactions)
 */
export function useRecentActivity(limit: number = 10) {
  return useQuery({
    queryKey: ["crm", "activity", limit],
    queryFn: async () => {
      const interactions = await api.crm.getInteractions({ limit });

      return interactions.map((interaction: Interaction) => ({
        id: `interaction-${interaction.id}`,
        type:
          interaction.interaction_type === "chat"
            ? "note_added"
            : interaction.interaction_type === "email"
              ? "document_uploaded"
              : "status_changed",
        description:
          interaction.summary ||
          interaction.subject ||
          `${interaction.interaction_type} interaction`,
        user: interaction.team_member,
        timestamp: interaction.created_at,
        clientId: interaction.client_id,
        practiceId: interaction.practice_id,
      }));
    },
    staleTime: 60 * 1000,
  });
}

/**
 * Hook per notifiche browser (push notifications)
 */
export function useBrowserNotifications() {
  const [permission, setPermission] =
    useState<NotificationPermission>("default");
  const [supported, setSupported] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined" && "Notification" in window) {
      setSupported(true);
      setPermission(Notification.permission);
    }
  }, []);

  const requestPermission = useCallback(async () => {
    if (!supported) return false;

    const result = await Notification.requestPermission();
    setPermission(result);
    return result === "granted";
  }, [supported]);

  const showNotification = useCallback(
    (title: string, options?: NotificationOptions) => {
      if (supported && permission === "granted") {
        return new Notification(title, {
          icon: "/favicon.ico",
          badge: "/favicon.ico",
          ...options,
        });
      }
      return null;
    },
    [supported, permission],
  );

  return {
    supported,
    permission,
    requestPermission,
    showNotification,
    isGranted: permission === "granted",
    isDenied: permission === "denied",
  };
}

export type { Notification };
export { NOTIFICATION_ICONS, NOTIFICATION_COLORS };
