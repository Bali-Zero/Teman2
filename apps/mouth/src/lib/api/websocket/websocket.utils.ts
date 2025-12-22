import { ApiClientBase } from '../client';

/**
 * WebSocket utilities
 */
export class WebSocketUtils {
  constructor(private client: ApiClientBase) {}

  getWebSocketUrl(): string {
    // SECURITY: Return base URL only - token should be passed via subprotocol, not query param
    // This prevents token exposure in browser history and server logs
    const normalizeBaseUrl = (url: string): string => url.replace(/\/+$/, '').replace(/\/api$/, '');
    const isUsableBase = (value: string | undefined): value is string =>
      Boolean(value) && value !== 'undefined' && value !== 'null';
    const envBase = process.env.NEXT_PUBLIC_API_URL;
    const clientBase = this.client.getBaseUrl();
    const base =
      (isUsableBase(clientBase) ? clientBase : '') ||
      (isUsableBase(envBase) ? envBase : '') ||
      (typeof window !== 'undefined' && window.location?.origin
        ? window.location.origin
        : 'http://localhost:3000');
    const normalizedBase = normalizeBaseUrl(base);
    const wsUrl = normalizedBase.replace('https://', 'wss://').replace('http://', 'ws://');
    return `${wsUrl}/ws`;
  }

  getWebSocketSubprotocol(): string | null {
    // SECURITY: Return token as subprotocol instead of query param
    const token = this.client.getToken();
    if (!token) return null;
    return `bearer.${token}`;
  }
}
