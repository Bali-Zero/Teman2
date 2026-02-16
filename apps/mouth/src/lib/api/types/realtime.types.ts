/**
 * Real-time WebSocket message types
 * Type-safe definitions for WebSocket communication
 */

/**
 * Base WebSocket message structure
 */
export interface WebSocketMessageBase {
  timestamp: string;
  userId: string;
  userName: string;
}

/**
 * Message type discriminator
 */
export type WebSocketMessageType =
  | "dashboard_update"
  | "user_presence"
  | "case_update"
  | "email_update"
  | "system_alert"
  | "heartbeat"
  | "connection_status";

/**
 * Dashboard update message data
 */
export interface DashboardUpdateData {
  userId: string;
  action: "view" | "edit" | "delete" | "create";
  resource: "case" | "email" | "client" | "document";
  resourceId: string;
  changes?: Record<string, unknown>;
}

/**
 * User presence message data
 */
export interface UserPresenceData {
  status: "online" | "offline" | "away";
  currentView: string;
  timestamp: string;
}

/**
 * Case update message data
 */
export interface CaseUpdateData {
  caseId: string;
  changes: Record<string, unknown>;
  updatedBy: string;
}

/**
 * Email update message data
 */
export interface EmailUpdateData {
  emailId: string;
  changes: Record<string, unknown>;
  updatedBy: string;
}

/**
 * System alert message data
 */
export interface SystemAlertData {
  level: "info" | "warning" | "error" | "success";
  message: string;
  title?: string;
  actionUrl?: string;
}

/**
 * Heartbeat message data
 */
export interface HeartbeatData {
  timestamp: number;
}

/**
 * Connection status message data
 */
export interface ConnectionStatusData {
  connected: boolean;
}

/**
 * Union type for all message data types
 */
export type WebSocketMessageData =
  | DashboardUpdateData
  | UserPresenceData
  | CaseUpdateData
  | EmailUpdateData
  | SystemAlertData
  | HeartbeatData
  | ConnectionStatusData;

/**
 * Type-safe WebSocket message
 */
export interface WebSocketMessage<
  T extends WebSocketMessageType = WebSocketMessageType,
> extends WebSocketMessageBase {
  type: T;
  data: T extends "dashboard_update"
    ? DashboardUpdateData
    : T extends "user_presence"
      ? UserPresenceData
      : T extends "case_update"
        ? CaseUpdateData
        : T extends "email_update"
          ? EmailUpdateData
          : T extends "system_alert"
            ? SystemAlertData
            : T extends "heartbeat"
              ? HeartbeatData
              : T extends "connection_status"
                ? ConnectionStatusData
                : never;
}

/**
 * Type guard for WebSocket message type
 */
export function isWebSocketMessage(value: unknown): value is WebSocketMessage {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const msg = value as Record<string, unknown>;
  return (
    typeof msg.type === "string" &&
    typeof msg.timestamp === "string" &&
    typeof msg.userId === "string" &&
    typeof msg.userName === "string" &&
    "data" in msg
  );
}

/**
 * Type guard for specific message type
 */
export function isMessageType<T extends WebSocketMessageType>(
  message: WebSocketMessage,
  type: T,
): message is WebSocketMessage<T> {
  return message.type === type;
}
