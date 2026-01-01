/**
 * API Client Interface and Types
 * Provides type-safe contracts for API client implementations
 */

import { UserProfile } from '@/types';

/**
 * HTTP request options
 */
export interface ApiRequestOptions extends Omit<RequestInit, 'headers'> {
  headers?: Record<string, string>;
}

/**
 * Interface for API client implementations.
 * Domain APIs depend on this interface, not concrete implementations.
 */
export interface IApiClient {
  /**
   * Make an HTTP request to the backend API.
   * @param endpoint - API endpoint path (e.g., '/api/auth/login')
   * @param options - Request options (method, body, headers)
   * @param timeoutMs - Request timeout in milliseconds (default: 30000)
   * @returns Promise resolving to typed response
   */
  request<T>(
    endpoint: string,
    options?: ApiRequestOptions,
    timeoutMs?: number
  ): Promise<T>;

  /**
   * Get admin-specific headers for protected endpoints.
   * Throws if user is not an admin.
   */
  getAdminHeaders(): Record<string, string>;

  /**
   * Get the current user profile.
   */
  getUserProfile(): UserProfile | null;

  /**
   * Set the current user profile.
   */
  setUserProfile(profile: UserProfile): void;

  /**
   * Set the authentication token.
   */
  setToken(token: string): void;

  /**
   * Get the current authentication token.
   */
  getToken(): string | null;

  /**
   * Clear authentication state (token, CSRF, profile).
   */
  clearToken(): void;

  /**
   * Set the CSRF token for state-changing requests.
   */
  setCsrfToken(token: string): void;

  /**
   * Get the current CSRF token.
   */
  getCsrfToken(): string | null;

  /**
   * Check if user is authenticated.
   */
  isAuthenticated(): boolean;

  /**
   * Check if user has admin role.
   */
  isAdmin(): boolean;

  /**
   * Get the base URL for API requests.
   */
  getBaseUrl(): string;
}
