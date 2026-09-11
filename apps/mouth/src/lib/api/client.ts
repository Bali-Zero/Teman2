import { UserProfile } from "@/types";
import type {
  IApiClient,
  ApiRequestOptions,
  SessionState,
} from "./types/api-client.types";
import { safeStorage } from "@/lib/utils/storage";
import { isTokenExpired } from "@/lib/utils/token";
import { logger } from "@/lib/logger";
import { ApiError } from "./error-handler";

/** FastAPI validation error structure */
interface FastAPIValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
}

/**
 * localStorage key for superuser portal impersonation ("view as client X").
 * Single source of truth — this module owns the key because it is also the
 * one that reads/consumes it (constructor seed + request() injection +
 * clearToken() teardown, below). AdminImpersonationContext
 * (contexts/AdminImpersonationContext.tsx) imports this constant rather than
 * re-typing the literal: the two sides MUST agree on the exact key, and a
 * future rename/version-bump (_v1 -> _v2) done in only one place would leave
 * the context writing/restoring a key clearToken() no longer clears —
 * silently reviving the cross-operator impersonation-inheritance bug this
 * key exists to guard against.
 */
export const PORTAL_IMPERSONATION_STORAGE_KEY = "bz_portal_impersonation_v1";

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
  // Memoized cookie-only session probe (see hasSession()/probeSession()
  // below). N components asking "am I logged in?" at once collapse into one
  // fetch. Invalidated by setToken()/clearToken() so a login/logout never
  // leaves a stale verdict behind for the rest of the page's life.
  private sessionProbe: Promise<SessionState> | null = null;
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
        const rawImp = localStorage.getItem(PORTAL_IMPERSONATION_STORAGE_KEY);
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
    // A fresh token invalidates any cached probe verdict — a stale
    // "anonymous" from before login must never be replayed to a gate that
    // asks right after.
    this.sessionProbe = null;
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
    // Same reasoning as setToken(): logout (or the 401 handler below, which
    // calls this) must not leave a pre-logout "authenticated" verdict
    // sitting in cache for the login page's own gate to read.
    this.sessionProbe = null;
    // Reset superuser impersonation together with the session. Without this,
    // logging out (or a token-expiry 401, below) leaves the in-memory
    // portalImpersonationClientId set AND the localStorage key that
    // AdminImpersonationContext restores on mount — so the very next login
    // in this browser, even by a DIFFERENT superuser, silently inherits the
    // previous operator's impersonation target on every portal request.
    this.portalImpersonationClientId = null;
    if (typeof window !== "undefined") {
      safeStorage.removeItem("auth_token");
      safeStorage.removeItem("user_profile");
      try {
        localStorage.removeItem(PORTAL_IMPERSONATION_STORAGE_KEY);
      } catch {
        // ignore — impersonation storage is optional, same as the read path
      }
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

  /**
   * Positive-only signal: a local token proves a session exists, but its
   * ABSENCE does NOT mean the visitor is anonymous — auth here is
   * cookie-PRIMARY (see the class docstring above), and the httpOnly cookie
   * this app actually relies on is invisible to a check like this one. A
   * gate that redirects to /login on a `false` here is wrong for a
   * cookie-only session (no local token, still logged in). Use
   * `hasSession()` / `useSessionState()` instead — they ask the server
   * before concluding "anonymous".
   */
  isAuthenticated(): boolean {
    // Check token dynamically to ensure we have the latest state
    const token = this.getToken();
    return token !== null && token.length > 0;
  }

  /**
   * Cookie-primary session check (auth-gates-cookie-primary). Resolves to
   * "authenticated" | "anonymous" | "unknown" — the third value is the
   * point: a network hiccup or an ambiguous status is NOT proof the visitor
   * is anonymous, so callers that redirect on "anonymous" alone stay
   * correct even when the probe itself is inconclusive.
   */
  async hasSession(): Promise<SessionState> {
    // Fast path: a local token is already a sufficient POSITIVE signal (see
    // the docstring on the method above) — no need to ask the server.
    if (this.isAuthenticated()) return "authenticated";
    if (!this.sessionProbe) {
      this.sessionProbe = this.probeSession().then((result) => {
        // "unknown" is not a verdict — never cache it, so the next gate that
        // asks gets a fresh attempt instead of being stuck behind one
        // transient failure for the rest of the page's life.
        if (result === "unknown") this.sessionProbe = null;
        return result;
      });
    }
    return this.sessionProbe;
  }

  /**
   * The actual cookie-only network probe behind hasSession(). Deliberately a
   * NAKED fetch, never this.request(): request() auto-redirects to /login
   * and calls clearToken() on a 401, and a background "am I logged in?"
   * check must never itself log a visitor out or bounce the page — side
   * effects here would turn a read into a surprise action.
   *
   * Endpoint choice: `/api/auth/check` would be the obvious pick, but that
   * router (`routers/auth.py`) authenticates with its own strict
   * `HTTPBearer` dependency — a cookie-only request passes the app's
   * middleware and then gets a 403 from THIS route specifically, so it
   * cannot tell "no session" apart from "session, but no bearer token".
   * `/api/bali-zero/conversations/stats` instead goes through the central
   * `get_current_user` dependency, which reads `request.state.user` set by
   * the cookie-aware middleware — it works cookie-only, is GET/side-effect
   * free, and is available to any authenticated role. Borrowed on purpose;
   * migrate to `/api/auth/check` once that router accepts cookies too
   * (residual, tracked in PENDING-ARMS).
   */
  private async probeSession(): Promise<SessionState> {
    if (typeof window === "undefined") return "unknown";
    try {
      const res = await fetch(
        `${this.baseUrl}/api/bali-zero/conversations/stats`,
        { credentials: "include", cache: "no-store" },
      );
      if (res.ok) return "authenticated";
      if (res.status === 401) return "anonymous";
      return "unknown";
    } catch {
      return "unknown";
    }
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
        // React Query owns API response caching. Browser HTTP caching can replay
        // stale rows immediately after a successful CRM mutation.
        ...(method === "GET" && options.cache === undefined
          ? { cache: "no-store" }
          : {}),
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
        // Did a session ever exist? A visitor who never logged in gets 401
        // from any authenticated endpoint, and calling that "expired" is wrong
        // twice: the message is false, and the event is not worth an alert.
        // Auth here is cookie-PRIMARY (see the class docstring), so a live
        // session can exist with no local token — hence the profile check.
        // Read this BEFORE clearToken(), which erases the evidence.
        const hadSession =
          this.getToken() !== null || this.userProfile !== null;

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
          const loginPath = isPortal ? "/portal/login-upgraded" : "/login";
          const alreadyOnLogin =
            currentPath === loginPath ||
            (isPortal && currentPath === "/portal/login");
          // A background call on a public page opts out of the navigation
          // entirely (see ApiRequestOptions.redirectOnUnauthorized).
          const mayRedirect = options.redirectOnUnauthorized !== false;
          if (
            mayRedirect &&
            !alreadyOnLogin &&
            !currentPath.startsWith("/api/")
          ) {
            // Level, not silence: a session that DIED is worth seeing, a
            // visitor who never had one is not. `logger.warn` forwards to
            // Sentry on the same branch as `logger.error` (logger.ts), so
            // logging every anonymous 401 at warn burned the Sentry quota —
            // measured 2026-08-28, Sentry answers 429 and drops REAL events.
            const context = {
              component: "ApiClient",
              action: "auth_redirect",
              metadata: { currentPath, target: loginPath },
            };
            if (hadSession) {
              logger.warn(
                "Token expired or invalid, redirecting to login",
                context,
              );
            } else {
              logger.debug(
                "Unauthenticated visitor on a protected route, sending to login",
                context,
              );
            }
            // Use replace to avoid adding to history
            const loginParams = new URLSearchParams({
              expired: "true",
              reason: "token_expired",
            });
            if (isPortal) {
              loginParams.set(
                "redirect",
                `${currentPath}${window.location.search || ""}`,
              );
            }
            window.location.replace(`${loginPath}?${loginParams.toString()}`);
          }
        }

        const error = await response
          .json()
          .catch(() => ({ detail: "Authentication required" }));
        // Messages below are unchanged on purpose: ApiError extends Error, so
        // every existing `instanceof Error` / `.message` consumer keeps working.
        // What is new is `statusCode` — the thing callers actually need.
        throw new ApiError(
          error.detail || "Session expired. Please login again.",
          response.status,
          error,
        );
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
          throw new ApiError(
            `Validation error: ${validationErrors}`,
            response.status,
            error,
          );
        }

        // Handle 405 Method Not Allowed - convert to INVALID_METHOD for consistency
        if (response.status === 405) {
          throw new ApiError("INVALID_METHOD", response.status, error);
        }

        throw new ApiError(
          error.detail || `HTTP ${response.status}`,
          response.status,
          error,
        );
      }

      // Handle empty responses (204 No Content, etc.)
      const contentType = response.headers.get("content-type");
      if (
        response.status === 204 ||
        !contentType?.includes("application/json")
      ) {
        return {} as T;
      }

      // Keep the deadline and AbortError handling active while the body is read.
      // Headers can arrive promptly even when the JSON body stalls.
      return await response.json();
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
