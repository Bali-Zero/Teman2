/**
 * WebSocket Context Provider
 * Manages WebSocket connections for real-time updates
 */

'use client';

import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react';
import type { WebSocketMessage, WebSocketChannel } from '@/lib/api/zantara-sdk/types';

export interface WebSocketContextValue {
  isConnected: boolean;
  connect: () => void;
  disconnect: () => void;
  sendMessage: (message: WebSocketMessage) => void;
  subscribe: (channel: WebSocketChannel, callback: (message: WebSocketMessage) => void) => () => void;
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

export interface WebSocketProviderProps {
  children: React.ReactNode;
  url: string;
  token?: string;
  autoConnect?: boolean;
}

export function WebSocketProvider({
  children,
  url,
  token,
  autoConnect = true,
}: WebSocketProviderProps) {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const subscribersRef = useRef<Map<WebSocketChannel, Set<(message: WebSocketMessage) => void>>>(
    new Map()
  );
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 5;
  const reconnectDelay = 3000;

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return; // Already connected
    }

    try {
      // Build WebSocket URL with token
      const wsUrl = url.replace(/^http/, 'ws');
      const ws = new WebSocket(wsUrl, token ? [`bearer.${token}`] : undefined);

      ws.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        reconnectAttemptsRef.current = 0;

        // Send ping to keep connection alive
        const pingInterval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }));
          } else {
            clearInterval(pingInterval);
          }
        }, 30000); // Ping every 30 seconds
      };

      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);

          // Handle pong
          if (message.type === 'pong') {
            return;
          }

          // Route message to subscribers based on type
          const channelMap: Record<string, WebSocketChannel> = {
            notification: 'USER_NOTIFICATIONS',
            'ai-result': 'AI_RESULTS',
            'chat-message': 'CHAT_MESSAGES',
            'system-event': 'SYSTEM_EVENTS',
          };

          const channel = channelMap[message.type] || 'SYSTEM_EVENTS';
          const subscribers = subscribersRef.current.get(channel);
          if (subscribers) {
            subscribers.forEach((callback) => callback(message));
          }
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err);
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setIsConnected(false);
        wsRef.current = null;

        // Attempt to reconnect
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current += 1;
          reconnectTimeoutRef.current = setTimeout(() => {
            console.log(`Reconnecting... (attempt ${reconnectAttemptsRef.current})`);
            connect();
          }, reconnectDelay);
        } else {
          console.error('Max reconnection attempts reached');
        }
      };

      wsRef.current = ws;
    } catch (err) {
      console.error('Failed to create WebSocket connection:', err);
      setIsConnected(false);
    }
  }, [url, token]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setIsConnected(false);
  }, []);

  const sendMessage = useCallback((message: WebSocketMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket is not connected');
    }
  }, []);

  const subscribe = useCallback(
    (channel: WebSocketChannel, callback: (message: WebSocketMessage) => void) => {
      if (!subscribersRef.current.has(channel)) {
        subscribersRef.current.set(channel, new Set());
      }
      subscribersRef.current.get(channel)!.add(callback);

      // Return unsubscribe function
      return () => {
        const subscribers = subscribersRef.current.get(channel);
        if (subscribers) {
          subscribers.delete(callback);
          if (subscribers.size === 0) {
            subscribersRef.current.delete(channel);
          }
        }
      };
    },
    []
  );

  // Auto-connect on mount
  useEffect(() => {
    if (autoConnect) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [autoConnect, connect, disconnect]);

  const value: WebSocketContextValue = {
    isConnected,
    connect,
    disconnect,
    sendMessage,
    subscribe,
  };

  return <WebSocketContext.Provider value={value}>{children}</WebSocketContext.Provider>;
}

export function useWebSocket() {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within WebSocketProvider');
  }
  return context;
}

