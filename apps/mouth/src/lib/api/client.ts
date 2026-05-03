import { UserProfile } from "@/types";
import type { IApiClient, ApiRequestOptions } from "./types/api-client.types";
import { safeStorage } from "@/lib/utils/storage";
import { isTokenExpired } from "@/lib/utils/token";
import { logger } from "@/lib/logger";

/** FastAPI validation error structure */
interface FastAPIValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
}

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
  // Superuser impersonation: when set, every portal/lkpm API call adds
  // ?as_client=<id>. Seeded from localStorage and kept in sync by the
  // AdminImpersonationContext (contexts/AdminImpersonationContext.tsx).
  protected portalImpersonationClientId: number | null = null;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
    if (typeof window !== "undefined") {
      this.token = safeStorage.getItem("auth_token");
      const storedProfile = safeStorage.getItem("user_profile");
      if (storedProfile) {
        try {
          this.userProfile = JSON.parse(storedProfile);
        } catch {
          this.userProfile = null;
        }
      }
      // Seed impersonation from localStorage so the very first portal fetch
      // on page reload already carries as_client.
      try {
        const rawImp = localStorage.getItem("bz_portal_impersonation_v1");
        if (rawImp) {
          const parsed = JSON.parse(rawImp) as { id?: number };
          if (typeof parsed.id === "number") {
            this.portalImpersonationClientId = parsed.id;
          }
        }
      } catch {
        // ignore — impersonation is optional
      }
    }

    // Generated OpenAPI client removed - was importing from non-existent file
    // If needed, can be re-added when generated client is available
  }

  setToken(token: string) {
    this.token = token;
    if (typeof window !== "undefined") {
      const success = safeStorage.setItem("auth_token", token);
      if (!success) {
        logger.warn(
          "localStorage blocked - using memory fallback. Auth via httpOnly cookies will work.",
          {
            component: "ApiClient",
            action: "set_token_fallback",
          },
        );
      }
    }
  }

  setUserProfile(profile: UserProfile) {
    this.userProfile = profile;
    if (typeof window !== "undefined") {
      const success = safeStorage.setItem(
        "user_profile",
        JSON.stringify(profile),
      );
      if (!success) {
        logger.warn(
          "localStorage blocked - user profile in memory only (session-scoped).",
          {
            component: "ApiClient",
            action: "set_profile_fallback",
          },
        );
      }
    }
  }

  clearToken() {
    this.token = null;
    this.csrfToken = null;
    this.userProfile = null;
    if (typeof window !== "undefined") {
      safeStorage.removeItem("auth_token");
      safeStorage.removeItem("user_profile");
    }
  }

  getToken(): string | null {
    // Always read from storage to ensure we have the latest token
    // This is critical for cases where login happens after ApiClient instantiation
    if (typeof window !== "undefined") {
      const storedToken = safeStorage.getItem("auth_token");
      if (storedToken !== this.token) {
        this.token = storedToken;
      }
      // Validate token expiry -- clear if expired
      if (this.token && isTokenExpired(this.token)) {
        logger.warn("Auth token expired, clearing from storage", {
          component: "ApiClient",
          action: "token_expired",
        });
        this.clearToken();
        return null;
      }
    }
    return this.token;
  }

  /**
   * Read CSRF token from cookie (fallback when not stored in memory)
   * Cookie is set by backend as non-httpOnly for double-submit pattern
   */
  protected getCsrfFromCookie(): string | null {
    if (typeof document === "undefined") return null;
    const match = document.cookie.match(/nz_csrf_token=([^;]+)/);
    return match ? match[1] : null;
  }

  /**
   * Superuser-only: set/clear the client id that all portal/lkpm calls
   * should be scoped to via ?as_client=<id>. null disables impersonation.
   */
  setPortalImpersonation(clientId: number | null) {
    this.portalImpersonationClientId = clientId;
  }

  getPortalImpersonation(): number | null {
    return this.portalImpersonationClientId;
  }

  getUserProfile(): UserProfile | null {
    // Always read from storage to ensure we have the latest profile
    // This is critical for cases where login happens after ApiClient instantiation
    if (typeof window !== "undefined") {
      const storedProfile = safeStorage.getItem("user_profile");
      if (storedProfile) {
        try {
          const parsed = JSON.parse(storedProfile);
          if (JSON.stringify(parsed) !== JSON.stringify(this.userProfile)) {
            logger.debug("User profile synced from localStorage", {
              component: "ApiClient",
              action: "profile_sync",
              metadata: {
                previousEmail: this.userProfile?.email || "none",
                newEmail: parsed?.email || "none",
              },
            });
            this.userProfile = parsed;
          }
        } catch (e) {
          // Keep existing profile if parsing fails
          logger.warn("Failed to parse user profile from localStorage", {
            component: "ApiClient",
            action: "profile_parse_error",
          });
        }
      }
    }
    return this.userProfile;
  }

  isAuthenticated(): boolean {
    // Check token dynamically to ensure we have the latest state
    const token = this.getToken();
    return token !== null && token.length > 0;
  }

  isAdmin(): boolean {
    const role = this.userProfile?.role?.toLowerCase();
    return (
      role === "admin" ||
      role === "founder" ||
      role === "owner" ||
      role === "board"
    );
  }

  /**
   * Check if user is on the Board (can see all folders and manage permissions)
   */
  isBoard(): boolean {
    const role = this.userProfile?.role?.toLowerCase();
    return (
      role === "board" ||
      role === "admin" ||
      role === "founder" ||
      role === "owner"
    );
  }

  getAdminHeaders(): Record<string, string> {
    if (!this.userProfile || !this.isAdmin()) {
      throw new Error("Admin access required");
    }
    return { "X-User-Email": this.userProfile.email };
  }

  /**
   * Core request method with CSRF token handling, timeout, and error handling.
   * Public method implementing IApiClient interface.
   */
  async request<T>(
    endpoint: string,
    options: ApiRequestOptions = {},
    timeoutMs: number = 30000,
  ): Promise<T> {
    // Superuser impersonation: append ?as_client=<id> to portal/lkpm paths
    // when the context has a target set. Idempotent — if the query already
    // carries as_client we leave it alone, honoring explicit callers (e.g.
    // admin tooling).
    if (this.portalImpersonationClientId !== null) {
      const isPortalApi =
        endpoint.startsWith("/api/portal") ||
        endpoint.startsWith("/api/v1/lkpm");
      // The admin-only endpoints must NOT be rewritten — they operate on
      // the superuser itself, not on the impersonated client.
      const isAdminApi = endpoint.startsWith("/api/portal/admin");
      if (isPortalApi && !isAdminApi) {
        const alreadySet = /[?&]as_client=/.test(endpoint);
        if (!alreadySet) {
          const sep = endpoint.includes("?") ? "&" : "?";
          endpoint = `${endpoint}${sep}as_client=${this.portalImpersonationClientId}`;
        }
      }
    }

    // Don't set Content-Type for FormData - browser will set it with boundary
    const isFormData = options.body instanceof FormData;
    const headers: Record<string, string> = isFormData
      ? { ...((options.headers as Record<string, string>) || {}) }
      : {
          "Content-Type": "application/json",
          ...((options.headers as Record<string, string>) || {}),
        };

    // Add CSRF header for state-changing requests (POST, PUT, DELETE, PATCH)
    const method = (options.method || "GET").toUpperCase();
    if (["POST", "PUT", "DELETE", "PATCH"].includes(method)) {
      const csrf = this.csrfToken || this.getCsrfFromCookie();
      if (csrf) {
        headers["X-CSRF-Token"] = csrf;
      }
    }

    // Keep Authorization header for backward compatibility (WebSocket, mobile apps)
    // Use getToken() to ensure we always have the latest token from localStorage
    const currentToken = this.getToken();
    if (currentToken) {
      headers["Authorization"] = `Bearer ${currentToken}`;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    logger.debug("HTTP request starting", {
      component: "ApiClient",
      action: "request",
      metadata: {
        method,
        endpoint,
        fullUrl: `${this.baseUrl}${endpoint}`,
        hasToken: !!currentToken,
        hasCsrf: !!(this.csrfToken || this.getCsrfFromCookie()),
        credentials: "include",
      },
    });

    try {
      const response = await fetch(`${this.baseUrl}${endpoint}`, {
        ...options,
        headers,
        credentials: "include", // CRITICAL: Send httpOnly cookies
        signal: controller.signal,
      });

      logger.debug("HTTP response received", {
        component: "ApiClient",
        action: "response",
        metadata: {
          method,
          endpoint,
          status: response.status,
          ok: response.ok,
          statusText: response.statusText,
          headers: {
            contentType: response.headers.get("content-type"),
            setCookie: response.headers.get("set-cookie"),
          },
        },
      });

      // Handle 401 Unauthorized (token expired or invalid)
      if (response.status === 401) {
        // Clear token and redirect to login
        this.clearToken();

        // Only redirect if we're in the browser (not SSR)
        if (typeof window !== "undefined") {
          // Avoid redirect loops by checking current path
          const currentPath = window.location.pathname;
          // Portal subdomain uses /portal/login; workspace uses /login.
          // Without this check, shareholders on my.balizero.com would bounce
          // to /login, which mouth's middleware redirects cross-origin to
          // kita.balizero.com/login — breaking the portal session silently.
          const isPortal = currentPath.startsWith("/portal");
          const loginPath = isPortal ? "/portal/login" : "/login";
          const alreadyOnLogin = currentPath === loginPath;
          if (!alreadyOnLogin && !currentPath.startsWith("/api/")) {
            logger.warn("Token expired or invalid, redirecting to login", {
              component: "ApiClient",
              action: "auth_redirect",
              metadata: { currentPath, target: loginPath },
            });
            // Use replace to avoid adding to history
            window.location.replace(
              `${loginPath}?expired=true&reason=token_expired`,
            );
          }
        }

        const error = await response
          .json()
          .catch(() => ({ detail: "Authentication required" }));
        throw new Error(error.detail || "Session expired. Please login again.");
      }

      // Allow 204 as success even if ok is false (defensive)
      if (!response.ok && response.status !== 204) {
        const error = await response
          .json()
          .catch(() => ({ detail: "Request failed" }));

        // Handle FastAPI 422 validation errors (detail is array of validation errors)
        if (response.status === 422 && Array.isArray(error.detail)) {
          const validationErrors = (error.detail as FastAPIValidationError[])
            .map((err) => {
              const field = err.loc ? err.loc.join(".") : "unknown";
              return `${field}: ${err.msg}`;
            })
            .join(", ");
          throw new Error(`Validation error: ${validationErrors}`);
        }

        // Handle 405 Method Not Allowed - convert to INVALID_METHOD for consistency
        if (response.status === 405) {
          throw new Error("INVALID_METHOD");
        }

        throw new Error(error.detail || `HTTP ${response.status}`);
      }

      // Handle empty responses (204 No Content, etc.)
      const contentType = response.headers.get("content-type");
      if (
        response.status === 204 ||
        !contentType?.includes("application/json")
      ) {
        return {} as T;
      }

      return response.json();
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") {
        throw new Error("Request timeout");
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

  /**
   * Convenience method for POST requests
   */
  async post<T>(
    endpoint: string,
    body?: unknown,
    timeoutMs?: number,
  ): Promise<T> {
    return this.request<T>(
      endpoint,
      {
        method: "POST",
        body: body ? JSON.stringify(body) : undefined,
      },
      timeoutMs,
    );
  }
}
