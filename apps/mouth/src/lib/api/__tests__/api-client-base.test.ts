import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ApiClientBase } from "../client";
import { safeStorage } from "@/lib/utils/storage";
import { logger } from "@/lib/logger";

// Mock dependencies
vi.mock("@/lib/utils/storage", () => ({
  safeStorage: {
    getItem: vi.fn(),
    setItem: vi.fn(),
    removeItem: vi.fn(),
  },
}));

vi.mock("@/lib/logger", () => ({
  logger: {
    debug: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}));

describe("ApiClientBase", () => {
  let client: ApiClientBase;
  const baseUrl = "https://api.example.com";

  beforeEach(() => {
    vi.clearAllMocks();

    // Reset safeStorage to return null by default
    vi.mocked(safeStorage.getItem).mockReturnValue(null);
    vi.mocked(safeStorage.setItem).mockReturnValue(true);

    global.fetch = vi.fn();

    // Mock document.cookie for CSRF tests
    Object.defineProperty(document, "cookie", {
      writable: true,
      value: "",
    });

    // Mock window.location
    delete (window as any).location;
    (window as any).location = {
      pathname: "/dashboard",
      replace: vi.fn(),
    };

    client = new ApiClientBase(baseUrl);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("Constructor and Initialization", () => {
    it("should initialize with base URL", () => {
      expect(client.getBaseUrl()).toBe(baseUrl);
    });

    it("should load token from storage on initialization", () => {
      vi.mocked(safeStorage.getItem).mockReturnValue("stored-token");

      const newClient = new ApiClientBase(baseUrl);

      expect(safeStorage.getItem).toHaveBeenCalledWith("auth_token");
      expect(newClient.getToken()).toBe("stored-token");
    });

    it("should load user profile from storage on initialization", () => {
      const mockProfile = {
        id: "1",
        email: "test@example.com",
        name: "Test",
        role: "user",
      };
      vi.mocked(safeStorage.getItem).mockImplementation((key) => {
        if (key === "user_profile") return JSON.stringify(mockProfile);
        return null;
      });

      const newClient = new ApiClientBase(baseUrl);

      expect(newClient.getUserProfile()).toEqual(mockProfile);
    });

    it("should handle malformed profile JSON gracefully", () => {
      vi.mocked(safeStorage.getItem).mockImplementation((key) => {
        if (key === "user_profile") return "invalid-json";
        return null;
      });

      const newClient = new ApiClientBase(baseUrl);

      expect(newClient.getUserProfile()).toBeNull();
    });
  });

  describe("Token Management", () => {
    it("should set token in memory and storage", () => {
      vi.mocked(safeStorage.setItem).mockReturnValue(true);
      vi.mocked(safeStorage.getItem).mockReturnValue("new-token");

      client.setToken("new-token");

      expect(client.getToken()).toBe("new-token");
      expect(safeStorage.setItem).toHaveBeenCalledWith(
        "auth_token",
        "new-token",
      );
    });

    it("should warn when localStorage is blocked", () => {
      vi.mocked(safeStorage.setItem).mockReturnValue(false);

      client.setToken("new-token");

      expect(logger.warn).toHaveBeenCalledWith(
        expect.stringContaining("localStorage blocked"),
        expect.any(Object),
      );
    });

    it("should clear token from memory and storage", () => {
      client.setToken("token-to-clear");
      client.clearToken();

      expect(client.getToken()).toBeNull();
      expect(safeStorage.removeItem).toHaveBeenCalledWith("auth_token");
      expect(safeStorage.removeItem).toHaveBeenCalledWith("user_profile");
    });

    it("should sync token from storage on getToken", () => {
      client.setToken("old-token");
      vi.mocked(safeStorage.getItem).mockReturnValue("new-token-from-storage");

      const token = client.getToken();

      expect(token).toBe("new-token-from-storage");
    });
  });

  describe("User Profile Management", () => {
    it("should set user profile in memory and storage", () => {
      const profile = {
        id: "1",
        email: "user@example.com",
        name: "User",
        role: "admin",
      };
      vi.mocked(safeStorage.setItem).mockReturnValue(true);

      client.setUserProfile(profile);

      expect(client.getUserProfile()).toEqual(profile);
      expect(safeStorage.setItem).toHaveBeenCalledWith(
        "user_profile",
        JSON.stringify(profile),
      );
    });

    it("should warn when localStorage is blocked for profile", () => {
      const profile = {
        id: "1",
        email: "user@example.com",
        name: "User",
        role: "user",
      };
      vi.mocked(safeStorage.setItem).mockReturnValue(false);

      client.setUserProfile(profile);

      expect(logger.warn).toHaveBeenCalledWith(
        expect.stringContaining("localStorage blocked"),
        expect.any(Object),
      );
    });

    it("should sync profile from storage on getUserProfile", () => {
      const oldProfile = {
        id: "1",
        email: "old@example.com",
        name: "Old",
        role: "user",
      };
      const newProfile = {
        id: "2",
        email: "new@example.com",
        name: "New",
        role: "admin",
      };

      client.setUserProfile(oldProfile);
      vi.mocked(safeStorage.getItem).mockReturnValue(
        JSON.stringify(newProfile),
      );

      const profile = client.getUserProfile();

      expect(profile).toEqual(newProfile);
      expect(logger.debug).toHaveBeenCalledWith(
        expect.stringContaining("User profile synced"),
        expect.any(Object),
      );
    });

    it("should handle profile parse errors gracefully", () => {
      const validProfile = {
        id: "1",
        email: "test@example.com",
        name: "Test",
        role: "user",
      };
      client.setUserProfile(validProfile);

      vi.mocked(safeStorage.getItem).mockReturnValue("invalid-json");

      const profile = client.getUserProfile();

      expect(profile).toEqual(validProfile); // Should keep existing profile
      expect(logger.warn).toHaveBeenCalledWith(
        expect.stringContaining("Failed to parse"),
        expect.any(Object),
      );
    });
  });

  describe("Authentication Status", () => {
    it("should return true when token exists", () => {
      vi.mocked(safeStorage.getItem).mockReturnValue("valid-token");
      client.setToken("valid-token");

      expect(client.isAuthenticated()).toBe(true);
    });

    it("should return false when token is null", () => {
      vi.mocked(safeStorage.getItem).mockReturnValue(null);
      client.clearToken();

      expect(client.isAuthenticated()).toBe(false);
    });

    it("should return false when token is empty string", () => {
      vi.mocked(safeStorage.getItem).mockReturnValue("");
      client.setToken("");

      expect(client.isAuthenticated()).toBe(false);
    });
  });

  describe("Role-Based Access", () => {
    it("should identify admin role", () => {
      client.setUserProfile({
        id: "1",
        email: "admin@example.com",
        name: "Admin",
        role: "admin",
      });

      expect(client.isAdmin()).toBe(true);
    });

    it("should identify founder role as admin", () => {
      client.setUserProfile({
        id: "1",
        email: "founder@example.com",
        name: "Founder",
        role: "founder",
      });

      expect(client.isAdmin()).toBe(true);
    });

    it("should identify owner role as admin", () => {
      client.setUserProfile({
        id: "1",
        email: "owner@example.com",
        name: "Owner",
        role: "owner",
      });

      expect(client.isAdmin()).toBe(true);
    });

    it("should identify board role as admin", () => {
      client.setUserProfile({
        id: "1",
        email: "board@example.com",
        name: "Board",
        role: "board",
      });

      expect(client.isAdmin()).toBe(true);
    });

    it("should not identify regular user as admin", () => {
      client.setUserProfile({
        id: "1",
        email: "user@example.com",
        name: "User",
        role: "user",
      });

      expect(client.isAdmin()).toBe(false);
    });

    it("should handle case-insensitive role check", () => {
      client.setUserProfile({
        id: "1",
        email: "admin@example.com",
        name: "Admin",
        role: "ADMIN",
      });

      expect(client.isAdmin()).toBe(true);
    });

    it("should identify board members correctly", () => {
      client.setUserProfile({
        id: "1",
        email: "board@example.com",
        name: "Board",
        role: "board",
      });

      expect(client.isBoard()).toBe(true);
    });

    it("should identify admin as board member", () => {
      client.setUserProfile({
        id: "1",
        email: "admin@example.com",
        name: "Admin",
        role: "admin",
      });

      expect(client.isBoard()).toBe(true);
    });
  });

  describe("Admin Headers", () => {
    it("should return admin headers when user is admin", () => {
      client.setUserProfile({
        id: "1",
        email: "admin@example.com",
        name: "Admin",
        role: "admin",
      });

      const headers = client.getAdminHeaders();

      expect(headers).toEqual({ "X-User-Email": "admin@example.com" });
    });

    it("should throw error when user is not admin", () => {
      client.setUserProfile({
        id: "1",
        email: "user@example.com",
        name: "User",
        role: "user",
      });

      expect(() => client.getAdminHeaders()).toThrow("Admin access required");
    });

    it("should throw error when no user profile exists", () => {
      expect(() => client.getAdminHeaders()).toThrow("Admin access required");
    });
  });

  describe("CSRF Token Management", () => {
    it("should set CSRF token", () => {
      client.setCsrfToken("csrf-token-123");

      expect(client.getCsrfToken()).toBe("csrf-token-123");
    });

    it("should read CSRF token from cookie when not in memory", () => {
      document.cookie = "nz_csrf_token=cookie-csrf-token; path=/";

      const token = client.getCsrfToken();

      expect(token).toBe("cookie-csrf-token");
    });

    it("should prefer memory CSRF token over cookie", () => {
      document.cookie = "nz_csrf_token=cookie-token; path=/";
      client.setCsrfToken("memory-token");

      const token = client.getCsrfToken();

      expect(token).toBe("memory-token");
    });

    it("should clear CSRF token on clearToken", () => {
      client.setCsrfToken("csrf-token");
      client.clearToken();

      expect(client.getCsrfToken()).toBeNull();
    });
  });

  describe("HTTP Request - Success Cases", () => {
    it("should make successful GET request", async () => {
      const mockData = { id: 1, name: "Test" };
      vi.mocked(global.fetch).mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => mockData,
      } as Response);

      const result = await client.request("/test");

      expect(global.fetch).toHaveBeenCalledWith(
        `${baseUrl}/test`,
        expect.objectContaining({
          headers: expect.objectContaining({
            "Content-Type": "application/json",
          }),
          credentials: "include",
        }),
      );
      expect(result).toEqual(mockData);
    });

    it("should include Authorization header when token exists", async () => {
      vi.mocked(safeStorage.getItem).mockReturnValue("test-token");
      client.setToken("test-token");

      vi.mocked(global.fetch).mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({}),
      } as Response);

      await client.request("/test");

      expect(global.fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: "Bearer test-token",
          }),
        }),
      );
    });

    it("should include CSRF header for POST requests", async () => {
      client.setCsrfToken("csrf-token");
      vi.mocked(global.fetch).mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({}),
      } as Response);

      await client.request("/test", { method: "POST" });

      expect(global.fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            "X-CSRF-Token": "csrf-token",
          }),
        }),
      );
    });

    it("should include CSRF header for PUT requests", async () => {
      client.setCsrfToken("csrf-token");
      vi.mocked(global.fetch).mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({}),
      } as Response);

      await client.request("/test", { method: "PUT" });

      expect(global.fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            "X-CSRF-Token": "csrf-token",
          }),
        }),
      );
    });

    it("should include CSRF header for DELETE requests", async () => {
      client.setCsrfToken("csrf-token");
      vi.mocked(global.fetch).mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({}),
      } as Response);

      await client.request("/test", { method: "DELETE" });

      expect(global.fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            "X-CSRF-Token": "csrf-token",
          }),
        }),
      );
    });

    it("should not include Content-Type for FormData", async () => {
      const formData = new FormData();
      formData.append("file", new Blob(["test"]), "test.txt");

      vi.mocked(global.fetch).mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({}),
      } as Response);

      await client.request("/upload", { method: "POST", body: formData });

      const fetchCall = vi.mocked(global.fetch).mock.calls[0][1];
      expect(fetchCall?.headers).not.toHaveProperty("Content-Type");
    });

    it("should handle 204 No Content response", async () => {
      vi.mocked(global.fetch).mockResolvedValue({
        ok: true,
        status: 204,
        headers: new Headers(),
        json: async () => {
          throw new Error("No content");
        },
      } as unknown as Response);

      const result = await client.request("/test", { method: "DELETE" });

      expect(result).toEqual({});
    });

    it("should handle non-JSON responses", async () => {
      vi.mocked(global.fetch).mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "text/plain" }),
        json: async () => {
          throw new Error("Not JSON");
        },
      } as unknown as Response);

      const result = await client.request("/test");

      expect(result).toEqual({});
    });
  });

  describe("HTTP Request - Error Handling", () => {
    it("should handle 401 Unauthorized and redirect to login", async () => {
      client.setToken("expired-token");
      vi.mocked(global.fetch).mockResolvedValue({
        ok: false,
        status: 401,
        headers: new Headers(),
        json: async () => ({ detail: "Token expired" }),
      } as Response);

      await expect(client.request("/test")).rejects.toThrow("Token expired");

      expect(client.getToken()).toBeNull();
      expect(window.location.replace).toHaveBeenCalledWith(
        expect.stringContaining("/login?expired=true"),
      );
    });

    it("should not redirect on 401 if already on login page", async () => {
      (window as any).location.pathname = "/login";
      vi.mocked(global.fetch).mockResolvedValue({
        ok: false,
        status: 401,
        headers: new Headers(),
        json: async () => ({ detail: "Unauthorized" }),
      } as Response);

      await expect(client.request("/test")).rejects.toThrow();

      expect(window.location.replace).not.toHaveBeenCalled();
    });

    it("should handle 422 validation errors", async () => {
      vi.mocked(global.fetch).mockResolvedValue({
        ok: false,
        status: 422,
        headers: new Headers(),
        json: async () => ({
          detail: [
            {
              loc: ["body", "email"],
              msg: "Invalid email",
              type: "value_error",
            },
            {
              loc: ["body", "password"],
              msg: "Too short",
              type: "value_error",
            },
          ],
        }),
      } as Response);

      await expect(client.request("/test", { method: "POST" })).rejects.toThrow(
        "Validation error: body.email: Invalid email, body.password: Too short",
      );
    });

    it("should handle 405 Method Not Allowed", async () => {
      vi.mocked(global.fetch).mockResolvedValue({
        ok: false,
        status: 405,
        headers: new Headers(),
        json: async () => ({ detail: "Method not allowed" }),
      } as Response);

      await expect(client.request("/test", { method: "POST" })).rejects.toThrow(
        "INVALID_METHOD",
      );
    });

    it("should handle generic HTTP errors", async () => {
      vi.mocked(global.fetch).mockResolvedValue({
        ok: false,
        status: 500,
        headers: new Headers(),
        json: async () => ({ detail: "Internal server error" }),
      } as Response);

      await expect(client.request("/test")).rejects.toThrow(
        "Internal server error",
      );
    });

    it("should handle network errors", async () => {
      vi.mocked(global.fetch).mockRejectedValue(new Error("Network error"));

      await expect(client.request("/test")).rejects.toThrow("Network error");
    });

    it("should handle request timeout", async () => {
      vi.mocked(global.fetch).mockImplementation(
        (_url, options) =>
          new Promise((resolve, reject) => {
            const signal = options?.signal as AbortSignal;
            if (signal) {
              signal.addEventListener("abort", () => {
                const error = new Error("Request timeout");
                error.name = "AbortError";
                reject(error);
              });
            }
            setTimeout(() => {
              resolve({
                ok: true,
                status: 200,
                headers: new Headers(),
                json: async () => ({}),
              } as unknown as Response);
            }, 5000);
          }),
      );

      await expect(client.request("/test", {}, 100)).rejects.toThrow(
        "Request timeout",
      );
    });

    it("should handle malformed error response", async () => {
      vi.mocked(global.fetch).mockResolvedValue({
        ok: false,
        status: 500,
        headers: new Headers(),
        json: async () => {
          throw new Error("Invalid JSON");
        },
      } as unknown as Response);

      await expect(client.request("/test")).rejects.toThrow("Request failed");
    });
  });

  describe("Convenience Methods", () => {
    it("should provide post convenience method", async () => {
      vi.mocked(global.fetch).mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({ success: true }),
      } as Response);

      const result = await client.post("/test", { data: "value" });

      expect(global.fetch).toHaveBeenCalledWith(
        `${baseUrl}/test`,
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ data: "value" }),
        }),
      );
      expect(result).toEqual({ success: true });
    });

    it("should handle post without body", async () => {
      vi.mocked(global.fetch).mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({ success: true }),
      } as Response);

      await client.post("/test");

      expect(global.fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          method: "POST",
          body: undefined,
        }),
      );
    });

    it("should support custom timeout in post method", async () => {
      vi.mocked(global.fetch).mockImplementation(
        (_url, options) =>
          new Promise((resolve, reject) => {
            const signal = options?.signal as AbortSignal;
            if (signal) {
              signal.addEventListener("abort", () => {
                const error = new Error("Request timeout");
                error.name = "AbortError";
                reject(error);
              });
            }
            setTimeout(() => {
              resolve({
                ok: true,
                status: 200,
                headers: new Headers(),
                json: async () => ({}),
              } as unknown as Response);
            }, 2000);
          }),
      );

      await expect(client.post("/test", {}, 100)).rejects.toThrow(
        "Request timeout",
      );
    });
  });

  describe("Logging", () => {
    it("should log request start", async () => {
      vi.mocked(global.fetch).mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({}),
      } as Response);

      await client.request("/test");

      expect(logger.debug).toHaveBeenCalledWith(
        "HTTP request starting",
        expect.objectContaining({
          component: "ApiClient",
          action: "request",
        }),
      );
    });

    it("should log response received", async () => {
      vi.mocked(global.fetch).mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({}),
      } as Response);

      await client.request("/test");

      expect(logger.debug).toHaveBeenCalledWith(
        "HTTP response received",
        expect.objectContaining({
          component: "ApiClient",
          action: "response",
        }),
      );
    });

    it("should log 401 redirect warning", async () => {
      vi.mocked(global.fetch).mockResolvedValue({
        ok: false,
        status: 401,
        headers: new Headers(),
        json: async () => ({ detail: "Unauthorized" }),
      } as Response);

      await expect(client.request("/test")).rejects.toThrow();

      expect(logger.warn).toHaveBeenCalledWith(
        expect.stringContaining("Token expired"),
        expect.any(Object),
      );
    });
  });
});
