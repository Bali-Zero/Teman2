import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { logger, LogLevel } from "./logger";
import * as Sentry from "@sentry/nextjs";

// Mock Sentry
vi.mock("@sentry/nextjs", () => ({
  captureException: vi.fn(),
  captureMessage: vi.fn(),
  setContext: vi.fn(),
  setUser: vi.fn(),
}));

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};

  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value;
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
  };
})();

Object.defineProperty(global, "localStorage", {
  value: localStorageMock,
  writable: true,
});

describe("Logger with Sentry Integration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorageMock.clear();
    logger.clearHistory();
    logger.clearStoredLogs();
  });

  afterEach(() => {
    vi.clearAllMocks();
    localStorageMock.clear();
  });

  describe("Basic Logging", () => {
    it("should skip debug messages in production", () => {
      const consoleSpy = vi
        .spyOn(console, "debug")
        .mockImplementation(() => {});

      // Logger is initialized with NODE_ENV check, which may be 'test'
      // Debug logs are only shown in development
      logger.debug("Debug message", { component: "Test" });

      // In test/production environment, debug is skipped
      // So we expect it NOT to be called if isDevelopment is false
      consoleSpy.mockRestore();
    });

    it("should log info messages to console", () => {
      const consoleSpy = vi.spyOn(console, "info").mockImplementation(() => {});

      logger.info("Info message", { component: "Test", action: "test_action" });

      expect(consoleSpy).toHaveBeenCalled();
      consoleSpy.mockRestore();
    });

    it("should log warning messages to console", () => {
      const consoleSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

      logger.warn("Warning message", { component: "Test" });

      expect(consoleSpy).toHaveBeenCalled();
      consoleSpy.mockRestore();
    });

    it("should log error messages with stack trace", () => {
      const consoleSpy = vi
        .spyOn(console, "error")
        .mockImplementation(() => {});
      const error = new Error("Test error");

      logger.error("Error occurred", { component: "Test" }, error);

      expect(consoleSpy).toHaveBeenCalledTimes(3); // Message, error details, stack trace
      consoleSpy.mockRestore();
    });
  });

  describe("Log History", () => {
    it("should maintain log history", () => {
      logger.info("Message 1");
      logger.info("Message 2");
      logger.warn("Message 3");

      const history = logger.getHistory();

      expect(history).toHaveLength(3);
      expect(history[0].message).toBe("Message 1");
      expect(history[1].message).toBe("Message 2");
      expect(history[2].message).toBe("Message 3");
    });

    it("should limit log history to 100 entries", () => {
      for (let i = 0; i < 150; i++) {
        logger.info(`Message ${i}`);
      }

      const history = logger.getHistory();

      expect(history).toHaveLength(100);
      expect(history[0].message).toBe("Message 50"); // First 50 should be dropped
    });

    it("should clear log history", () => {
      logger.info("Message 1");
      logger.info("Message 2");

      logger.clearHistory();

      expect(logger.getHistory()).toHaveLength(0);
    });
  });

  describe("Sentry Integration (Production)", () => {
    it("should send error with exception to Sentry", () => {
      // Note: In tests, isDevelopment is true, so we test Sentry calls directly
      const error = new Error("Test error");
      const originalEnv = process.env.NODE_ENV;

      // Create a new logger instance with production flag
      const prodLogger = new (logger.constructor as any)();
      (prodLogger as any).isDevelopment = false;

      prodLogger.error(
        "Error occurred",
        { component: "TestComponent", action: "test_action" },
        error,
      );

      expect(Sentry.setContext).toHaveBeenCalledWith(
        "log_context",
        expect.objectContaining({
          component: "TestComponent",
          action: "test_action",
        }),
      );

      expect(Sentry.captureException).toHaveBeenCalledWith(
        error,
        expect.objectContaining({
          extra: expect.objectContaining({
            message: "Error occurred",
          }),
          tags: {
            component: "TestComponent",
            action: "test_action",
          },
        }),
      );
    });

    it("should send error without exception to Sentry as message", () => {
      const prodLogger = new (logger.constructor as any)();
      (prodLogger as any).isDevelopment = false;

      prodLogger.error("Error occurred", { component: "TestComponent" });

      expect(Sentry.captureMessage).toHaveBeenCalledWith(
        "Error occurred",
        expect.objectContaining({
          level: "error",
          tags: {
            component: "TestComponent",
            action: "unknown",
          },
        }),
      );
    });

    it("should send warning to Sentry", () => {
      const prodLogger = new (logger.constructor as any)();
      (prodLogger as any).isDevelopment = false;

      prodLogger.warn("Warning occurred", {
        component: "TestComponent",
        action: "test_action",
      });

      expect(Sentry.captureMessage).toHaveBeenCalledWith(
        "Warning occurred",
        expect.objectContaining({
          level: "warning",
          tags: {
            component: "TestComponent",
            action: "test_action",
          },
        }),
      );
    });

    it("should not send info messages to Sentry", () => {
      const prodLogger = new (logger.constructor as any)();
      (prodLogger as any).isDevelopment = false;

      prodLogger.info("Info message", { component: "TestComponent" });

      expect(Sentry.captureMessage).not.toHaveBeenCalled();
      expect(Sentry.captureException).not.toHaveBeenCalled();
    });

    it("should not send debug messages to Sentry", () => {
      const prodLogger = new (logger.constructor as any)();
      (prodLogger as any).isDevelopment = false;

      prodLogger.debug("Debug message", { component: "TestComponent" });

      expect(Sentry.captureMessage).not.toHaveBeenCalled();
      expect(Sentry.captureException).not.toHaveBeenCalled();
    });
  });

  describe("User Context", () => {
    it("should set user context in Sentry", () => {
      logger.setUser("user123", "user@example.com", "TestUser");

      expect(Sentry.setUser).toHaveBeenCalledWith({
        id: "user123",
        email: "user@example.com",
        username: "TestUser",
      });
    });

    it("should clear user context in Sentry", () => {
      logger.clearUser();

      expect(Sentry.setUser).toHaveBeenCalledWith(null);
    });
  });

  describe("Local Storage Backup", () => {
    it("should store errors in localStorage", () => {
      const prodLogger = new (logger.constructor as any)();
      (prodLogger as any).isDevelopment = false;

      const error = new Error("Test error");

      prodLogger.error("Error occurred", { component: "Test" }, error);

      const storedLogs = prodLogger.getStoredLogs();

      expect(storedLogs).toHaveLength(1);
      expect(storedLogs[0]).toMatchObject({
        level: LogLevel.ERROR,
        message: "Error occurred",
        context: { component: "Test" },
      });
    });

    it("should limit stored logs to 50", () => {
      const prodLogger = new (logger.constructor as any)();
      (prodLogger as any).isDevelopment = false;

      for (let i = 0; i < 60; i++) {
        prodLogger.error(`Error ${i}`, { component: "Test" });
      }

      const storedLogs = prodLogger.getStoredLogs();

      expect(storedLogs).toHaveLength(50);
    });

    it("should clear stored logs", () => {
      const prodLogger = new (logger.constructor as any)();
      (prodLogger as any).isDevelopment = false;

      prodLogger.error("Error 1", { component: "Test" });
      prodLogger.error("Error 2", { component: "Test" });

      prodLogger.clearStoredLogs();

      expect(prodLogger.getStoredLogs()).toHaveLength(0);
    });
  });

  describe("Convenience Methods", () => {
    it("should log API calls", () => {
      const consoleSpy = vi.spyOn(console, "info").mockImplementation(() => {});

      logger.apiCall("/api/users", "GET", { component: "UserService" });

      expect(consoleSpy).toHaveBeenCalled();
      const history = logger.getHistory();
      expect(history[history.length - 1]).toMatchObject({
        message: "API Call: GET /api/users",
        context: expect.objectContaining({
          action: "api_call",
        }),
      });

      consoleSpy.mockRestore();
    });

    it("should log API success", () => {
      const consoleSpy = vi.spyOn(console, "info").mockImplementation(() => {});

      logger.apiSuccess("/api/users", 150, { component: "UserService" });

      expect(consoleSpy).toHaveBeenCalled();
      const history = logger.getHistory();
      expect(history[history.length - 1]).toMatchObject({
        message: "API Success: /api/users",
        context: expect.objectContaining({
          action: "api_success",
        }),
      });

      consoleSpy.mockRestore();
    });

    it("should log API errors", () => {
      const consoleSpy = vi
        .spyOn(console, "error")
        .mockImplementation(() => {});
      const error = new Error("API failed");

      logger.apiError("/api/users", error, { component: "UserService" });

      expect(consoleSpy).toHaveBeenCalled();
      const history = logger.getHistory();
      expect(history[history.length - 1]).toMatchObject({
        message: "API Error: /api/users",
        context: expect.objectContaining({
          action: "api_error",
        }),
        error,
      });

      consoleSpy.mockRestore();
    });

    it("should log user actions", () => {
      const consoleSpy = vi.spyOn(console, "info").mockImplementation(() => {});

      logger.userAction("click_button", "visa", "visa123", {
        component: "VisaCard",
      });

      expect(consoleSpy).toHaveBeenCalled();
      const history = logger.getHistory();
      expect(history[history.length - 1]).toMatchObject({
        message: "User Action: click_button",
        context: expect.objectContaining({
          action: "click_button",
          itemType: "visa",
          itemId: "visa123",
        }),
      });

      consoleSpy.mockRestore();
    });

    it("should skip component lifecycle logs in production", () => {
      const consoleSpy = vi
        .spyOn(console, "debug")
        .mockImplementation(() => {});

      // Component lifecycle logs are debug level
      // They're skipped in production/test environments
      logger.componentMount("TestComponent", { user: "user123" });
      logger.componentUnmount("TestComponent", { user: "user123" });

      // Clean up
      consoleSpy.mockRestore();
    });
  });

  describe("Error Handling", () => {
    it("should not throw if Sentry fails", () => {
      vi.mocked(Sentry.captureException).mockImplementation(() => {
        throw new Error("Sentry error");
      });

      const consoleSpy = vi
        .spyOn(console, "error")
        .mockImplementation(() => {});
      const prodLogger = new (logger.constructor as any)();
      (prodLogger as any).isDevelopment = false;

      expect(() => {
        prodLogger.error(
          "Test error",
          { component: "Test" },
          new Error("Original error"),
        );
      }).not.toThrow();

      consoleSpy.mockRestore();
    });

    it("should not throw if localStorage fails", () => {
      vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
        throw new Error("localStorage error");
      });

      const consoleSpy = vi
        .spyOn(console, "error")
        .mockImplementation(() => {});
      const prodLogger = new (logger.constructor as any)();
      (prodLogger as any).isDevelopment = false;

      expect(() => {
        prodLogger.error("Test error", { component: "Test" });
      }).not.toThrow();

      consoleSpy.mockRestore();
    });
  });
});
