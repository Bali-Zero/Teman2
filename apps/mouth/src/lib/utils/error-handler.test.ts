import { describe, it, expect, vi, beforeEach } from "vitest";

// vi.mock is hoisted — must use inline object, not external const
vi.mock("@/lib/logger", () => ({
  logger: {
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
  },
}));

import { handleError, handleApiError } from "./error-handler";
import { logger } from "@/lib/logger";

const mockLogger = logger as unknown as {
  error: ReturnType<typeof vi.fn>;
  warn: ReturnType<typeof vi.fn>;
  info: ReturnType<typeof vi.fn>;
  debug: ReturnType<typeof vi.fn>;
};

describe("handleError", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns error message from Error instance", () => {
    const err = new Error("something broke");
    const result = handleError(err, {
      component: "TestComponent",
      action: "test",
    });
    expect(result).toBe("something broke");
  });

  it("returns userMessage when provided", () => {
    const err = new Error("internal detail");
    const result = handleError(
      err,
      { component: "TestComponent", action: "test" },
      "Something went wrong, try again",
    );
    expect(result).toBe("Something went wrong, try again");
  });

  it("handles non-Error values (string)", () => {
    const result = handleError("raw string error", {
      component: "TestComponent",
      action: "test",
    });
    expect(result).toBe("raw string error");
  });

  it("logs the error with structured context", () => {
    const err = new Error("logged error");
    handleError(err, {
      component: "MyComponent",
      action: "save",
      metadata: { userId: 123 },
    });

    expect(mockLogger.error).toHaveBeenCalledWith(
      "Operation failed",
      expect.objectContaining({
        component: "MyComponent",
        action: "save",
        metadata: expect.objectContaining({
          userId: 123,
          errorName: "Error",
          errorMessage: "logged error",
        }),
      }),
      err,
    );
  });
});

describe("handleApiError", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("maps known error codes to user-friendly messages", () => {
    const err = Object.assign(new Error("timeout"), { code: "TIMEOUT" });
    const result = handleApiError(err, {
      component: "API",
      action: "fetch",
    });
    expect(result.message).toBe("Request timed out. Please try again.");
    expect(result.code).toBe("TIMEOUT");
  });

  it("uses defaultMessage for unknown error codes", () => {
    const err = Object.assign(new Error("unknown"), {
      code: "UNKNOWN_CODE",
    });
    const result = handleApiError(err, {
      component: "API",
      action: "fetch",
    });
    expect(result.message).toBe("An error occurred");
    expect(result.code).toBe("UNKNOWN_CODE");
  });

  it("uses custom default message", () => {
    const err = new Error("fail");
    const result = handleApiError(
      err,
      { component: "API", action: "fetch" },
      "Custom fallback",
    );
    expect(result.message).toBe("Custom fallback");
  });

  it("handles UNAUTHORIZED code", () => {
    const err = Object.assign(new Error("auth"), { code: "UNAUTHORIZED" });
    const result = handleApiError(err, {
      component: "API",
      action: "fetch",
    });
    expect(result.message).toBe("Authentication required. Please log in.");
  });

  it("returns undefined code when error has no code property", () => {
    const err = new Error("no code");
    const result = handleApiError(err, {
      component: "API",
      action: "fetch",
    });
    expect(result.code).toBeUndefined();
  });
});
