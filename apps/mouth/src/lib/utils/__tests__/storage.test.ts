import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { safeStorage, storage } from "../storage";
import { logger } from "../../logger";

// Mock logger
vi.mock("../../logger", () => ({
  logger: {
    warn: vi.fn(),
    debug: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}));

describe("SafeStorage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    // Reset safeStorage internal state
    safeStorage._resetForTesting();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("localStorage available", () => {
    it("should set and get item from localStorage", () => {
      const result = safeStorage.setItem("test-key", "test-value");

      expect(result).toBe(true);
      expect(safeStorage.getItem("test-key")).toBe("test-value");
      expect(localStorage.getItem("test-key")).toBe("test-value");
    });

    it("should remove item from localStorage", () => {
      safeStorage.setItem("test-key", "test-value");
      safeStorage.removeItem("test-key");

      expect(safeStorage.getItem("test-key")).toBeNull();
      expect(localStorage.getItem("test-key")).toBeNull();
    });

    it("should clear all items from localStorage", () => {
      safeStorage.setItem("key1", "value1");
      safeStorage.setItem("key2", "value2");

      safeStorage.clear();

      expect(safeStorage.getItem("key1")).toBeNull();
      expect(safeStorage.getItem("key2")).toBeNull();
      expect(localStorage.length).toBe(0);
    });

    it("should return true for isLocalStorageAvailable", () => {
      expect(safeStorage.isLocalStorageAvailable()).toBe(true);
    });

    it("should handle getting non-existent key", () => {
      expect(safeStorage.getItem("non-existent")).toBeNull();
    });

    it("should overwrite existing value", () => {
      safeStorage.setItem("key", "value1");
      safeStorage.setItem("key", "value2");

      expect(safeStorage.getItem("key")).toBe("value2");
    });
  });

  describe("SSR environment (no window)", () => {
    it("should handle SSR gracefully", () => {
      expect(safeStorage).toBeDefined();
      expect(safeStorage.getItem).toBeDefined();
      expect(safeStorage.setItem).toBeDefined();
    });
  });

  describe("backward compatible storage export", () => {
    it("should provide getItem method", () => {
      safeStorage.setItem("test", "value");
      expect(storage.getItem("test")).toBe("value");
    });

    it("should provide setItem method", () => {
      const result = storage.setItem("test", "value");
      expect(result).toBe(true);
      expect(storage.getItem("test")).toBe("value");
    });

    it("should provide removeItem method", () => {
      storage.setItem("test", "value");
      storage.removeItem("test");
      expect(storage.getItem("test")).toBeNull();
    });

    it("should provide clear method", () => {
      storage.setItem("key1", "value1");
      storage.setItem("key2", "value2");
      storage.clear();
      expect(storage.getItem("key1")).toBeNull();
      expect(storage.getItem("key2")).toBeNull();
    });

    it("should provide isAvailable method", () => {
      expect(typeof storage.isAvailable()).toBe("boolean");
    });
  });

  describe("edge cases", () => {
    it("should handle empty string as value", () => {
      safeStorage.setItem("empty", "");
      const value = safeStorage.getItem("empty");
      expect(value).toBe("");
    });

    it("should handle special characters in key", () => {
      const specialKey = "key-with-special_chars.123";
      safeStorage.setItem(specialKey, "value");
      expect(safeStorage.getItem(specialKey)).toBe("value");
    });

    it("should handle special characters in value", () => {
      const specialValue = "value with spaces and 特殊字符 and émojis 🎉";
      safeStorage.setItem("key", specialValue);
      expect(safeStorage.getItem("key")).toBe(specialValue);
    });

    it("should handle JSON strings", () => {
      const jsonValue = JSON.stringify({ foo: "bar", nested: { value: 123 } });
      safeStorage.setItem("json", jsonValue);
      expect(safeStorage.getItem("json")).toBe(jsonValue);
      expect(JSON.parse(safeStorage.getItem("json")!)).toEqual({
        foo: "bar",
        nested: { value: 123 },
      });
    });

    it("should handle large values", () => {
      const largeValue = "x".repeat(10000);
      safeStorage.setItem("large", largeValue);
      expect(safeStorage.getItem("large")).toBe(largeValue);
    });

    it("should handle multiple rapid operations", () => {
      for (let i = 0; i < 100; i++) {
        safeStorage.setItem(`key${i}`, `value${i}`);
      }

      for (let i = 0; i < 100; i++) {
        expect(safeStorage.getItem(`key${i}`)).toBe(`value${i}`);
      }

      safeStorage.clear();

      for (let i = 0; i < 100; i++) {
        expect(safeStorage.getItem(`key${i}`)).toBeNull();
      }
    });
  });

  describe("error handling at runtime", () => {
    it("should log warning when getItem fails at runtime", () => {
      // First set a value
      safeStorage.setItem("test", "value");

      // Mock localStorage.getItem to throw
      vi.spyOn(localStorage, "getItem").mockImplementation(() => {
        throw new Error("Storage error");
      });

      // This should catch the error and fall back to memory
      safeStorage.getItem("test");

      expect(logger.warn).toHaveBeenCalledWith(
        expect.stringContaining("getItem failed"),
        expect.any(Object),
        expect.any(Error),
      );
    });

    it("should log warning when removeItem fails at runtime", () => {
      vi.spyOn(localStorage, "removeItem").mockImplementation(() => {
        throw new Error("Storage error");
      });

      safeStorage.removeItem("test");

      expect(logger.warn).toHaveBeenCalledWith(
        expect.stringContaining("removeItem failed"),
        expect.any(Object),
        expect.any(Error),
      );
    });

    it("should log warning when clear fails at runtime", () => {
      vi.spyOn(localStorage, "clear").mockImplementation(() => {
        throw new Error("Storage error");
      });

      safeStorage.clear();

      expect(logger.warn).toHaveBeenCalledWith(
        expect.stringContaining("clear failed"),
        expect.any(Object),
        expect.any(Error),
      );
    });
  });
});
