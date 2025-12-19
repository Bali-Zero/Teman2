import { ApiClientBase } from '../client';

/**
 * WebSocket utilities
 */
export class WebSocketUtils {
  constructor(private client: ApiClientBase) {}

  getWebSocketUrl(): string {
    // SECURITY: Return base URL only - token should be passed via subprotocol, not query param
    // This prevents token exposure in browser history and server logs
    const base =
      this.client.getBaseUrl() ||
      (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:3000');
    const wsUrl = base.replace('https://', 'wss://').replace('http://', 'ws://');
    return `${wsUrl}/ws`;
  }

  getWebSocketSubprotocol(): string | null {
    // SECURITY: Return token as subprotocol instead of query param
    const token = this.client.getToken();
    if (!token) return null;
    return `bearer.${token}`;
  }
}

