import { UserProfile } from '@/types';
import { NuzantaraClient } from '../../../lib/api/generated';

/**
 * Base API client with token management and request handling.
 * This is the core class that all domain-specific API modules extend or use.
 */
export class ApiClientBase {
  protected baseUrl: string;
  protected token: string | null = null;
  protected csrfToken: string | null = null; // CSRF token for cookie-based auth
  protected userProfile: UserProfile | null = null;
  public readonly client: NuzantaraClient;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
    if (typeof window !== 'undefined') {
      this.token = localStorage.getItem('auth_token');
      const storedProfile = localStorage.getItem('user_profile');
      if (storedProfile) {
        try {
          this.userProfile = JSON.parse(storedProfile);
        } catch {
          this.userProfile = null;
        }
      }
    }

    // Generated OpenAPI client (used by some pages); token is resolved dynamically.
    this.client = new NuzantaraClient({
      BASE: this.baseUrl,
      TOKEN: async () => this.token || '',
    });
  }

  setToken(token: string) {
    this.token = token;
    if (typeof window !== 'undefined') {
      localStorage.setItem('auth_token', token);
    }
  }

  setUserProfile(profile: UserProfile) {
    this.userProfile = profile;
    if (typeof window !== 'undefined') {
      localStorage.setItem('user_profile', JSON.stringify(profile));
    }
  }

  clearToken() {
    this.token = null;
    this.csrfToken = null;
    this.userProfile = null;
    if (typeof window !== 'undefined') {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('user_profile');
    }
  }

  getToken() {
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
    return this.token !== null && this.token.length > 0;
  }

  isAdmin(): boolean {
    return this.userProfile?.role === 'admin';
  }

  protected getAdminHeaders(): Record<string, string> {
    if (!this.userProfile || this.userProfile.role !== 'admin') {
      throw new Error('Admin access required');
    }
    return { 'X-User-Email': this.userProfile.email };
  }

  /**
   * Core request method with CSRF token handling, timeout, and error handling.
   */
  protected async request<T>(
    endpoint: string,
    options: RequestInit = {},
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
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        ...options,
        headers,
        credentials: 'include', // CRITICAL: Send httpOnly cookies
        signal: controller.signal,
      });

      console.log(`[ApiClient] ${method} ${endpoint} -> Status: ${response.status}, OK: ${response.ok}`);

      // Allow 204 as success even if ok is false (defensive)
      if (!response.ok && response.status !== 204) {
        const error = await response.json().catch(() => ({ detail: 'Request failed' }));
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

