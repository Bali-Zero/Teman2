/**
 * Realtime Hook Types
 * Type definitions for useRealtime hook return value
 */

import type { UserPresenceData } from '../api/types/realtime.types';

export interface RealtimeHookReturn {
  isConnected: boolean;
  onlineUsers: UserPresenceData[];
  onlineUsersCount: number;
  connect: (userId: string, userName: string) => Promise<void>;
  disconnect: () => void;
  sendDashboardUpdate: (
    action: 'view' | 'edit' | 'delete' | 'create',
    resource: 'case' | 'email' | 'client' | 'document',
    resourceId: string,
    changes?: Record<string, unknown>
  ) => void;
  subscribe: <T extends unknown>(
    event: string,
    callback: (data: T) => void
  ) => () => void;
}
