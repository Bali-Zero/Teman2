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
    queryFn: async () => {
      try {
        return await dashboardApi.getDashboardSummary();
      } catch (err) {
        // Detailed error logging for debugging
        const errorDetails = {
          message: err instanceof Error ? err.message : String(err),
          name: err instanceof Error ? err.name : 'UnknownError',
          stack: err instanceof Error ? err.stack : undefined,
          timestamp: new Date().toISOString(),
          endpoint: '/api/dashboard/summary',
        };

        // Log to console with full details
        console.error('[Dashboard] Failed to load dashboard data:', errorDetails);

        // Check for specific error types
        if (err instanceof Error) {
          if (err.message.includes('401') || err.message.includes('Unauthorized')) {
            console.error('[Dashboard] Authentication error - user may need to login again');
          } else if (err.message.includes('403') || err.message.includes('Forbidden')) {
            console.error('[Dashboard] Authorization error - user may not have permission');
          } else if (err.message.includes('Network') || err.message.includes('fetch')) {
            console.error('[Dashboard] Network error - backend may be unreachable');
          } else if (err.message.includes('CORS')) {
            console.error('[Dashboard] CORS error - backend CORS configuration may be incorrect');
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

  // Log error details when error occurs
  if (error) {
    console.error('[Dashboard] Error state detected:', {
      error: error instanceof Error ? {
        message: error.message,
        name: error.name,
        stack: error.stack,
      } : error,
      hasData: !!data,
      timestamp: new Date().toISOString(),
    });
  }

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
