/**
 * API Error Handler
 *
 * Centralized error handling for API calls
 */

import { createLogger } from "../utils/console";

const logger = createLogger("API");

export class ApiError extends Error {
  /**
   * Backend-supplied `detail` (FastAPI convention) and machine-readable `code`,
   * lifted out of the response body so callers do not have to re-parse `data`.
   *
   * These two fields exist because `lib/api/index.ts` used to declare a SECOND,
   * competing `ApiError` — a structural interface carrying `detail`/`code` but no
   * status — while this class carried `statusCode` and was never thrown by
   * anything. Consumers imported the interface, found no status on it, and fell
   * back to sniffing substrings out of `error.message`. The two types are now one,
   * and this class is a superset of what that interface promised.
   */
  readonly detail?: string;
  readonly code?: string;

  constructor(
    message: string,
    public statusCode: number,
    public data?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
    const body = data as { detail?: unknown; code?: unknown } | undefined;
    if (typeof body?.detail === "string") this.detail = body.detail;
    if (typeof body?.code === "string") this.code = body.code;
  }
}

/**
 * Handle API errors consistently
 */
export function handleApiError(error: unknown): ApiError {
  if (error instanceof ApiError) {
    return error;
  }

  if (error instanceof Response) {
    const status = error.status;
    const message = getErrorMessageForStatus(status);
    return new ApiError(message, status);
  }

  if (error instanceof Error) {
    logger.error("API Error:", error.message);
    return new ApiError(error.message, 0);
  }

  logger.error("Unknown API Error:", error);
  return new ApiError("An unexpected error occurred", 0);
}

function getErrorMessageForStatus(status: number): string {
  switch (status) {
    case 400:
      return "Invalid request. Please check your input.";
    case 401:
      return "You need to sign in to access this resource.";
    case 403:
      return "You do not have permission to access this resource.";
    case 404:
      return "The requested resource was not found.";
    case 409:
      return "This action conflicts with existing data.";
    case 422:
      return "Validation failed. Please check your input.";
    case 429:
      return "Too many requests. Please try again later.";
    case 500:
      return "A server error occurred. Please try again later.";
    case 503:
      return "Service temporarily unavailable. Please try again later.";
    default:
      return "An error occurred while processing your request.";
  }
}

/**
 * Safe fetch wrapper with error handling
 */
export async function safeFetch<T>(
  url: string,
  options?: RequestInit,
): Promise<T> {
  try {
    const response = await fetch(url, options);

    if (!response.ok) {
      throw response;
    }

    return await response.json();
  } catch (error) {
    throw handleApiError(error);
  }
}

/**
 * Retry fetch with exponential backoff
 */
export async function retryFetch<T>(
  url: string,
  options?: RequestInit,
  maxRetries = 3,
): Promise<T> {
  let lastError: Error | undefined;

  for (let i = 0; i < maxRetries; i++) {
    try {
      return await safeFetch<T>(url, options);
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));

      // Don't retry on 4xx errors (client errors)
      if (
        error instanceof ApiError &&
        error.statusCode >= 400 &&
        error.statusCode < 500
      ) {
        throw error;
      }

      // Wait before retrying (exponential backoff)
      if (i < maxRetries - 1) {
        await new Promise((resolve) =>
          setTimeout(resolve, Math.pow(2, i) * 1000),
        );
      }
    }
  }

  throw lastError;
}
