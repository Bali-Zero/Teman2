/**
 * Type Safety Logger
 * Provides structured logging for type safety operations
 */

import { logger } from "@/lib/logger";

export interface TypeSafetyLogContext {
  file: string;
  line?: number;
  type?: string;
  action:
    | "any_replaced"
    | "type_guard_added"
    | "type_created"
    | "migration_completed";
  metadata?: Record<string, unknown>;
}

/**
 * Log type safety operation
 */
export function logTypeSafety(context: TypeSafetyLogContext): void {
  const { file, line, type, action, metadata } = context;

  const logMetadata = {
    component: "TypeSafety",
    action,
    metadata: {
      file,
      ...(line && { line }),
      ...(type && { type }),
      ...metadata,
    },
  };

  switch (action) {
    case "any_replaced":
      logger.info(
        "Type safety: `any` replaced with specific type",
        logMetadata,
      );
      break;
    case "type_guard_added":
      logger.debug("Type safety: Type guard added", logMetadata);
      break;
    case "type_created":
      logger.info("Type safety: New type definition created", logMetadata);
      break;
    case "migration_completed":
      logger.info("Type safety: Migration phase completed", logMetadata);
      break;
    default:
      logger.debug("Type safety: Operation logged", logMetadata);
  }
}

/**
 * Log type error (for monitoring)
 */
export function logTypeError(
  error: unknown,
  context: { file: string; line?: number },
): void {
  logger.error(
    "Type safety: Type error detected",
    {
      component: "TypeSafety",
      action: "type_error",
      metadata: {
        file: context.file,
        ...(context.line && { line: context.line }),
        error: error instanceof Error ? error.message : String(error),
      },
    },
    error instanceof Error ? error : new Error(String(error)),
  );
}

/**
 * Log migration progress
 */
export function logMigrationProgress(
  phase: string,
  progress: { completed: number; total: number; percentage: number },
): void {
  logger.info("Type safety: Migration progress", {
    component: "TypeSafety",
    action: "migration_progress",
    metadata: {
      phase,
      completed: progress.completed,
      total: progress.total,
      percentage: progress.percentage.toFixed(2),
    },
  });
}
