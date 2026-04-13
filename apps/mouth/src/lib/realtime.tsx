/**
 * Real-time WebSocket service for dashboard collaboration
 * Enables live updates, user presence, and collaborative features
 */

import React from "react";
import { logger } from "./logger";
import { getValidToken } from "./utils/token";
import type { Metadata } from "./types/common";
import type {
  WebSocketMessage,
  WebSocketMessageType,
  DashboardUpdateData,
  UserPresenceData,
  CaseUpdateData,
  EmailUpdateData,
  SystemAlertData,
  WebSocketMessageData,
  HeartbeatData,
  ConnectionStatusData,
} from "./api/types/realtime.types";
import { isWebSocketMessage, isMessageType } from "./api/types/realtime.types";
import type { RealtimeHookReturn } from "./types/realtime-hook.types";

// Types moved to realtime.types.ts - using imported types

class RealtimeService {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private listeners: Map<string, Set<(data: WebSocketMessageData) => void>> =
    new Map();
  private isConnecting = false;
  private heartbeatInterval: NodeJS.Timeout | null = null;

  constructor() {
    // Only setup event listeners in browser (not during SSR)
    if (typeof window !== "undefined") {
      this.setupEventListeners();
    }
  }

  // Initialize WebSocket connection
  async connect(userId: string, userName: string): Promise<void> {
    if (
      this.isConnecting ||
      (this.ws && this.ws.readyState === WebSocket.OPEN)
    ) {
      return;
    }

    // Get auth token from localStorage with expiry validation, fallback to sessionStorage
    let token: string | null = null;
    if (typeof window !== "undefined") {
      token = getValidToken("auth_token", localStorage);
      // Fallback: try sessionStorage
      if (!token) {
        token = getValidToken("auth_token", sessionStorage);
      }
    }

    if (!token) {
      logger.warn("Cannot connect WebSocket: No auth token available", {
        component: "RealtimeService",
        action: "connect_no_token",
      });
      // IMPROVED: Prevent infinite reconnect loop when no token
      this.reconnectAttempts = this.maxReconnectAttempts;
      return;
    }

    // IMPROVED: Validate token format (JWT has 3 parts separated by dots)
    const tokenParts = token.split(".");
    if (tokenParts.length !== 3 || token.length < 50) {
      logger.warn("Invalid token format detected", {
        component: "RealtimeService",
        action: "invalid_token_format",
      });
      this.reconnectAttempts = this.maxReconnectAttempts;
      return;
    }

    this.isConnecting = true;

    try {
      const wsUrl =
        process.env.NEXT_PUBLIC_WS_URL || "wss://nuzantara-rag.fly.dev/ws";
      // Pass token via subprotocol (browser WebSocket doesn't support custom headers)
      // Backend expects: "bearer.<token>"
      this.ws = new WebSocket(wsUrl, [`bearer.${token}`]);

      this.ws.onopen = () => {
        logger.info("WebSocket connected", {
          component: "RealtimeService",
          action: "connect",
        });
        this.isConnecting = false;
        this.reconnectAttempts = 0;
        this.startHeartbeat();
        this.sendPresence("online");
      };

      this.ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          this.handleMessage(message);
        } catch (error) {
          logger.error(
            "Failed to parse WebSocket message",
            {
              component: "RealtimeService",
              action: "parse_message",
            },
            error instanceof Error ? error : new Error(String(error)),
          );
        }
      };

      this.ws.onclose = (event) => {
        // Only log if it was a clean close or unexpected close after successful connection
        // Don't log if it failed during handshake (code 1006 = abnormal closure)
        if (event.code !== 1006 || this.ws?.readyState === WebSocket.OPEN) {
          logger.info("WebSocket disconnected", {
            component: "RealtimeService",
            action: "disconnect",
            code: event.code,
            reason: event.reason || "Unknown",
          });
        }
        this.isConnecting = false;
        this.stopHeartbeat();
        // Only schedule reconnect if we had a successful connection before
        if (event.code !== 1006) {
          this.scheduleReconnect();
        } else {
          // Server doesn't support WebSocket, stop trying
          this.reconnectAttempts = this.maxReconnectAttempts;
        }
      };

