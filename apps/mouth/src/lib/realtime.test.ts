/**
 * Tests for RealtimeService WebSocket authentication
 * Tests the fix for WebSocket auth token handling
 */

import {
  describe,
  it,
  expect,
  vi,
  beforeEach,
  afterEach,
  MockInstance,
} from "vitest";

// Mock the logger before importing the module
vi.mock("./logger", () => ({
  logger: {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
  },
}));

// Mock WebSocket
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  readyState = MockWebSocket.CONNECTING;
  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;

  url: string;
  protocols: string | string[] | undefined;

  constructor(url: string, protocols?: string | string[]) {
    this.url = url;
    this.protocols = protocols;
  }

  send = vi.fn();
  close = vi.fn();
}

// Setup globals
(global as any).WebSocket = MockWebSocket;

// Mock localStorage
const createLocalStorageMock = () => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
    _setStore: (newStore: Record<string, string>) => {
      store = newStore;
    },
  };
};

const localStorageMock = createLocalStorageMock();

// Mock sessionStorage
const sessionStorageMock = createLocalStorageMock();

Object.defineProperty(global, "localStorage", {
  value: localStorageMock,
  writable: true,
});
Object.defineProperty(global, "sessionStorage", {
  value: sessionStorageMock,
  writable: true,
});

// Mock window
Object.defineProperty(global, "window", {
  value: {
    location: { pathname: "/dashboard" },
    addEventListener: vi.fn(),
    localStorage: localStorageMock,
    sessionStorage: sessionStorageMock,
  },
  writable: true,
});

// Mock document
Object.defineProperty(global, "document", {
  value: {
    addEventListener: vi.fn(),
    hidden: false,
  },
  writable: true,
});

