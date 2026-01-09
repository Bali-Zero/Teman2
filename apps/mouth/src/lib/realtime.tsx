/**
 * Real-time WebSocket service for dashboard collaboration
 * Enables live updates, user presence, and collaborative features
 */

import React from 'react';
import { logger } from './logger';

interface WebSocketMessage {
  type: 'dashboard_update' | 'user_presence' | 'case_update' | 'email_update' | 'system_alert';
  data: any;
  timestamp: string;
  userId: string;
  userName: string;
}

interface UserPresence {
  userId: string;
  userName: string;
  email: string;
  avatar?: string;
  currentView: string;
  lastSeen: string;
  isOnline: boolean;
}

interface DashboardUpdate {
  userId: string;
  action: 'view' | 'edit' | 'delete' | 'create';
  resource: 'case' | 'email' | 'client' | 'document';
  resourceId: string;
  changes?: Record<string, any>;
}

class RealtimeService {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private listeners: Map<string, Set<(data: any) => void>> = new Map();
  private isConnecting = false;
  private heartbeatInterval: NodeJS.Timeout | null = null;

  constructor() {
    this.setupEventListeners();
  }

  // Initialize WebSocket connection
  async connect(userId: string, userName: string): Promise<void> {
    if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.OPEN)) {
      return;
    }

    this.isConnecting = true;

    try {
      const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'wss://nuzantara-rag.fly.dev/ws';
      this.ws = new WebSocket(`${wsUrl}?userId=${userId}&userName=${encodeURIComponent(userName)}`);

      this.ws.onopen = () => {
        logger.info('WebSocket connected', {
          component: 'RealtimeService',
          action: 'connect',
        });
        this.isConnecting = false;
        this.reconnectAttempts = 0;
        this.startHeartbeat();
        this.sendPresence('online');
      };

      this.ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          this.handleMessage(message);
        } catch (error) {
          logger.error('Failed to parse WebSocket message', {
            component: 'RealtimeService',
            action: 'parse_message',
          }, error instanceof Error ? error : new Error(String(error)));
        }
      };

      this.ws.onclose = () => {
        logger.info('WebSocket disconnected', {
          component: 'RealtimeService',
          action: 'disconnect',
        });
        this.isConnecting = false;
        this.stopHeartbeat();
        this.scheduleReconnect();
      };

      this.ws.onerror = (error) => {
        logger.error('WebSocket error', {
          component: 'RealtimeService',
          action: 'websocket_error',
        }, error instanceof Error ? error : new Error(String(error)));
        this.isConnecting = false;
      };

    } catch (error) {
      logger.error('Failed to connect WebSocket', {
        component: 'RealtimeService',
        action: 'connect_error',
      }, error instanceof Error ? error : new Error(String(error)));
      this.isConnecting = false;
      this.scheduleReconnect();
    }
  }

  // Disconnect WebSocket
  disconnect(): void {
    if (this.ws) {
      this.sendPresence('offline');
      this.ws.close();
      this.ws = null;
    }
    this.stopHeartbeat();
  }

  // Subscribe to specific message types
  subscribe(type: string, callback: (data: any) => void): () => void {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, new Set());
    }
    this.listeners.get(type)!.add(callback);

    // Return unsubscribe function
    return () => {
      const callbacks = this.listeners.get(type);
      if (callbacks) {
        callbacks.delete(callback);
        if (callbacks.size === 0) {
          this.listeners.delete(type);
        }
      }
    };
  }

  // Send message to server
  private send(type: string, data: any): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      const message: WebSocketMessage = {
        type: type as any,
        data,
        timestamp: new Date().toISOString(),
        userId: this.getCurrentUserId(),
        userName: this.getCurrentUserName(),
      };
      this.ws.send(JSON.stringify(message));
    }
  }

  // Send user presence update
  sendPresence(status: 'online' | 'offline' | 'away'): void {
    this.send('user_presence', {
      status,
      currentView: window.location.pathname,
      timestamp: new Date().toISOString(),
    });
  }

  // Send dashboard activity
  sendDashboardUpdate(action: DashboardUpdate['action'], resource: DashboardUpdate['resource'], resourceId: string, changes?: Record<string, any>): void {
    this.send('dashboard_update', {
      action,
      resource,
      resourceId,
      changes,
      timestamp: new Date().toISOString(),
    });
  }

  // Handle incoming messages
  private handleMessage(message: WebSocketMessage): void {
    const callbacks = this.listeners.get(message.type);
    if (callbacks) {
      callbacks.forEach(callback => callback(message.data));
    }

    // Handle system messages
    switch (message.type) {
      case 'user_presence':
        this.updateUserPresence(message.data);
        break;
      case 'dashboard_update':
        this.handleDashboardUpdate(message.data);
        break;
      case 'system_alert':
        this.showSystemAlert(message.data);
        break;
    }
  }

  // Auto-reconnect logic
  private scheduleReconnect(): void {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
      
      logger.debug('Reconnecting WebSocket', {
        component: 'RealtimeService',
        action: 'reconnect',
        metadata: {
          delay,
          attempt: this.reconnectAttempts,
        },
      });
      
      setTimeout(() => {
        this.connect(this.getCurrentUserId(), this.getCurrentUserName());
      }, delay);
    } else {
      logger.error('Max reconnection attempts reached', {
        component: 'RealtimeService',
        action: 'max_reconnect',
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
        this.send('heartbeat', { timestamp: Date.now() });
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
  private updateUserPresence(data: UserPresence): void {
    // This would typically update a global state management store
    logger.debug('User presence updated', {
      component: 'RealtimeService',
      action: 'presence_update',
      metadata: data,
    });
  }

  // Handle dashboard updates from other users
  private handleDashboardUpdate(data: DashboardUpdate): void {
    logger.debug('Dashboard update received', {
      component: 'RealtimeService',
      action: 'dashboard_update',
      metadata: data,
    });
    // Trigger refresh of relevant data
    this.notifyDashboardUpdate(data);
  }

  // Show system alerts
  private showSystemAlert(data: any): void {
    logger.info('System alert', {
      component: 'RealtimeService',
      action: 'system_alert',
      metadata: data,
    });
    // Show toast notification or banner
  }

  // Notify dashboard components of updates
  private notifyDashboardUpdate(update: DashboardUpdate): void {
    const callbacks = this.listeners.get('dashboard_refresh');
    if (callbacks) {
      callbacks.forEach(callback => callback(update));
    }
  }

  // Setup browser event listeners
  private setupEventListeners(): void {
    // Send presence updates on page visibility changes
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        this.sendPresence('away');
      } else {
        this.sendPresence('online');
      }
    });

    // Send presence updates on page unload
    window.addEventListener('beforeunload', () => {
      this.sendPresence('offline');
    });

    // Track current view changes
    window.addEventListener('popstate', () => {
      this.sendPresence('online');
    });
  }

  // Helper methods to get current user info
  private getCurrentUserId(): string {
    // This would typically come from auth context
    return localStorage.getItem('userId') || 'anonymous';
  }

  private getCurrentUserName(): string {
    // This would typically come from auth context
    return localStorage.getItem('userName') || 'Anonymous User';
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
export function useRealtime() {
  const [isConnected, setIsConnected] = React.useState(false);
  const [onlineUsers, setOnlineUsers] = React.useState<UserPresence[]>([]);

  React.useEffect(() => {
    // Subscribe to connection status changes
    const unsubscribeConnection = realtimeService.subscribe('connection_status', (connected) => {
      setIsConnected(connected);
    });

    // Subscribe to user presence updates
    const unsubscribePresence = realtimeService.subscribe('user_presence', (users) => {
      setOnlineUsers(users);
    });

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
    sendDashboardUpdate: realtimeService.sendDashboardUpdate.bind(realtimeService),
    subscribe: realtimeService.subscribe.bind(realtimeService),
  };
}

// Higher-order component for real-time updates
export function withRealtime<P extends object>(
  Component: React.ComponentType<P & { realtime?: any }>
) {
  const WrappedComponent = (props: P) => {
    const realtime = useRealtime();

    return <Component {...props} realtime={realtime} />;
  };

  WrappedComponent.displayName = `withRealtime(${Component.displayName || Component.name})`;
  return WrappedComponent;
}
