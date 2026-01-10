/**
 * Custom hook for dashboard data management
 * Replaces 7 separate API calls with 1 optimized call using React Query
 */

import { useQuery } from '@tanstack/react-query';
import { dashboardApi, type DashboardData } from '@/lib/api/dashboard/dashboard.api';

export function useDashboardData() {
  const {
    data,
    isLoading: loading,
    error,
    refetch,
  } = useQuery<DashboardData>({
    queryKey: ['dashboard'],
    queryFn: () => dashboardApi.getDashboardSummary(),
    staleTime: 30_000, // Cache for 30 seconds
    refetchInterval: 60_000, // Auto-refresh every minute
    retry: 2, // Retry failed requests 2 times
  });

  // Extract data with fallbacks
  const user = data?.user || { email: '', role: '', is_admin: false };
  const stats = data?.stats || {
    activeCases: 0,
    criticalDeadlines: 0,
    whatsappUnread: 0,
    emailUnread: 0,
    hoursWorked: '0h 0m',
  };
  const practices = data?.data?.practices || [];
  const interactions = data?.data?.interactions || [];
  const emailStats = data?.data?.email || { connected: false, unread_count: 0 };
  const systemStatus = data?.system_status || 'degraded';

  // Check if user is zero@balizero.com
  const isZero = user.email === 'zero@balizero.com';

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
    
    // Computed
    totalUnread: stats.whatsappUnread + stats.emailUnread,
    isHealthy: systemStatus === 'healthy',
  };
}

export type UseDashboardDataReturn = ReturnType<typeof useDashboardData>;