      this.ws.onerror = (error) => {
        // Only log error if we're actually trying to connect
        // WebSocket errors during handshake are common if server doesn't support WS
        if (this.isConnecting) {
          logger.warn(
            "WebSocket connection error (server may not support WebSocket)",
            {
              component: "RealtimeService",
              action: "websocket_error",
              note: "This is non-critical - real-time features will be disabled",
            },
          );
        }
        this.isConnecting = false;
        // Prevent infinite reconnect attempts
        this.reconnectAttempts = this.maxReconnectAttempts;
      };
    } catch (error) {
      logger.error(
        "Failed to connect WebSocket",
        {
          component: "RealtimeService",
          action: "connect_error",
        },
        error instanceof Error ? error : new Error(String(error)),
      );
      this.isConnecting = false;
      this.scheduleReconnect();
    }
  }

  // Disconnect WebSocket
  disconnect(): void {
    if (this.ws) {
      this.sendPresence("offline");
      this.ws.close();
      this.ws = null;
    }
    this.stopHeartbeat();
  }

  // Subscribe to specific message types
  subscribe<T extends WebSocketMessageType>(
    type: T,
    callback: (data: WebSocketMessage<T>["data"]) => void,
  ): () => void {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, new Set());
    }
    // Type assertion needed because Set stores WebSocketMessageData but we have typed callbacks
    this.listeners
      .get(type)!
      .add(callback as (data: WebSocketMessageData) => void);

    // Return unsubscribe function
    return () => {
      const callbacks = this.listeners.get(type);
      if (callbacks) {
        callbacks.delete(callback as (data: WebSocketMessageData) => void);
        if (callbacks.size === 0) {
          this.listeners.delete(type);
        }
      }
    };
  }

  // Send message to server
  private send<T extends WebSocketMessageType>(
    type: T,
    data: WebSocketMessage<T>["data"],
  ): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      const message: WebSocketMessage<T> = {
        type,
        data,
        timestamp: new Date().toISOString(),
        userId: this.getCurrentUserId(),
        userName: this.getCurrentUserName(),
      };
      this.ws.send(JSON.stringify(message));
    }
  }

  // Send user presence update
  sendPresence(status: "online" | "offline" | "away"): void {
    this.send("user_presence", {
      status,
      currentView: window.location.pathname,
      timestamp: new Date().toISOString(),
    });
  }

  // Send dashboard activity
  sendDashboardUpdate(
    action: DashboardUpdateData["action"],
    resource: DashboardUpdateData["resource"],
    resourceId: string,
    changes?: Record<string, unknown>,
  ): void {
    this.send("dashboard_update", {
      userId: this.getCurrentUserId(),
      action,
      resource,
      resourceId,
      changes,
    });
  }

  // Handle incoming messages
  private handleMessage(message: WebSocketMessage): void {
    const callbacks = this.listeners.get(message.type);
    if (callbacks) {
      callbacks.forEach((callback) => {
        // Type-safe callback invocation
        callback(message.data as WebSocketMessageData);
      });
    }

    // Handle system messages with type guards
    if (isMessageType(message, "user_presence")) {
      this.updateUserPresence(message.data);
    } else if (isMessageType(message, "dashboard_update")) {
      this.handleDashboardUpdate(message.data);
    } else if (isMessageType(message, "system_alert")) {
      this.showSystemAlert(message.data);
    }
  }

  // Auto-reconnect logic
  private scheduleReconnect(): void {
    // Don't reconnect if no valid auth token available
    const token =
      typeof window !== "undefined" ? getValidToken("auth_token", localStorage) : null;
    if (!token) {
      logger.debug("Skipping WebSocket reconnect: No auth token", {
        component: "RealtimeService",
        action: "reconnect_skip",
      });
      return;
    }

    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay =
        this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

      logger.debug("Reconnecting WebSocket", {
        component: "RealtimeService",
        action: "reconnect",
        metadata: {
          delay,
          attempt: this.reconnectAttempts,
        },
      });

      setTimeout(() => {
        this.connect(this.getCurrentUserId(), this.getCurrentUserName());
      }, delay);
    } else {
      logger.warn("Max reconnection attempts reached", {
        component: "RealtimeService",
        action: "max_reconnect",
        metadata: {
          maxAttempts: this.maxReconnectAttempts,
        },
      });
    }
  }

  // Heartbeat to keep connection alive
  private startHeartbeat(): void {
    this.heartbeatInterval = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.send("heartbeat", { timestamp: Date.now() });
      }
    }, 30000); // 30 seconds
  }

  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = null;
    }
  }

  // Update user presence in local state
  private updateUserPresence(data: UserPresenceData): void {
    // This would typically update a global state management store
    logger.debug("User presence updated", {
      component: "RealtimeService",
      action: "presence_update",
      metadata: data as unknown as Metadata,
    });
  }

  // Handle dashboard updates from other users
  private handleDashboardUpdate(data: DashboardUpdateData): void {
    logger.debug("Dashboard update received", {
      component: "RealtimeService",
      action: "dashboard_update",
      metadata: data as unknown as Metadata,
    });
    // Trigger refresh of relevant data
    this.notifyDashboardUpdate(data);
  }

  // Show system alerts
  private showSystemAlert(data: SystemAlertData): void {
    logger.info("System alert", {
      component: "RealtimeService",
      action: "system_alert",
      metadata: data as unknown as Metadata,
    });
    // Show toast notification or banner
  }

  // Notify dashboard components of updates
  private notifyDashboardUpdate(update: DashboardUpdateData): void {
    const callbacks = this.listeners.get("dashboard_refresh");
    if (callbacks) {
      callbacks.forEach((callback) => callback(update as WebSocketMessageData));
    }
  }

  // Setup browser event listeners
  private setupEventListeners(): void {
    // Send presence updates on page visibility changes
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) {
        this.sendPresence("away");
      } else {
        this.sendPresence("online");
      }
    });

    // Send presence updates on page unload
    window.addEventListener("beforeunload", () => {
      this.sendPresence("offline");
    });

    // Track current view changes
    window.addEventListener("popstate", () => {
      this.sendPresence("online");
    });
  }

  // Helper methods to get current user info
  private getCurrentUserId(): string {
    // This would typically come from auth context
    return localStorage.getItem("userId") || "anonymous";
  }

  private getCurrentUserName(): string {
    // This would typically come from auth context
    return localStorage.getItem("userName") || "Anonymous User";
  }

  // Get connection status
  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  // Get online users count
  getOnlineUsersCount(): number {
    // This would typically come from a global state
    return 0; // Placeholder
  }
}

