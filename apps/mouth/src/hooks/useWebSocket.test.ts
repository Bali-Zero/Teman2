import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useWebSocket } from './useWebSocket';

// Mock api
const mockGetToken = vi.fn();
vi.mock('@/lib/api', () => ({
  api: {
    getToken: () => mockGetToken(),
  },
}));

// Mock WebSocket
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  url: string;
  protocol: string = ''; // SECURITY: Subprotocol for token authentication
  readyState: number = MockWebSocket.CONNECTING;
  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  static instances: MockWebSocket[] = [];

  constructor(url: string, protocols?: string | string[]) {
    this.url = url;
    // SECURITY: Store subprotocol (token authentication)
    if (protocols) {
      this.protocol = Array.isArray(protocols) ? protocols[0] : protocols;
    }
    MockWebSocket.instances.push(this);
  }

  send = vi.fn();
  close = vi.fn(() => {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent('close'));
    }
  });

  simulateOpen() {
    this.readyState = MockWebSocket.OPEN;
    if (this.onopen) {
      this.onopen(new Event('open'));
    }
  }

  simulateMessage(data: unknown) {
    if (this.onmessage) {
      this.onmessage(new MessageEvent('message', { data: JSON.stringify(data) }));
    }
  }

  simulateError() {
    if (this.onerror) {
      this.onerror(new Event('error'));
    }
  }

  simulateClose() {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent('close'));
    }
  }
}

// Replace global WebSocket
const originalWebSocket = global.WebSocket;
beforeEach(() => {
  MockWebSocket.instances = [];
  // @ts-expect-error - mock WebSocket
  global.WebSocket = MockWebSocket;
  vi.useFakeTimers();
});

afterEach(() => {
  global.WebSocket = originalWebSocket;
  vi.useRealTimers();
  vi.clearAllMocks();
});

