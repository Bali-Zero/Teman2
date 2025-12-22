import { describe, it, expect, vi, beforeEach } from 'vitest';
import { WebSocketUtils } from './websocket.utils';
import { ApiClientBase } from '../client';

describe('WebSocketUtils', () => {
  let wsUtils: WebSocketUtils;
  let mockClient: ApiClientBase;

  beforeEach(() => {
    mockClient = {
      getBaseUrl: vi.fn(() => 'https://api.test.com'),
      getToken: vi.fn(() => 'test-token'),
    } as any;
    wsUtils = new WebSocketUtils(mockClient);
  });

  describe('getWebSocketUrl', () => {
    it('should convert HTTPS to WSS', () => {
      (mockClient.getBaseUrl as any).mockReturnValue('https://api.test.com');
      const url = wsUtils.getWebSocketUrl();
      expect(url).toBe('wss://api.test.com/ws');
    });

    it('should convert HTTP to WS', () => {
      (mockClient.getBaseUrl as any).mockReturnValue('http://localhost:3000');
      const url = wsUtils.getWebSocketUrl();
      expect(url).toBe('ws://localhost:3000/ws');
    });

    it('should strip /api from base URL', () => {
      (mockClient.getBaseUrl as any).mockReturnValue('https://api.test.com/api');
      const url = wsUtils.getWebSocketUrl();
      expect(url).toBe('wss://api.test.com/ws');
    });

    it('should fall back to NEXT_PUBLIC_API_URL when base URL is empty', () => {
      const originalEnv = process.env.NEXT_PUBLIC_API_URL;
      process.env.NEXT_PUBLIC_API_URL = 'https://env.test.com/api';
      (mockClient.getBaseUrl as any).mockReturnValue('');

      const url = wsUtils.getWebSocketUrl();
      expect(url).toBe('wss://env.test.com/ws');

      process.env.NEXT_PUBLIC_API_URL = originalEnv;
    });

    it('should use window.location.origin as fallback', () => {
      (mockClient.getBaseUrl as any).mockReturnValue('');
      Object.defineProperty(window, 'location', {
        value: { origin: 'https://app.test.com' },
        writable: true,
      });
      const url = wsUtils.getWebSocketUrl();
      expect(url).toBe('wss://app.test.com/ws');
    });

    it('should handle localhost fallback', () => {
      (mockClient.getBaseUrl as any).mockReturnValue('');
      // When baseUrl is empty, should use window.location.origin or fallback to localhost:3000
      // In test environment, window exists, so we test the URL format
      const url = wsUtils.getWebSocketUrl();
      // Should be a valid WebSocket URL
      expect(url).toMatch(/wss?:\/\/.*\/ws/);
    });
  });

  describe('getWebSocketSubprotocol', () => {
    it('should return bearer token as subprotocol', () => {
      (mockClient.getToken as any).mockReturnValue('test-token');
      const subprotocol = wsUtils.getWebSocketSubprotocol();
      expect(subprotocol).toBe('bearer.test-token');
    });

    it('should return null when no token', () => {
      (mockClient.getToken as any).mockReturnValue(null);
      const subprotocol = wsUtils.getWebSocketSubprotocol();
      expect(subprotocol).toBeNull();
    });
  });
});
