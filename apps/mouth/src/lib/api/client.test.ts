import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ApiClientBase, PORTAL_IMPERSONATION_STORAGE_KEY } from "./client";
import { UserProfile } from "@/types";

// The 401 branch chooses a LOG LEVEL, and level is the whole point: `warn` and
// `error` both forward to Sentry, `debug` does not (see logger.ts). Asserting
// "it logged" would pass either way, so these tests assert WHICH method ran.
vi.mock("@/lib/logger", () => ({
  logger: {
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  },
}));
import { logger } from "@/lib/logger";

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
  };
})();

Object.defineProperty(window, "localStorage", { value: localStorageMock });

// Mock document.cookie
Object.defineProperty(document, "cookie", {
  writable: true,
  value: "",
});

describe("ApiClientBase", () => {
  let client: ApiClientBase;
  const baseUrl = "https://api.test.com";

  beforeEach(() => {
    localStorageMock.clear();
    vi.clearAllMocks();
    client = new ApiClientBase(baseUrl);
    document.cookie = "";
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("Constructor", () => {
    it("should initialize with baseUrl", () => {
      expect(client.getBaseUrl()).toBe(baseUrl);
    });

    it("should load token from localStorage if available", () => {
      localStorageMock.setItem("auth_token", "test-token");
      const newClient = new ApiClientBase(baseUrl);
      expect(newClient.getToken()).toBe("test-token");
    });

    it("should load user profile from localStorage if available", () => {
      const profile: UserProfile = {
        id: "123",
        email: "test@example.com",
        name: "Test User",
        role: "user",
      };
      localStorageMock.setItem("user_profile", JSON.stringify(profile));
      const newClient = new ApiClientBase(baseUrl);
      expect(newClient.getUserProfile()).toEqual(profile);
    });

    it("should handle invalid JSON in localStorage gracefully", () => {
      localStorageMock.setItem("user_profile", "invalid-json");
      const newClient = new ApiClientBase(baseUrl);
      expect(newClient.getUserProfile()).toBeNull();
    });
  });

  describe("Token Management", () => {
    it("should set and get token", () => {
      client.setToken("test-token");
      expect(client.getToken()).toBe("test-token");
      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        "auth_token",
        "test-token",
      );
    });

    it("should clear token", () => {
      client.setToken("test-token");
      client.clearToken();
      expect(client.getToken()).toBeNull();
      expect(localStorageMock.removeItem).toHaveBeenCalledWith("auth_token");
    });

    it("should check authentication status", () => {
      expect(client.isAuthenticated()).toBe(false);
      client.setToken("test-token");
      expect(client.isAuthenticated()).toBe(true);
      client.setToken("");
      expect(client.isAuthenticated()).toBe(false);
    });
  });

  describe("Portal Impersonation (cross-operator inheritance regression)", () => {
    // Storage key comes from the imported PORTAL_IMPERSONATION_STORAGE_KEY
    // constant (see import above) — no local literal, single source of truth
    // with client.ts.

    beforeEach(() => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({}),
      });
    });

    it("clearToken() removes the impersonation key from storage AND stops injecting as_client into subsequent requests", async () => {
      // Simulate a superuser (zero@) who is viewing as client 42 — the
      // AdminImpersonationContext both persists the target to localStorage
      // and pushes it into the live api client's in-memory field.
      client.setPortalImpersonation(42);
      localStorageMock.setItem(
        PORTAL_IMPERSONATION_STORAGE_KEY,
        JSON.stringify({ id: 42, email: "client@example.com", fullName: null }),
      );
      expect(client.getPortalImpersonation()).toBe(42);

      // logout() -> clearToken()
      client.clearToken();

      // 1. The persisted key must be gone — a fresh page/context mount must
      //    have nothing to rehydrate from.
      expect(localStorageMock.removeItem).toHaveBeenCalledWith(
        PORTAL_IMPERSONATION_STORAGE_KEY,
      );
      expect(
        localStorageMock.getItem(PORTAL_IMPERSONATION_STORAGE_KEY),
      ).toBeNull();

      // 2. The in-memory id must be reset too — this is what actually rides
      //    on the next request, independent of storage.
      expect(client.getPortalImpersonation()).toBeNull();

      // 3. The real property under test: a DIFFERENT superuser logging in
      //    right after must NOT have as_client silently attached to their
      //    portal calls.
      await (client as any).request("/api/portal/clients");
      const callArgs = (global.fetch as any).mock.calls[0];
      const requestedUrl = callArgs[0] as string;
      expect(requestedUrl).not.toContain("as_client=");
    });

    it("clearToken() does not throw and still clears the ordinary session when no impersonation was ever set", () => {
      // Innocence: a regular client/employee logging out (never impersonating)
      // must not be affected by the impersonation-clearing logic.
      client.setToken("plain-token");
      expect(() => client.clearToken()).not.toThrow();
      expect(client.getToken()).toBeNull();
      expect(client.getPortalImpersonation()).toBeNull();
      // No impersonation key ever existed — removeItem is safe to call
      // regardless (storage.removeItem on a missing key is a no-op).
      expect(
        localStorageMock.getItem(PORTAL_IMPERSONATION_STORAGE_KEY),
      ).toBeNull();
    });

    it("a plain page reload while still logged in legitimately re-seeds impersonation from storage (must NOT regress)", () => {
      // This is the moment impersonation SHOULD persist: the operator never
      // logged out, they just refreshed the tab. ApiClientBase's constructor
      // seeds portalImpersonationClientId from localStorage precisely so the
      // very first portal fetch after reload still carries as_client.
      localStorageMock.setItem("auth_token", "still-logged-in-token");
      localStorageMock.setItem(
        PORTAL_IMPERSONATION_STORAGE_KEY,
        JSON.stringify({ id: 7, email: "other@example.com", fullName: null }),
      );

      // clearToken() is never called on a reload — only the constructor runs.
      const reloadedClient = new ApiClientBase(baseUrl);

      expect(reloadedClient.getPortalImpersonation()).toBe(7);
    });
  });

  describe("User Profile Management", () => {
    it("should set and get user profile", () => {
      const profile: UserProfile = {
        id: "123",
        email: "test@example.com",
        name: "Test User",
        role: "user",
      };
      client.setUserProfile(profile);
      expect(client.getUserProfile()).toEqual(profile);
      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        "user_profile",
        JSON.stringify(profile),
      );
    });

    it("should clear user profile on clearToken", () => {
      const profile: UserProfile = {
        id: "123",
        email: "test@example.com",
        name: "Test User",
        role: "user",
      };
      client.setUserProfile(profile);
      client.clearToken();
      expect(client.getUserProfile()).toBeNull();
    });

    it("should sync profile from localStorage when external change occurs (FIX TEST)", () => {
      // This tests the fix for getUserProfile() not re-reading from localStorage
      // Scenario: Login happens AFTER ApiClient instantiation

      // 1. Client initialized with no profile
      const freshClient = new ApiClientBase(baseUrl);
      expect(freshClient.getUserProfile()).toBeNull();

      // 2. Profile saved externally (e.g., by login flow)
      const newProfile: UserProfile = {
        id: "456",
        email: "newuser@example.com",
        name: "New User",
        role: "admin",
      };
      localStorageMock.setItem("user_profile", JSON.stringify(newProfile));

      // 3. getUserProfile should re-read from localStorage and get the new profile
      const retrievedProfile = freshClient.getUserProfile();
      expect(retrievedProfile).toEqual(newProfile);
    });

    it("should handle corrupted profile in localStorage gracefully during sync", () => {
      const profile: UserProfile = {
        id: "123",
        email: "test@example.com",
        name: "Test User",
        role: "user",
      };
      client.setUserProfile(profile);

      // Corrupt localStorage externally
      localStorageMock.setItem("user_profile", "not-valid-json");

      // Should keep existing profile on parse error
      expect(client.getUserProfile()).toEqual(profile);
    });

    it("should detect and update when localStorage profile differs from memory", () => {
      // Set initial profile
      const initialProfile: UserProfile = {
        id: "1",
        email: "first@example.com",
        name: "First",
        role: "user",
      };
      client.setUserProfile(initialProfile);

      // Modify localStorage directly (simulating another tab or login)
      const updatedProfile: UserProfile = {
        id: "2",
        email: "second@example.com",
        name: "Second",
        role: "admin",
      };
      localStorageMock.setItem("user_profile", JSON.stringify(updatedProfile));

      // getUserProfile should pick up the new profile
      const result = client.getUserProfile();
      expect(result).toEqual(updatedProfile);
    });
  });

  describe("CSRF Token Management", () => {
    it("should set CSRF token", () => {
      client.setCsrfToken("csrf-token");
      expect(client.getCsrfToken()).toBe("csrf-token");
    });

    it("should read CSRF token from cookie as fallback", () => {
      document.cookie = "nz_csrf_token=csrf-from-cookie";
      expect(client.getCsrfToken()).toBe("csrf-from-cookie");
    });

    it("should return null if no CSRF token in memory or cookie", () => {
      document.cookie = "";
      expect(client.getCsrfToken()).toBeNull();
    });
  });

  describe("Admin Check", () => {
    it("should return false for non-admin user", () => {
      const profile: UserProfile = {
        id: "123",
        email: "test@example.com",
        name: "Test User",
        role: "user",
      };
      client.setUserProfile(profile);
      expect(client.isAdmin()).toBe(false);
    });

    it("should return true for admin user", () => {
      const profile: UserProfile = {
        id: "123",
        email: "admin@example.com",
        name: "Admin User",
        role: "admin",
      };
      client.setUserProfile(profile);
      expect(client.isAdmin()).toBe(true);
    });

    it("should return false if no user profile", () => {
      expect(client.isAdmin()).toBe(false);
    });
  });

  describe("Request Method", () => {
    beforeEach(() => {
      global.fetch = vi.fn();
    });

    it("should make GET request successfully", async () => {
      const mockResponse = { data: "test" };
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => mockResponse,
      });

      const result = await (client as any).request("/test");
      expect(result).toEqual(mockResponse);
      expect(global.fetch).toHaveBeenCalledTimes(1);
      const callArgs = (global.fetch as any).mock.calls[0];
      expect(callArgs[0]).toBe(`${baseUrl}/test`);
      if (callArgs[1]) {
        expect(callArgs[1].method || "GET").toBe("GET");
        expect(callArgs[1].credentials).toBe("include");
        expect(callArgs[1].cache).toBe("no-store");
      }
    });

    it("should preserve an explicit GET cache policy", async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({}),
      });

      await (client as any).request("/test", { cache: "force-cache" });

      const callArgs = (global.fetch as any).mock.calls[0];
      expect(callArgs[1].cache).toBe("force-cache");
    });

    it("should add Authorization header when token exists", async () => {
      client.setToken("test-token");
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({}),
      });

      await (client as any).request("/test");
      expect(global.fetch).toHaveBeenCalled();
      const callArgs = (global.fetch as any).mock.calls[0];
      expect(callArgs[1].headers).toMatchObject({
        Authorization: "Bearer test-token",
      });
    });

    it("should add CSRF token for POST requests", async () => {
      client.setCsrfToken("csrf-token");
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({}),
      });

      await (client as any).request("/test", { method: "POST" });
      expect(global.fetch).toHaveBeenCalled();
      const callArgs = (global.fetch as any).mock.calls[0];
      expect(callArgs[1].headers).toMatchObject({
        "X-CSRF-Token": "csrf-token",
      });
    });

    it("should handle HTTP errors", async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: "Not Found",
        headers: {
          get: vi.fn((name: string) => {
            if (name === "content-type") return "application/json";
            return null;
          }),
        },
        json: async () => ({ detail: "Not found" }),
      });

      await expect((client as any).request("/test")).rejects.toThrow(
        "Not found",
      );
    });

    it("should handle empty responses (204)", async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 204,
        headers: new Headers(),
      });

      const result = await (client as any).request("/test");
      expect(result).toEqual({});
    });
  });

  // Measured 2026-08-28 on the live site: `/dream` is public, its autosave hits
  // an authenticated endpoint, and an anonymous visitor who typed one character
  // was ejected to kita.balizero.com/login?expired=true within seconds — while
  // every tick logged at a Sentry-forwarding level until Sentry answered 429.
  // Each test below fails if its half of that cure is removed.
  describe("401 handling: never-authenticated visitor vs expired session", () => {
    let replace: ReturnType<typeof vi.fn>;
    let originalLocation: Location;

    beforeEach(() => {
      replace = vi.fn();
      originalLocation = window.location;
      Object.defineProperty(window, "location", {
        configurable: true,
        writable: true,
        value: { pathname: "/dream", search: "", replace },
      });
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        headers: new Headers(),
        json: async () => ({ detail: "Authentication required" }),
      });
    });

    afterEach(() => {
      Object.defineProperty(window, "location", {
        configurable: true,
        writable: true,
        value: originalLocation,
      });
    });

    const seedSession = () => {
      const profile: UserProfile = {
        id: "1",
        email: "someone@balizero.com",
        name: "Someone",
        role: "user",
      };
      localStorageMock.setItem("user_profile", JSON.stringify(profile));
      return new ApiClientBase(baseUrl);
    };

    it("does NOT navigate away when the caller opts out (background autosave)", async () => {
      await expect(
        (client as any).request("/api/dream/state", {
          method: "POST",
          redirectOnUnauthorized: false,
        }),
      ).rejects.toThrow();

      expect(replace).not.toHaveBeenCalled();
    });

    it("logs an anonymous visitor's 401 at debug — never at a Sentry-forwarding level", async () => {
      await expect((client as any).request("/api/protected")).rejects.toThrow();

      expect(logger.debug).toHaveBeenCalled();
      expect(logger.warn).not.toHaveBeenCalled();
      expect(logger.error).not.toHaveBeenCalled();
    });

    it("still warns and redirects when a real session died", async () => {
      const authed = seedSession();

      await expect((authed as any).request("/api/protected")).rejects.toThrow();

      expect(logger.warn).toHaveBeenCalled();
      expect(replace).toHaveBeenCalledWith(
        expect.stringContaining("/login?expired=true"),
      );
    });

    it("still redirects an anonymous visitor on a protected route by default", async () => {
      // The opt-out is per-call, not a blanket change: a route that really is
      // authenticated-only must keep sending the visitor to log in.
      await expect((client as any).request("/api/protected")).rejects.toThrow();

      expect(replace).toHaveBeenCalled();
    });
  });
});