describe("RealtimeService WebSocket Auth", () => {
  let webSocketInstances: MockWebSocket[];
  let originalWebSocket: typeof WebSocket;

  beforeEach(() => {
    webSocketInstances = [];
    originalWebSocket = (global as any).WebSocket;

    // Track all WebSocket instances
    (global as any).WebSocket = class extends MockWebSocket {
      constructor(url: string, protocols?: string | string[]) {
        super(url, protocols);
        webSocketInstances.push(this);
      }
    };

    localStorageMock.clear();
    sessionStorageMock.clear();
    vi.clearAllMocks();
  });

  afterEach(() => {
    (global as any).WebSocket = originalWebSocket;
    vi.restoreAllMocks();
    // Reset module state
    vi.resetModules();
  });

  describe("Token-based authentication", () => {
    it("should not connect when no auth token available", async () => {
      // Import fresh instance
      const { realtimeService } = await import("./realtime");

      // Ensure no token
      localStorageMock.clear();
      sessionStorageMock.clear();

      // Attempt to connect
      await realtimeService.connect("user-123", "Test User");

      // Should NOT create WebSocket without token
      expect(webSocketInstances).toHaveLength(0);
    });

    it("should connect with JWT token from localStorage", async () => {
      // Set a valid JWT token (3 parts separated by dots, > 50 chars)
      const validJwt =
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c";
      localStorageMock.setItem("auth_token", validJwt);

      const { realtimeService } = await import("./realtime");

      await realtimeService.connect("user-123", "Test User");

      // Should create WebSocket with token in subprotocol
      expect(webSocketInstances).toHaveLength(1);
      expect(webSocketInstances[0].protocols).toContain(`bearer.${validJwt}`);
    });

    it("should try sessionStorage as fallback when localStorage empty", async () => {
      const validJwt =
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c";

      // Only in sessionStorage
      localStorageMock.clear();
      sessionStorageMock.setItem("auth_token", validJwt);

      const { realtimeService } = await import("./realtime");

      await realtimeService.connect("user-123", "Test User");

      expect(webSocketInstances).toHaveLength(1);
      expect(webSocketInstances[0].protocols).toContain(`bearer.${validJwt}`);
    });

    it("should reject invalid token format (not 3 parts)", async () => {
      // Invalid: only 2 parts
      localStorageMock.setItem("auth_token", "invalid.token");

      const { realtimeService } = await import("./realtime");

      await realtimeService.connect("user-123", "Test User");

      // Should NOT create WebSocket with invalid token
      expect(webSocketInstances).toHaveLength(0);
    });

    it("should reject token too short (< 50 chars)", async () => {
      // Valid format but too short
      localStorageMock.setItem("auth_token", "a.b.c");

      const { realtimeService } = await import("./realtime");

      await realtimeService.connect("user-123", "Test User");

      // Should NOT create WebSocket with short token
      expect(webSocketInstances).toHaveLength(0);
    });

    it("should use correct WebSocket URL", async () => {
      const validJwt =
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c";
      localStorageMock.setItem("auth_token", validJwt);

      const { realtimeService } = await import("./realtime");

      await realtimeService.connect("user-123", "Test User");

      // Should use default or env WebSocket URL
      expect(webSocketInstances[0].url).toContain("wss://");
    });
  });

  describe("Reconnection behavior", () => {
    it("should not attempt reconnect when no token available", async () => {
      localStorageMock.clear();

      const { realtimeService } = await import("./realtime");

      // Try to connect - should fail silently
      await realtimeService.connect("user-123", "Test User");

      expect(webSocketInstances).toHaveLength(0);

      // Reconnect attempts should be maxed out
      // (internal state prevents infinite loops)
    });

    it("should not create duplicate connections", async () => {
      const validJwt =
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c";
      localStorageMock.setItem("auth_token", validJwt);

      const { realtimeService } = await import("./realtime");

      // First connection
      await realtimeService.connect("user-123", "Test User");

      // Simulate connection open
      webSocketInstances[0].readyState = MockWebSocket.OPEN;
      if (webSocketInstances[0].onopen) {
        webSocketInstances[0].onopen(new Event("open"));
      }

      // Try to connect again (should be ignored)
      await realtimeService.connect("user-123", "Test User");

      // Should still only have 1 WebSocket instance
      expect(webSocketInstances).toHaveLength(1);
    });
  });

  describe("Connection status", () => {
    it("should report not connected when WebSocket is null", async () => {
      const { realtimeService } = await import("./realtime");

      expect(realtimeService.isConnected()).toBe(false);
    });

    it("should report connected when WebSocket is OPEN", async () => {
      const validJwt =
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c";
      localStorageMock.setItem("auth_token", validJwt);

      const { realtimeService } = await import("./realtime");

      await realtimeService.connect("user-123", "Test User");

      // Simulate connection open
      webSocketInstances[0].readyState = MockWebSocket.OPEN;
      if (webSocketInstances[0].onopen) {
        webSocketInstances[0].onopen(new Event("open"));
      }

      expect(realtimeService.isConnected()).toBe(true);
    });
  });

  describe("Subscription management", () => {
    it("should allow subscribing to message types", async () => {
      const { realtimeService } = await import("./realtime");

      const callback = vi.fn();
      const unsubscribe = realtimeService.subscribe(
        "dashboard_update",
        callback,
      );

      expect(typeof unsubscribe).toBe("function");
    });

    it("should call subscriber when message received", async () => {
      const validJwt =
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c";
      localStorageMock.setItem("auth_token", validJwt);

      const { realtimeService } = await import("./realtime");

      const callback = vi.fn();
      realtimeService.subscribe("dashboard_update", callback);

      await realtimeService.connect("user-123", "Test User");

      // Simulate receiving a message
      if (webSocketInstances[0].onmessage) {
        webSocketInstances[0].onmessage(
          new MessageEvent("message", {
            data: JSON.stringify({
              type: "dashboard_update",
              data: { action: "create" },
              timestamp: new Date().toISOString(),
              userId: "user-456",
              userName: "Other User",
            }),
          }),
        );
      }

      expect(callback).toHaveBeenCalledWith({ action: "create" });
    });

    it("should unsubscribe correctly", async () => {
      const { realtimeService } = await import("./realtime");

      const callback = vi.fn();
      const unsubscribe = realtimeService.subscribe(
        "dashboard_update",
        callback,
      );

      unsubscribe();

      // Callback should no longer be called for messages after unsubscribe
      // (This would require setting up a connection to fully test)
    });
  });

  describe("Disconnect behavior", () => {
    it("should close WebSocket on disconnect", async () => {
      const validJwt =
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c";
      localStorageMock.setItem("auth_token", validJwt);

      const { realtimeService } = await import("./realtime");

      await realtimeService.connect("user-123", "Test User");
      webSocketInstances[0].readyState = MockWebSocket.OPEN;

      realtimeService.disconnect();

      expect(webSocketInstances[0].close).toHaveBeenCalled();
    });
  });
});
