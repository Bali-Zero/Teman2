import { useEffect, useRef, useCallback, useState } from 'react';
import { api } from '@/lib/api';
import { WEBSOCKET } from '@/constants';

type MessageHandler = (data: WebSocketMessage) => void;

function normalizeWsBaseUrl(url: string): string {
  // Accept either wss://host or wss://host/ws and normalize to wss://host
  return url.replace(/\/+$/, '').replace(/\/ws$/, '');
}

/**
 * Standard WebSocket message structure for the application.
 */
interface WebSocketMessage {
  type: string;
  content?: string;
  data?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

/**
 * Configuration options for the useWebSocket hook.
 */
interface UseWebSocketOptions {
  /** Callback triggered when a message is received */
  onMessage?: MessageHandler;
  /** Callback triggered when the connection is successfully established */
  onConnect?: () => void;
  /** Callback triggered when the connection is lost or closed */
  onDisconnect?: () => void;
  /** Callback triggered when a WebSocket error occurs */
  onError?: (error: Event) => void;
  /** Time in milliseconds to wait before attempting to reconnect (default: 3000) */
  reconnectInterval?: number;
  /** Maximum number of reconnection attempts before giving up (default: 5) */
  maxReconnectAttempts?: number;
}

/**
 * Custom hook for managing WebSocket connections with automatic reconnection,
 * authentication, and heartbeat (ping/pong) support.
 *
 * @param options - Configuration options for the WebSocket connection
 * @returns Object containing connection status and methods to interact with the WebSocket
 */
export function useWebSocket(options: UseWebSocketOptions = {}) {
  const {
    onMessage,
    onConnect,
    onDisconnect,
    onError,
    reconnectInterval = WEBSOCKET.RECONNECT_INTERVAL,
    maxReconnectAttempts = WEBSOCKET.MAX_RECONNECT_ATTEMPTS,
  } = options;

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);

  const clearPingInterval = useCallback(() => {
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
  }, []);

  // Ref to store the latest connect function to avoid circular dependency
  const connectRef = useRef<() => void>(() => {});

  const connect = useCallback(() => {
    const token = api.getToken();
    if (!token) {
      console.warn('No auth token for WebSocket');
      return;
    }

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    setIsConnecting(true);

    const apiWsUrl = typeof api.getWebSocketUrl === 'function' ? api.getWebSocketUrl() : undefined;
    const wsUrlCandidate =
      process.env.NEXT_PUBLIC_WS_URL ||
      apiWsUrl ||
      process.env.NEXT_PUBLIC_API_URL?.replace('https://', 'wss://').replace('http://', 'ws://') ||
      'wss://nuzantara-rag.fly.dev';
    const wsBaseUrl = normalizeWsBaseUrl(wsUrlCandidate);

    // SECURITY: Use subprotocol instead of query param to prevent token exposure in logs/URLs
    // WebSocket API doesn't support custom headers easily, so we use subprotocol as bearer token
    const ws = new WebSocket(`${wsBaseUrl}/ws`, [`bearer.${token}`]);

    ws.onopen = () => {
      // console.log('WebSocket connected');
      setIsConnected(true);
      setIsConnecting(false);
      reconnectAttemptsRef.current = 0;
      onConnect?.();

      // Start ping interval
      clearPingInterval();
      pingIntervalRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }));
        }
      }, WEBSOCKET.PING_INTERVAL);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as WebSocketMessage;
        onMessage?.(data);
      } catch {
        console.error('Failed to parse WebSocket message:', event.data);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setIsConnecting(false);
      onError?.(error);
    };

    ws.onclose = () => {
      setIsConnected(false);
      setIsConnecting(false);
      clearPingInterval();
      onDisconnect?.();

      // Attempt reconnect
      if (reconnectAttemptsRef.current < maxReconnectAttempts) {
        reconnectAttemptsRef.current++;
        // Use ref to call the latest connect function
        reconnectTimeoutRef.current = setTimeout(() => connectRef.current(), reconnectInterval);
      }
    };

    wsRef.current = ws;
  }, [
    onMessage,
    onConnect,
    onDisconnect,
    onError,
    reconnectInterval,
    maxReconnectAttempts,
    clearPingInterval,
  ]);

  // Update ref whenever connect changes
  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    clearPingInterval();
    reconnectAttemptsRef.current = maxReconnectAttempts; // Prevent reconnect
    wsRef.current?.close();
    wsRef.current = null;
    setIsConnected(false);
  }, [maxReconnectAttempts, clearPingInterval]);

  const send = useCallback((data: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
      return true;
    }
    console.warn('WebSocket not connected');
    return false;
  }, []);

  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    connect,
    disconnect,
    send,
    isConnected,
    isConnecting,
  };
}
