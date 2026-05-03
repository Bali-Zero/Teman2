/**
 * Centralized Error Handling Utility
 * Provides standardized error handling with structured logging
 */

import { logger } from "@/lib/logger";

export interface ErrorContext {
  component: string;
  action: string;
  metadata?: Record<string, unknown>;
}

/**
 * Handle errors with structured logging and optional user notification
 *
 * @param error - The error to handle
 * @param context - Context information (component, action, metadata)
 * @param userMessage - Optional user-friendly error message
 * @returns Formatted error message
 */
export function handleError(
  error: unknown,
  context: ErrorContext,
  userMessage?: string,
): string {
  const errorMessage = error instanceof Error ? error.message : String(error);
  const errorName = error instanceof Error ? error.name : "UnknownError";

  // Log error with structured context
  logger.error(
    userMessage || "Operation failed",
    {
      component: context.component,
      action: context.action,
      metadata: {
        ...context.metadata,
        errorName,
        errorMessage,
      },
    },
    error instanceof Error ? error : new Error(errorMessage),
  );

  // Return user-friendly message or fallback
  return userMessage || errorMessage;
}

/**
 * Handle API errors with specific error code handling
 */
export function handleApiError(
  error: unknown,
  context: ErrorContext,
  defaultMessage = "An error occurred",
): { message: string; code?: string } {
  const errorMessage = error instanceof Error ? error.message : String(error);

  // Extract error code if available
  const errorWithCode = error as Error & { code?: string };
  const code = errorWithCode.code;

  // Map common error codes to user-friendly messages
  const errorMessages: Record<string, string> = {
    TIMEOUT: "Request timed out. Please try again.",
    ABORTED: "Request was cancelled.",
    NETWORK_ERROR: "Network error. Please check your connection.",
    UNAUTHORIZED: "Authentication required. Please log in.",
    FORBIDDEN: "You do not have permission to perform this action.",
    NOT_FOUND: "Resource not found.",
    SERVER_ERROR: "Server error. Please try again later.",
  };

  const userMessage =
    code && errorMessages[code] ? errorMessages[code] : defaultMessage;

  handleError(error, context, userMessage);

  return {
    message: userMessage,
    code,
  };
}
