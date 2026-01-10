import type { IApiClient } from '../types/api-client.types';

/**
 * WebSocket utilities
 */
export class WebSocketUtils {
  constructor(private client: IApiClient) {}

  getWebSocketUrl(): string {
    const normalizeBaseUrl = (url: string): string => url.replace(/\/+$/, '').replace(/\/api$/, '');
    const isUsableBase = (value: string | undefined): value is string =>
      Boolean(value) && value !== 'undefined' && value !== 'null';
    
    const envBase = process.env.NEXT_PUBLIC_API_URL;
    const clientBase = this.client.getBaseUrl();
    const appUrl = process.env.NEXT_PUBLIC_APP_URL || 'https://zantara.balizero.com';
    
    // Determine the base URL
    const base =
      (isUsableBase(clientBase) ? clientBase : '') ||
      (isUsableBase(envBase) ? envBase : '') ||
      (typeof window !== 'undefined' && window.location?.origin
        ? window.location.origin
        : appUrl);

    let wsUrl: string;
    
    // CRITICAL: Next.js API Routes don't support WebSocket proxying.
    // If we're in production and using a relative /api path, we MUST point directly to the backend.
    if (base === '/api' || (typeof window !== 'undefined' && window.location.hostname === 'zantara.balizero.com')) {
      wsUrl = 'wss://nuzantara-rag.fly.dev';
    } else {
      const normalizedBase = normalizeBaseUrl(base);
      wsUrl = normalizedBase.replace('https://', 'wss://').replace('http://', 'ws://');
      
      // Handle relative paths
      if (!wsUrl.startsWith('ws')) {
        const protocol = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = typeof window !== 'undefined' ? window.location.host : 'nuzantara-rag.fly.dev';
        wsUrl = `${protocol}//${host}${wsUrl}`;
      }
    }

    return `${wsUrl}/ws`;
  }

  getWebSocketSubprotocol(): string | null {
    // SECURITY: Return token as subprotocol instead of query param
    const token = this.client.getToken();
    if (!token) return null;
    return `bearer.${token}`;
  }
}