// Singleton instance
export const realtimeService = new RealtimeService();

// React hook for real-time features
export function useRealtime(): RealtimeHookReturn {
  const [isConnected, setIsConnected] = React.useState(false);
  const [onlineUsers, setOnlineUsers] = React.useState<UserPresenceData[]>([]);

  React.useEffect(() => {
    // Subscribe to connection status changes
    const unsubscribeConnection = realtimeService.subscribe(
      "connection_status",
      (data) => {
        if (data && typeof data === "object" && "connected" in data) {
          setIsConnected((data as { connected: boolean }).connected);
        }
      },
    );

    // Subscribe to user presence updates
    const unsubscribePresence = realtimeService.subscribe(
      "user_presence",
      (data) => {
        // User presence data is a single object, not an array
        if (data && typeof data === "object" && "status" in data) {
          // Update online users list - this would need to be managed differently
          // For now, just track the current user's presence
          setOnlineUsers([data as UserPresenceData]);
        }
      },
    );

    return () => {
      unsubscribeConnection();
      unsubscribePresence();
    };
  }, []);

  return {
    isConnected,
    onlineUsers,
    onlineUsersCount: onlineUsers.length,
    connect: realtimeService.connect.bind(realtimeService),
    disconnect: realtimeService.disconnect.bind(realtimeService),
    sendDashboardUpdate:
      realtimeService.sendDashboardUpdate.bind(realtimeService),
    subscribe: realtimeService.subscribe.bind(realtimeService),
  };
}

// Higher-order component for real-time updates
export function withRealtime<P extends object>(
  Component: React.ComponentType<P & { realtime?: RealtimeHookReturn }>,
) {
  const WrappedComponent = (props: P) => {
    const realtime = useRealtime();

    return <Component {...props} realtime={realtime} />;
  };

  WrappedComponent.displayName = `withRealtime(${Component.displayName || Component.name})`;
  return WrappedComponent;
}
