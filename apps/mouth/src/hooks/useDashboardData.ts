/**
 * Custom hook for dashboard data management
 * Replaces 7 separate API calls with 1 optimized call using React Query
 */

import { useQuery } from "@tanstack/react-query";
import {
  dashboardApi,
  type DashboardData,
} from "@/lib/api/dashboard/dashboard.api";
import { logger } from "@/lib/logger";

export function useDashboardData() {
  const {
    data,
    isLoading: loading,
    error,
    refetch,
  } = useQuery<DashboardData>({
    queryKey: ["dashboard"],
    queryFn: async () => {
      try {
        const result = await dashboardApi.getDashboardSummary();
        return result;
      } catch (err) {
        // Detailed error logging for debugging
        const errorDetails = {
          message: err instanceof Error ? err.message : String(err),
          name: err instanceof Error ? err.name : "UnknownError",
          stack: err instanceof Error ? (err.stack ?? "") : "",
          timestamp: new Date().toISOString(),
          endpoint: "/api/dashboard/summary",
        };

        // Log error with structured logger
        logger.error(
          "Failed to load dashboard data",
          {
            component: "useDashboardData",
            action: "getDashboardSummary",
            metadata: errorDetails,
          },
          err instanceof Error ? err : new Error(String(err)),
        );

        // Check for specific error types
        if (err instanceof Error) {
          if (
            err.message.includes("401") ||
            err.message.includes("Unauthorized")
          ) {
            logger.warn("Authentication error - user may need to login again", {
              component: "useDashboardData",
              action: "getDashboardSummary",
            });
          } else if (
            err.message.includes("403") ||
            err.message.includes("Forbidden")
          ) {
            logger.warn("Authorization error - user may not have permission", {
              component: "useDashboardData",
              action: "getDashboardSummary",
            });
          } else if (
            err.message.includes("Network") ||
            err.message.includes("fetch")
          ) {
            logger.warn("Network error - backend may be unreachable", {
              component: "useDashboardData",
              action: "getDashboardSummary",
            });
          } else if (err.message.includes("CORS")) {
            logger.warn(
              "CORS error - backend CORS configuration may be incorrect",
              {
                component: "useDashboardData",
                action: "getDashboardSummary",
              },
            );
          }
        }

        // Re-throw to let React Query handle it
        throw err;
      }
    },
    staleTime: 30_000, // Cache for 30 seconds
    refetchInterval: 60_000, // Auto-refresh every minute
    retry: 2, // Retry failed requests 2 times
  });

  // Extract data with fallbacks — plain derivations, no useMemo needed
  // (these only recompute when `data` changes, which is already controlled by React Query)
  const user = data?.user || { email: "", role: "", is_admin: false };
  const stats = data?.stats || {
    activeCases: 0,
    criticalDeadlines: 0,
    pendingInvoices: 0,
    whatsappUnread: 0,
    emailUnread: 0,
    hoursWorked: "0h 0m",
  };
  const practices = data?.data?.practices || [];
  const interactions = data?.data?.interactions || [];
  const emailStats = data?.data?.email || { connected: false, unread_count: 0 };
  const systemStatus = data?.system_status || "degraded";
  const isZero = user.is_admin;
  const totalUnread = stats.whatsappUnread + stats.emailUnread;
  const isHealthy = systemStatus === "healthy";
  const revenue = data?.revenue || null;
  const revenueGrowth = data?.revenue_growth ?? null;
  const totalClients = data?.total_clients ?? null;
  const totalPractices = data?.total_practices ?? null;

  return {
    // Data
    user,
    stats,
    practices,
    interactions,
    emailStats,
    systemStatus,
    isZero,

    // Loading states
    isLoading: loading,
    isError: !!error,
    error,

    // Actions
    refetch,

    // Computed (now memoized)
    totalUnread,
    isHealthy,

    // Admin-only data
    revenue,
    revenueGrowth,
    totalClients,
    totalPractices,
  };
}

export type UseDashboardDataReturn = ReturnType<typeof useDashboardData>;
