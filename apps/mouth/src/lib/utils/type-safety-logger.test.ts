import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/lib/logger", () => ({
  logger: {
    info: vi.fn(),
    debug: vi.fn(),
    error: vi.fn(),
    warn: vi.fn(),
  },
}));

import {
  logTypeSafety,
  logTypeError,
  logMigrationProgress,
} from "./type-safety-logger";
import { logger } from "@/lib/logger";

const mockLogger = logger as unknown as {
  info: ReturnType<typeof vi.fn>;
  debug: ReturnType<typeof vi.fn>;
  error: ReturnType<typeof vi.fn>;
};

describe("logTypeSafety", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("logs any_replaced with info level", () => {
    logTypeSafety({
      file: "component.tsx",
      action: "any_replaced",
      type: "Record<string, unknown>",
    });
    expect(mockLogger.info).toHaveBeenCalledWith(
      "Type safety: `any` replaced with specific type",
      expect.objectContaining({
        component: "TypeSafety",
        action: "any_replaced",
      }),
    );
  });

  it("logs type_guard_added with debug level", () => {
    logTypeSafety({
      file: "utils.ts",
      action: "type_guard_added",
    });
    expect(mockLogger.debug).toHaveBeenCalledWith(
      "Type safety: Type guard added",
      expect.objectContaining({
        component: "TypeSafety",
        action: "type_guard_added",
      }),
    );
  });

  it("logs type_created with info level", () => {
    logTypeSafety({
      file: "types.ts",
      action: "type_created",
      type: "ClientProfile",
    });
    expect(mockLogger.info).toHaveBeenCalledWith(
      "Type safety: New type definition created",
      expect.any(Object),
    );
  });

  it("logs migration_completed with info level", () => {
    logTypeSafety({
      file: "migration.ts",
      action: "migration_completed",
    });
    expect(mockLogger.info).toHaveBeenCalledWith(
      "Type safety: Migration phase completed",
      expect.any(Object),
    );
  });
});

describe("logTypeError", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("logs error with Error instance", () => {
    const err = new Error("Type mismatch");
    logTypeError(err, { file: "broken.tsx", line: 42 });
    expect(mockLogger.error).toHaveBeenCalledWith(
      "Type safety: Type error detected",
      expect.objectContaining({
        component: "TypeSafety",
        action: "type_error",
        metadata: expect.objectContaining({
          file: "broken.tsx",
          line: 42,
          error: "Type mismatch",
        }),
      }),
      err,
    );
  });

  it("logs error with non-Error value", () => {
    logTypeError("string error", { file: "broken.tsx" });
    expect(mockLogger.error).toHaveBeenCalledWith(
      "Type safety: Type error detected",
      expect.objectContaining({
        metadata: expect.objectContaining({
          error: "string error",
        }),
      }),
      expect.any(Error),
    );
  });
});

describe("logMigrationProgress", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("logs migration progress with percentage", () => {
    logMigrationProgress("Phase 2", {
      completed: 15,
      total: 20,
      percentage: 75,
    });
    expect(mockLogger.info).toHaveBeenCalledWith(
      "Type safety: Migration progress",
      expect.objectContaining({
        metadata: expect.objectContaining({
          phase: "Phase 2",
          completed: 15,
          total: 20,
          percentage: "75.00",
        }),
      }),
    );
  });
});