describe('useWebSocket', () => {
  describe('Initial state', () => {
    it('should start disconnected', () => {
      mockGetToken.mockReturnValue('test-token');

      const { result } = renderHook(() => useWebSocket());

      expect(result.current.isConnected).toBe(false);
      expect(result.current.isConnecting).toBe(false);
    });

    it('should provide connect, disconnect, and send functions', () => {
      mockGetToken.mockReturnValue('test-token');

      const { result } = renderHook(() => useWebSocket());

      expect(typeof result.current.connect).toBe('function');
      expect(typeof result.current.disconnect).toBe('function');
      expect(typeof result.current.send).toBe('function');
    });
  });

  describe('connect', () => {
    it('should not connect without auth token', () => {
      mockGetToken.mockReturnValue(null);
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

      const { result } = renderHook(() => useWebSocket());
      act(() => {
        result.current.connect();
      });

      expect(MockWebSocket.instances.length).toBe(0);
      expect(consoleSpy).toHaveBeenCalledWith('No auth token for WebSocket');
      consoleSpy.mockRestore();
    });

    it('should create WebSocket connection with token in subprotocol (not URL)', () => {
      mockGetToken.mockReturnValue('test-token');

      const { result } = renderHook(() => useWebSocket());
      act(() => {
        result.current.connect();
      });

      expect(MockWebSocket.instances.length).toBe(1);
      // SECURITY: Token should NOT be in URL
      expect(MockWebSocket.instances[0].url).not.toContain('token=test-token');
      expect(MockWebSocket.instances[0].url).not.toContain('?token=');
      // SECURITY: Token should be in subprotocol
      expect(MockWebSocket.instances[0].protocol).toBe('bearer.test-token');
    });

    it('should set isConnecting to true while connecting', () => {
      mockGetToken.mockReturnValue('test-token');

      const { result } = renderHook(() => useWebSocket());
      act(() => {
        result.current.connect();
      });

      expect(result.current.isConnecting).toBe(true);
    });

    it('should set isConnected to true when WebSocket opens', async () => {
      mockGetToken.mockReturnValue('test-token');

      const { result } = renderHook(() => useWebSocket());
      act(() => {
        result.current.connect();
      });

      const ws = MockWebSocket.instances[0];
      act(() => {
        ws.simulateOpen();
      });

      expect(result.current.isConnected).toBe(true);
      expect(result.current.isConnecting).toBe(false);
    });

    it('should call onConnect callback when connected', async () => {
      mockGetToken.mockReturnValue('test-token');
      const onConnect = vi.fn();

      const { result } = renderHook(() => useWebSocket({ onConnect }));
      act(() => {
        result.current.connect();
      });

      const ws = MockWebSocket.instances[0];
      act(() => {
        ws.simulateOpen();
      });

      expect(onConnect).toHaveBeenCalled();
    });

    it('should not create new connection if already connected', () => {
      mockGetToken.mockReturnValue('test-token');

      const { result } = renderHook(() => useWebSocket());
      act(() => {
        result.current.connect();
      });

      const ws = MockWebSocket.instances[0];
      act(() => {
        ws.simulateOpen();
      });

      act(() => {
        result.current.connect();
      });

      expect(MockWebSocket.instances.length).toBe(1);
    });
  });

  describe('messages', () => {
    it('should call onMessage when receiving a message', () => {
      mockGetToken.mockReturnValue('test-token');
      const onMessage = vi.fn();

      const { result } = renderHook(() => useWebSocket({ onMessage }));
      act(() => {
        result.current.connect();
      });

      const ws = MockWebSocket.instances[0];
      act(() => {
        ws.simulateOpen();
        ws.simulateMessage({ type: 'test', content: 'Hello' });
      });

      expect(onMessage).toHaveBeenCalledWith({ type: 'test', content: 'Hello' });
    });

    it('should handle invalid JSON messages gracefully', () => {
      mockGetToken.mockReturnValue('test-token');
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      const onMessage = vi.fn();

      const { result } = renderHook(() => useWebSocket({ onMessage }));
      act(() => {
        result.current.connect();
      });

      const ws = MockWebSocket.instances[0];
      act(() => {
        ws.simulateOpen();
        // Simulate invalid JSON
        if (ws.onmessage) {
          ws.onmessage(new MessageEvent('message', { data: 'invalid json' }));
        }
      });

      expect(onMessage).not.toHaveBeenCalled();
      expect(consoleSpy).toHaveBeenCalled();
      consoleSpy.mockRestore();
    });
  });

  describe('send', () => {
    it('should send data when connected', () => {
      mockGetToken.mockReturnValue('test-token');

      const { result } = renderHook(() => useWebSocket());
      act(() => {
        result.current.connect();
      });

      const ws = MockWebSocket.instances[0];
      act(() => {
        ws.simulateOpen();
      });

      let success: boolean = false;
      act(() => {
        success = result.current.send({ type: 'test', message: 'hello' });
      });

      expect(success).toBe(true);
      expect(ws.send).toHaveBeenCalledWith(JSON.stringify({ type: 'test', message: 'hello' }));
    });

    it('should return false when trying to send while disconnected', () => {
      mockGetToken.mockReturnValue('test-token');
      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

      const { result } = renderHook(() => useWebSocket());

      let success: boolean = true;
      act(() => {
        success = result.current.send({ type: 'test' });
      });

      expect(success).toBe(false);
      expect(consoleSpy).toHaveBeenCalledWith('WebSocket not connected');
      consoleSpy.mockRestore();
    });
  });

  describe('disconnect', () => {
    it('should close WebSocket connection', () => {
      mockGetToken.mockReturnValue('test-token');
      const consoleSpy = vi.spyOn(console, 'log').mockImplementation(() => {});

      const { result } = renderHook(() => useWebSocket());
      act(() => {
        result.current.connect();
      });

      const ws = MockWebSocket.instances[0];
      act(() => {
        ws.simulateOpen();
      });

      act(() => {
        result.current.disconnect();
      });

      expect(ws.close).toHaveBeenCalled();
      expect(result.current.isConnected).toBe(false);
      consoleSpy.mockRestore();
    });

    it('should handle disconnect when connection closes before opening', () => {
      mockGetToken.mockReturnValue('test-token');
      const consoleSpy = vi.spyOn(console, 'log').mockImplementation(() => {});
      const onDisconnect = vi.fn();

      const { result } = renderHook(() => useWebSocket({ onDisconnect }));
      act(() => {
        result.current.connect();
      });

      const ws = MockWebSocket.instances[0];
      // Close before the connection fully opens (the onclose handler at line 91 is still active)
      act(() => {
        ws.readyState = MockWebSocket.CLOSED;
        if (ws.onclose) {
          ws.onclose(new CloseEvent('close'));
        }
      });

      expect(onDisconnect).toHaveBeenCalled();
      consoleSpy.mockRestore();
    });
  });

  describe('error handling', () => {
    it('should call onError callback on WebSocket error', () => {
      mockGetToken.mockReturnValue('test-token');
      const onError = vi.fn();

      const { result } = renderHook(() => useWebSocket({ onError }));
      act(() => {
        result.current.connect();
      });

      const ws = MockWebSocket.instances[0];
      act(() => {
        ws.simulateError();
      });

      expect(onError).toHaveBeenCalled();
      expect(result.current.isConnecting).toBe(false);
    });
  });

  describe('reconnection', () => {
    it('should schedule reconnect when connection fails before opening', async () => {
      mockGetToken.mockReturnValue('test-token');

      const { result } = renderHook(() =>
        useWebSocket({
          reconnectInterval: 1000,
          maxReconnectAttempts: 3,
        })
      );

      act(() => {
        result.current.connect();
      });

      const firstWs = MockWebSocket.instances[0];
      // Close before opening (simulating connection failure)
      // The onclose handler at line 91 is still active
      act(() => {
        firstWs.readyState = MockWebSocket.CLOSED;
        if (firstWs.onclose) {
          firstWs.onclose(new CloseEvent('close'));
        }
      });

      // The reconnect should have been scheduled - advance timers and verify a new socket is created
      expect(MockWebSocket.instances.length).toBe(1);
      act(() => {
        vi.advanceTimersByTime(1000);
      });
      expect(MockWebSocket.instances.length).toBe(2);
    });

    it('should prevent reconnect when explicitly disconnected', () => {
      mockGetToken.mockReturnValue('test-token');
      const consoleSpy = vi.spyOn(console, 'log').mockImplementation(() => {});

      const { result } = renderHook(() =>
        useWebSocket({
          reconnectInterval: 1000,
          maxReconnectAttempts: 3,
        })
      );

      act(() => {
        result.current.connect();
      });

      const ws = MockWebSocket.instances[0];
      const instancesBeforeDisconnect = MockWebSocket.instances.length;

      act(() => {
        ws.simulateOpen();
      });

      act(() => {
        result.current.disconnect();
      });

      act(() => {
        vi.advanceTimersByTime(5000);
      });

      // Should only have the original connection (no reconnects attempted)
      expect(MockWebSocket.instances.length).toBe(instancesBeforeDisconnect);
      consoleSpy.mockRestore();
    });
  });

  describe('ping/pong', () => {
    it('should send ping messages periodically', () => {
      mockGetToken.mockReturnValue('test-token');

      const { result } = renderHook(() => useWebSocket());
      act(() => {
        result.current.connect();
      });

      const ws = MockWebSocket.instances[0];
      act(() => {
        ws.simulateOpen();
      });

      // Advance past ping interval
      act(() => {
        vi.advanceTimersByTime(30000);
      });

      expect(ws.send).toHaveBeenCalledWith(JSON.stringify({ type: 'ping' }));
    });
  });

  describe('cleanup', () => {
    it('should disconnect on unmount', () => {
      mockGetToken.mockReturnValue('test-token');

      const { result, unmount } = renderHook(() => useWebSocket());
      act(() => {
        result.current.connect();
      });

      const ws = MockWebSocket.instances[0];
      act(() => {
        ws.simulateOpen();
      });

      unmount();

      expect(ws.close).toHaveBeenCalled();
    });
  });
});
