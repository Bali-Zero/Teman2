/**
 * CRM Hooks Index
 * 
 * Esporta tutti gli hooks CRM ottimizzati
 */

// Client hooks
export {
  useCrmClients,
  useCrmClient,
  useCreateClient,
  useUpdateClient,
  useCrmStats,
} from './useCrmClients';

// Practice hooks
export {
  useCrmPractices,
  useCrmPractice,
  useCreatePractice,
  useUpdatePractice,
  useUpdatePracticeStatus,
  useDeletePractice,
  PRACTICE_STATUSES,
  PRACTICE_PRIORITIES,
} from './useCrmPractices';

// Search hooks
export {
  useCrmSearch,
  useQuickSearch,
  useGlobalSearch,
} from './useCrmSearch';

// Notification hooks
export {
  useCrmNotifications,
  useExpiryAlerts,
  useUpcomingRenewals,
  useExpiryAlertsSummary,
  useDashboardStats,
  useRecentActivity,
  useBrowserNotifications,
  NOTIFICATION_ICONS,
  NOTIFICATION_COLORS,
  type Notification,
} from './useCrmNotifications';

// Re-export from optimized hooks
export {
  useDebounce,
  useDebouncedCallback,
} from '@/lib/hooks/optimized/useDebounce';
