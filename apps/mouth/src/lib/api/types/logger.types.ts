/**
 * Logger types
 * Type-safe definitions for logging parameters
 */

/**
 * API request parameters
 */
export interface ApiRequestParams {
  [key: string]:
    | string
    | number
    | boolean
    | null
    | undefined
    | string[]
    | number[];
}

/**
 * Error info structure
 */
export interface ErrorInfo {
  componentStack?: string;
  errorBoundary?: string;
  errorBoundaryName?: string;
  errorBoundaryInfo?: unknown;
  [key: string]: unknown;
}

/**
 * Log metadata
 */
export interface LogMetadata {
  [key: string]: string | number | boolean | null | undefined | unknown;
}

/**
 * Type guard for ApiRequestParams
 */
export function isApiRequestParams(value: unknown): value is ApiRequestParams {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const params = value as Record<string, unknown>;
  return Object.values(params).every(
    (v) =>
      typeof v === "string" ||
      typeof v === "number" ||
      typeof v === "boolean" ||
      v === null ||
      v === undefined ||
      Array.isArray(v),
  );
}

/**
 * Type guard for ErrorInfo
 */
export function isErrorInfo(value: unknown): value is ErrorInfo {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  // ErrorInfo is flexible, just check it's an object
  return true;
}
