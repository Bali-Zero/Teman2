import { UserProfile } from '@/types';
import type { IApiClient, ApiRequestOptions } from './types/api-client.types';
import { safeStorage } from '@/lib/utils/storage';

/**
 * Base API client with token management and request handling.
 * This is the core class that all domain-specific API modules extend or use.
 * Implements IApiClient interface for type-safe dependency injection.
 *
 * AUTH STRATEGY (2026 Best Practice):
 * - PRIMARY: httpOnly cookies (set by backend, immune to XSS, works in Private Browsing)
 * - OPTIONAL: localStorage (for WebSocket backward compat, offline access, UX enhancement)
 * - localStorage blocked (Safari Private)? No problem - cookies still work!
 */
export class ApiClientBase implements IApiClient {
  protected baseUrl: string;
  protected token: string | null = null;
  protected csrfToken: string | null = null; // CSRF token for cookie-based auth
  protected userProfile: UserProfile | null = null;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
    if (typeof window !== 'undefined') {
      this.token = safeStorage.getItem('auth_token');
      const storedProfile = safeStorage.getItem('user_profile');
      if (storedProfile) {
        try {
          this.userProfile = JSON.parse(storedProfile);
        } catch {
          this.userProfile = null;
        }
      }
    }

    // Generated OpenAPI client removed - was importing from non-existent file
    // If needed, can be re-added when generated client is available
  }

  setToken(token: string) {
    this.token = token;
    if (typeof window !== 'undefined') {
      const success = safeStorage.setItem('auth_token', token);
      if (!success) {
        console.warn('[ApiClient] localStorage blocked - using memory fallback. Auth via httpOnly cookies will work.');
      }
    }
  }

  setUserProfile(profile: UserProfile) {
    this.userProfile = profile;
    if (typeof window !== 'undefined') {
      const success = safeStorage.setItem('user_profile', JSON.stringify(profile));
      if (!success) {
        console.warn('[ApiClient] localStorage blocked - user profile in memory only (session-scoped).');
      }
    }
  }

  clearToken() {
    this.token = null;
    this.csrfToken = null;
    this.userProfile = null;
    if (typeof window !== 'undefined') {
      safeStorage.removeItem('auth_token');
      safeStorage.removeItem('user_profile');
    }
  }

  getToken(): string | null {
    // Always read from storage to ensure we have the latest token
    // This is critical for cases where login happens after ApiClient instantiation
    if (typeof window !== 'undefined') {
      const storedToken = safeStorage.getItem('auth_token');
      if (storedToken !== this.token) {
        this.token = storedToken;
      }
    }
    return this.token;
  }

  /**
   * Read CSRF token from cookie (fallback when not stored in memory)
   * Cookie is set by backend as non-httpOnly for double-submit pattern
   */
  protected getCsrfFromCookie(): string | null {
    if (typeof document === 'undefined') return null;
    const match = document.cookie.match(/nz_csrf_token=([^;]+)/);
    return match ? match[1] : null;
  }

  getUserProfile() {
    return this.userProfile;
  }

  isAuthenticated(): boolean {
    // Check token dynamically to ensure we have the latest state
    const token = this.getToken();
    return token !== null && token.length > 0;
  }

  isAdmin(): boolean {
    return this.userProfile?.role === 'admin';
  }

  /**
   * Check if user is on the Board (can see all folders and manage permissions)
   */
  isBoard(): boolean {
    const role = this.userProfile?.role?.toLowerCase();
    return role === 'board' || role === 'admin' || role === 'founder' || role === 'owner';
  }

  getAdminHeaders(): Record<string, string> {
    if (!this.userProfile || this.userProfile.role !== 'admin') {
      throw new Error('Admin access required');
    }
    return { 'X-User-Email': this.userProfile.email };
  }

  /**
   * Core request method with CSRF token handling, timeout, and error handling.
   * Public method implementing IApiClient interface.
   */
  async request<T>(
    endpoint: string,
    options: ApiRequestOptions = {},
    timeoutMs: number = 30000
  ): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...((options.headers as Record<string, string>) || {}),
    };

    // Add CSRF header for state-changing requests (POST, PUT, DELETE, PATCH)
    const method = (options.method || 'GET').toUpperCase();
    if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
      const csrf = this.csrfToken || this.getCsrfFromCookie();
      if (csrf) {
        headers['X-CSRF-Token'] = csrf;
      }
    }

    // Keep Authorization header for backward compatibility (WebSocket, mobile apps)
    // Use getToken() to ensure we always have the latest token from localStorage
    const currentToken = this.getToken();
    if (currentToken) {
      headers['Authorization'] = `Bearer ${currentToken}`;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    console.log('[HTTP] 🌐 Request starting:', {
      method,
      endpoint,
      fullUrl: `${this.baseUrl}${endpoint}`,
      hasToken: !!currentToken,
      hasCsrf: !!(this.csrfToken || this.getCsrfFromCookie()),
      credentials: 'include',
    });

    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        ...options,
        headers,
        credentials: 'include', // CRITICAL: Send httpOnly cookies
        signal: controller.signal,
      });

      console.log('[HTTP] ✅ Response received:', {
        method,
        endpoint,
        status: response.status,
        ok: response.ok,
        statusText: response.statusText,
        headers: {
          contentType: response.headers.get('content-type'),
          setCookie: response.headers.get('set-cookie'),
        },
      });

      if (process.env.NODE_ENV !== 'production') {
        console.log(
          `[ApiClient] ${method} ${endpoint} -> Status: ${response.status}, OK: ${response.ok}`
        );
      }

      // Handle 401 Unauthorized (token expired or invalid)
      if (response.status === 401) {
        // Clear token and redirect to login
        this.clearToken();

        // Only redirect if we're in the browser (not SSR)
        if (typeof window !== 'undefined') {
          // Avoid redirect loops by checking current path
          const currentPath = window.location.pathname;
          if (currentPath !== '/login' && !currentPath.startsWith('/api/')) {
            console.log('[ApiClient] Token expired or invalid, redirecting to login');
            // Use replace to avoid adding to history
            window.location.replace('/login?expired=true&reason=token_expired');
          }
        }

        const error = await response.json().catch(() => ({ detail: 'Authentication required' }));
        throw new Error(error.detail || 'Session expired. Please login again.');
      }

      // Allow 204 as success even if ok is false (defensive)
      if (!response.ok && response.status !== 204) {
        const error = await response.json().catch(() => ({ detail: 'Request failed' }));

        // Handle FastAPI 422 validation errors (detail is array of validation errors)
        if (response.status === 422 && Array.isArray(error.detail)) {
          const validationErrors = error.detail.map((err: any) => {
            const field = err.loc ? err.loc.join('.') : 'unknown';
            return `${field}: ${err.msg}`;
          }).join(', ');
          throw new Error(`Validation error: ${validationErrors}`);
        }

        throw new Error(error.detail || `HTTP ${response.status}`);
      }

      // Handle empty responses (204 No Content, etc.)
      const contentType = response.headers.get('content-type');
      if (response.status === 204 || !contentType?.includes('application/json')) {
        return {} as T;
      }

      return response.json();
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        throw new Error('Request timeout');
      }
      throw error;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  /**
   * Set CSRF token (called after login)
   */
  setCsrfToken(token: string) {
    this.csrfToken = token;
  }

  /**
   * Get base URL (for modules that need direct fetch access)
   */
  getBaseUrl(): string {
    return this.baseUrl;
  }

  /**
   * Get CSRF token (for modules that need direct fetch access)
   */
  getCsrfToken(): string | null {
    return this.csrfToken || this.getCsrfFromCookie();
  }
}
