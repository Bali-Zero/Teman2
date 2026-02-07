/**
 * CRM & Portal Hooks Index
 *
 * Esporta tutti gli hooks ottimizzati
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
export { useCrmSearch, useQuickSearch, useGlobalSearch } from './useCrmSearch';

// CRM Notification hooks
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

// Portal hooks
export {
  usePortalDashboard,
  usePortalTimeline,
  usePortalProfile,
  useVisaStatus,
  usePortalCompanies,
  usePortalCompany,
  useSetPrimaryCompany,
  useTaxOverview,
  usePortalDocuments,
  usePortalMessages,
  usePortalPreferences,
  useValidateInviteToken,
  useCompleteRegistration,
  usePortalNotifications,
} from './usePortal';

// Drive optimized hooks
export {
  useDriveStatus,
  useDriveFilesInfinite,
  useDriveFiles,
  useFileMetadata,
  usePrefetchFolder,
  useDriveUpload,
  useDriveMutationsOptimized,
  useDriveSearch,
} from './useDriveOptimized';

// File selection hook
export { useFileSelection, useFileKeyboardNavigation } from './useFileSelection';

// Re-export from optimized hooks
export { useDebounce, useDebouncedCallback } from '@/lib/hooks/optimized/useDebounce';

// Optimized list hooks
export { useOptimizedList, useInfiniteScroll } from './useOptimizedList';

// React Query hooks
export {
  useClientsQuery,
  useClientQuery,
  useCreateClientMutation,
  useUpdateClientMutation,
  useDeleteClientMutation,
  usePrefetchClients,
  clientKeys,
} from './useClientsQuery';

export {
  useArticlesQuery,
  useArticleQuery,
  useNewsFeedQuery,
  useArticleMutation,
  usePublishArticleMutation,
  usePrefetchArticles,
  articleKeys,
} from './useArticlesQuery';
