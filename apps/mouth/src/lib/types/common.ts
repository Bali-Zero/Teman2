/**
 * Common TypeScript types to replace `any` usage
 * These types provide better type safety while maintaining flexibility
 */

/**
 * JSON-serializable object (replaces Record<string, any>)
 * Use when you need a flexible object structure that can be serialized
 */
export type JsonObject = Record<string, unknown>;

/**
 * String-keyed record with unknown values (safer than Record<string, any>)
 * Use when you know keys are strings but values can be anything
 */
export type StringRecord = Record<string, unknown>;

/**
 * JSON-serializable value (can be object, array, string, number, boolean, null, undefined)
 * Note: undefined is included for optional fields in objects
 */
export type JsonValue =
  | string
  | number
  | boolean
  | null
  | undefined
  | JsonObject
  | JsonValue[];

/**
 * Generic error type (replaces error: any in catch blocks)
 * Always use `unknown` for catch clauses, then narrow with type guards
 */
export type ErrorLike =
  | Error
  | { message?: string; name?: string; stack?: string };

/**
 * Type guard to check if value is an Error
 */
export function isError(value: unknown): value is Error {
  return (
    value instanceof Error ||
    (typeof value === "object" && value !== null && "message" in value)
  );
}

/**
 * Convert unknown error to Error instance
 */
export function toError(error: unknown): Error {
  if (isError(error)) {
    return error;
  }
  if (typeof error === "string") {
    return new Error(error);
  }
  if (typeof error === "object" && error !== null && "message" in error) {
    return new Error(
      String((error as { message?: unknown }).message || "Unknown error"),
    );
  }
  return new Error("Unknown error");
}

/**
 * Metadata object for logging/analytics (replaces Record<string, any>)
 * Allows undefined values for optional fields
 */
export type Metadata = Record<string, JsonValue | undefined>;

/**
 * Properties object for analytics events
 */
export type AnalyticsProperties = Record<
  string,
  string | number | boolean | null | undefined
>;

/**
 * Configuration object (replaces Record<string, any>)
 */
export type ConfigObject = Record<string, JsonValue>;

/**
 * API Response wrapper type
 */
export interface ApiResponse<T = unknown> {
  data?: T;
  error?: string;
  message?: string;
  status: number;
}

/**
 * Pagination metadata
 */
export interface PaginationMeta {
  page: number;
  limit: number;
  total: number;
  totalPages: number;
  hasMore: boolean;
}

/**
 * Paginated response
 */
export interface PaginatedResponse<T> {
  data: T[];
  meta: PaginationMeta;
}

/**
 * Search result item
 */
export interface SearchResult {
  id: string;
  title: string;
  description?: string;
  url?: string;
  score?: number;
  metadata?: Metadata;
}

/**
 * Select option for dropdowns
 */
export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

/**
 * File with metadata
 */
export interface FileWithMeta {
  id: string;
  name: string;
  size?: number;
  type?: string;
  url?: string;
  createdAt?: string;
  updatedAt?: string;
  metadata?: Metadata;
}

/**
 * User info
 */
export interface UserInfo {
  id: string;
  email: string;
  name?: string;
  avatar?: string;
  role?: string;
  permissions?: string[];
}

/**
 * Navigation item
 */
export interface NavItem {
  label: string;
  href: string;
  icon?: string;
  active?: boolean;
  children?: NavItem[];
}

/**
 * Form field error
 */
export interface FieldError {
  field: string;
  message: string;
}

/**
 * Validation result
 */
export interface ValidationResult {
  valid: boolean;
  errors: FieldError[];
}
