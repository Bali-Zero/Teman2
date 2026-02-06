/**
 * useCrmNotifications Hook
 * 
 * Hook per notifiche e alert del CRM:
 * - Documenti in scadenza
 * - Pratiche da completare
 * - Passaporti in scadenza
 * - Nuovi clienti
 */

import { useCallback, useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { Client, ExpiryAlert, Practice } from '@/lib/api/crm/crm.types';

interface Notification {
  id: string;
  type: 'expiry' | 'overdue' | 'new_client' | 'status_change';
  title: string;
  message: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  createdAt: string;
  read: boolean;
  actionUrl?: string;
  metadata?: Record<string, any>;
}

interface UseCrmNotificationsOptions {
  unreadOnly?: boolean;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

const NOTIFICATION_ICONS = {
  expiry: 'Calendar',
  overdue: 'AlertTriangle',
  new_client: 'UserPlus',
  status_change: 'RefreshCw',
} as const;

const NOTIFICATION_COLORS = {
  low: 'blue',
  medium: 'yellow',
  high: 'orange',
  critical: 'red',
} as const;

/**
 * Hook per notifiche CRM
 */
export function useCrmNotifications(options: UseCrmNotificationsOptions = {}) {
  const {
    unreadOnly = false,
    autoRefresh = true,
    refreshInterval = 5 * 60 * 1000, // 5 minutes
  } = options;

  const queryClient = useQueryClient();
  const [unreadCount, setUnreadCount] = useState(0);

  const query = useQuery({
    queryKey: ['crm', 'notifications', { unreadOnly }],
    queryFn: async (): Promise<Notification[]> => {
      return api.client.request<Notification[]>(
        `/api/crm/notifications${unreadOnly ? '?unread_only=true' : ''}`
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

  // Mark as read
  const markAsRead = useMutation({
    mutationFn: async (notificationId: string) => {
      return api.client.request(`/api/crm/notifications/${notificationId}/read`, {
        method: 'POST',
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['crm', 'notifications'] });
    },
  });

  // Mark all as read
  const markAllAsRead = useMutation({
    mutationFn: async () => {
      return api.client.request('/api/crm/notifications/read-all', {
        method: 'POST',
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['crm', 'notifications'] });
      setUnreadCount(0);
    },
  });

  // Dismiss notification
  const dismiss = useMutation({
    mutationFn: async (notificationId: string) => {
      return api.client.request(`/api/crm/notifications/${notificationId}`, {
        method: 'DELETE',
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['crm', 'notifications'] });
    },
  });

  return {
    notifications: query.data || [],
    unreadCount,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    markAsRead: markAsRead.mutate,
    markAllAsRead: markAllAsRead.mutate,
    dismiss: dismiss.mutate,
    isMarkingAsRead: markAsRead.isPending,
    isMarkingAllAsRead: markAllAsRead.isPending,
  };
}

/**
 * Hook per alert scadenze
 */
export function useExpiryAlerts(days: number = 30) {
  return useQuery({
    queryKey: ['crm', 'alerts', 'expiry', days],
    queryFn: async (): Promise<ExpiryAlert[]> => {
      return api.client.request<ExpiryAlert[]>(`/api/crm/alerts/expiry?days=${days}`);
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Hook per pratiche in scadenza
 */
export function useOverduePractices(days: number = 7) {
  return useQuery({
    queryKey: ['crm', 'alerts', 'overdue', days],
    queryFn: async (): Promise<Practice[]> => {
      return api.client.request<Practice[]>(`/api/crm/practices/overdue?days=${days}`);
    },
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Hook per dashboard stats
 */
export function useDashboardStats() {
  return useQuery({
    queryKey: ['crm', 'dashboard'],
    queryFn: async () => {
      return api.client.request<{
        totalClients: number;
        newThisMonth: number;
        activePractices: number;
        overduePractices: number;
        expiryAlerts: number;
        revenue: {
          total: number;
          paid: number;
          outstanding: number;
        };
        byStatus: Record<string, number>;
        recentActivity: Array<{
          type: string;
          description: string;
          timestamp: string;
        }>;
      }>('/api/crm/dashboard');
    },
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
}

/**
 * Hook per attività recenti
 */
export function useRecentActivity(limit: number = 10) {
  return useQuery({
    queryKey: ['crm', 'activity', limit],
    queryFn: async () => {
      return api.client.request<Array<{
        id: string;
        type: 'client_created' | 'practice_created' | 'status_changed' | 'document_uploaded' | 'note_added';
        description: string;
        user: string;
        timestamp: string;
        clientId?: number;
        practiceId?: number;
      }>>(`/api/crm/activity?limit=${limit}`);
    },
    staleTime: 60 * 1000,
  });
}

/**
 * Hook per notifiche browser (push notifications)
 */
export function useBrowserNotifications() {
  const [permission, setPermission] = useState<NotificationPermission>('default');
  const [supported, setSupported] = useState(false);

  useEffect(() => {
    if ('Notification' in window) {
      setSupported(true);
      setPermission(Notification.permission);
    }
  }, []);

  const requestPermission = useCallback(async () => {
    if (!supported) return false;
    
    const result = await Notification.requestPermission();
    setPermission(result);
    return result === 'granted';
  }, [supported]);

  const showNotification = useCallback((title: string, options?: NotificationOptions) => {
    if (supported && permission === 'granted') {
      return new Notification(title, {
        icon: '/favicon.ico',
        badge: '/favicon.ico',
        ...options,
      });
    }
    return null;
  }, [supported, permission]);

  return {
    supported,
    permission,
    requestPermission,
    showNotification,
    isGranted: permission === 'granted',
    isDenied: permission === 'denied',
  };
}

export type { Notification };
export { NOTIFICATION_ICONS, NOTIFICATION_COLORS };
