/**
 * Realtime Hook Types
 * Type definitions for useRealtime hook return value
 */

import type {
  UserPresenceData,
  WebSocketMessageType,
} from "../api/types/realtime.types";

export interface RealtimeHookReturn {
  isConnected: boolean;
  onlineUsers: UserPresenceData[];
  onlineUsersCount: number;
  connect: (userId: string, userName: string) => Promise<void>;
  disconnect: () => void;
  sendDashboardUpdate: (
    action: "view" | "edit" | "delete" | "create",
    resource: "case" | "email" | "client" | "document",
    resourceId: string,
    changes?: Record<string, unknown>,
  ) => void;
  subscribe: <T extends WebSocketMessageType>(
    type: T,
    callback: (
      data: T extends "dashboard_update"
        ? import("../api/types/realtime.types").DashboardUpdateData
        : T extends "user_presence"
          ? UserPresenceData
          : T extends "case_update"
            ? import("../api/types/realtime.types").CaseUpdateData
            : T extends "email_update"
              ? import("../api/types/realtime.types").EmailUpdateData
              : T extends "system_alert"
                ? import("../api/types/realtime.types").SystemAlertData
                : T extends "heartbeat"
                  ? import("../api/types/realtime.types").HeartbeatData
                  : T extends "connection_status"
                    ? import("../api/types/realtime.types").ConnectionStatusData
                    : never,
    ) => void,
  ) => () => void;
}
