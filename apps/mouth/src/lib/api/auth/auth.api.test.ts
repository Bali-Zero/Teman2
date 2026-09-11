import { describe, it, expect, vi, beforeEach } from "vitest";

const { mockLoggerDebug, mockLoggerError, mockLoggerInfo } = vi.hoisted(() => ({
  mockLoggerDebug: vi.fn(),
  mockLoggerError: vi.fn(),
  mockLoggerInfo: vi.fn(),
}));

vi.mock("@/lib/logger", () => ({
  logger: {
    debug: mockLoggerDebug,
    error: mockLoggerError,
    info: mockLoggerInfo,
  },
}));

import { AuthApi } from "./auth.api";
import { ApiClientBase } from "../client";
import type { BackendLoginResponse } from "./auth.types";

describe("AuthApi", () => {
  let authApi: AuthApi;
  let mockClient: ApiClientBase;
  let mockRequest: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
    mockRequest = vi.fn();
    mockClient = {
      request: mockRequest,
      setToken: vi.fn(),
      setUserProfile: vi.fn(),
      setCsrfToken: vi.fn(),
      clearToken: vi.fn(),
    } as any;
    authApi = new AuthApi(mockClient);
  });

  describe("login", () => {
    it("should login successfully and set token/profile", async () => {
      const mockResponse: BackendLoginResponse = {
        success: true,
        message: "Login successful",
        data: {
          token: "test-token",
          token_type: "Bearer",
          expiresIn: 3600,
          user: {
            id: "123",
            email: "test@example.com",
            name: "Test User",
            role: "user",
          },
          csrfToken: "csrf-token",
        },
      };

      mockRequest.mockResolvedValueOnce(mockResponse);

      const result = await authApi.login("test@example.com", "1234");

      expect(mockRequest).toHaveBeenCalledWith(
        "/api/auth/login",
        {
          method: "POST",
          body: JSON.stringify({ email: "test@example.com", pin: "1234" }),
        },
        90000,
      );
      expect(mockClient.setCsrfToken).toHaveBeenCalledWith("csrf-token");
      expect(mockClient.setToken).toHaveBeenCalledWith("test-token");
      expect(mockClient.setUserProfile).toHaveBeenCalledWith(
        mockResponse.data.user,
      );
      expect(result).toEqual({
        access_token: "test-token",
        token_type: "Bearer",
        user: mockResponse.data.user,
      });
    });

    it("should throw error on failed login", async () => {
      const mockResponse: BackendLoginResponse = {
        success: false,
        message: "Invalid credentials",
        data: undefined as any,
      };

      mockRequest.mockResolvedValueOnce(mockResponse);

      await expect(authApi.login("test@example.com", "wrong")).rejects.toThrow(
        "Invalid credentials",
      );
    });

    it("records expected client denials without error-level telemetry", async () => {
      const denied = Object.assign(new Error("Portal access unavailable"), {
        status: 403,
      });
      mockRequest.mockRejectedValueOnce(denied);

      await expect(
        authApi.login("synthetic.disabled@example.test", "1234"),
      ).rejects.toBe(denied);

      expect(mockLoggerInfo).toHaveBeenCalledWith("Login denied", {
        component: "AuthApi",
        action: "login_denied",
        code: 403,
      });
      expect(mockLoggerError).not.toHaveBeenCalled();
    });

    it("should handle login without CSRF token", async () => {
      const mockResponse: BackendLoginResponse = {
        success: true,
        message: "Login successful",
        data: {
          token: "test-token",
          token_type: "Bearer",
          expiresIn: 3600,
          user: {
            id: "123",
            email: "test@example.com",
            name: "Test User",
            role: "user",
          },
        },
      };

      mockRequest.mockResolvedValueOnce(mockResponse);

      await authApi.login("test@example.com", "1234");

      expect(mockClient.setCsrfToken).not.toHaveBeenCalled();
    });

    it("never forwards email, credentials, response messages, or raw errors to telemetry", async () => {
      const email = "synthetic.private@example.test";
      const pin = "781245";
      const responseMessage = "synthetic account detail from backend";
      const rawError = Object.assign(new Error("synthetic backend detail"), {
        response: { data: { email, pin } },
      });

      mockRequest.mockResolvedValueOnce({
        success: false,
        message: responseMessage,
        data: undefined as never,
      } satisfies BackendLoginResponse);
      await expect(authApi.login(email, pin)).rejects.toThrow(responseMessage);

      mockRequest.mockRejectedValueOnce(rawError);
      await expect(authApi.login(email, pin)).rejects.toBe(rawError);

      const telemetry = JSON.stringify({
        debug: mockLoggerDebug.mock.calls,
        error: mockLoggerError.mock.calls,
        info: mockLoggerInfo.mock.calls,
      });
      expect(telemetry).not.toContain(email);
      expect(telemetry).not.toContain(pin);
      expect(telemetry).not.toContain(responseMessage);
      expect(telemetry).not.toContain("synthetic backend detail");
      expect(mockLoggerError).toHaveBeenCalledWith("Login error", {
        component: "AuthApi",
        action: "login_error",
      });
    });
  });

  describe("logout", () => {
    it("should logout and clear token", async () => {
      mockRequest.mockResolvedValueOnce({});

      await authApi.logout();

      expect(mockRequest).toHaveBeenCalledWith("/api/auth/logout", {
        method: "POST",
      });
      expect(mockClient.clearToken).toHaveBeenCalled();
    });

    it("should clear token even if logout request fails", async () => {
      mockRequest.mockRejectedValueOnce(new Error("Network error"));

      await expect(authApi.logout()).rejects.toThrow("Network error");
      expect(mockClient.clearToken).toHaveBeenCalled();
    });

    it("clears local auth state while server invalidation is still pending", async () => {
      let resolveLogout!: () => void;
      mockRequest.mockImplementationOnce(
        () =>
          new Promise<void>((resolve) => {
            resolveLogout = resolve;
          }),
      );

      const logoutPromise = authApi.logout();
      const clearCallsWhilePending = vi.mocked(mockClient.clearToken).mock.calls
        .length;

      resolveLogout();
      await logoutPromise;

      expect(clearCallsWhilePending).toBe(1);
    });
  });

  describe("getProfile", () => {
    it("should get and set user profile", async () => {
      const profile = {
        id: "123",
        email: "test@example.com",
        name: "Test User",
        role: "user",
      };

      mockRequest.mockResolvedValueOnce(profile);

      const result = await authApi.getProfile();

      // auth-gates-cookie-primary round 2: getProfile() always forwards a
      // (possibly empty) options object to request() — see the
      // "forwards options" test below for why the second argument exists.
      expect(mockRequest).toHaveBeenCalledWith("/api/auth/profile", {});
      expect(mockClient.setUserProfile).toHaveBeenCalledWith(profile);
      expect(result).toEqual(profile);
    });

    it("should handle profile fetch error", async () => {
      mockRequest.mockRejectedValueOnce(new Error("Unauthorized"));

      await expect(authApi.getProfile()).rejects.toThrow("Unauthorized");
    });

    // auth-gates-cookie-primary round 2: `/api/auth/profile` is bearer-only
    // (FastAPI 0.141.1's HTTPBearer answers 401 to a request with no
    // Authorization header, even one carrying a VALID cookie session). A
    // caller that already plans to classify that failure itself (the
    // workspace layout, useChatPage) must be able to opt out of
    // request()'s own auto-redirect-on-401 — this proves the option
    // reaches request() unchanged, not swallowed or defaulted away.
    it("forwards options through to request() unchanged (redirectOnUnauthorized opt-out)", async () => {
      const profile = {
        id: "1",
        email: "cookie-only@example.com",
        name: "Cookie Only",
        role: "user",
      };
      mockRequest.mockResolvedValueOnce(profile);

      const result = await authApi.getProfile({
        redirectOnUnauthorized: false,
      });

      expect(mockRequest).toHaveBeenCalledWith("/api/auth/profile", {
        redirectOnUnauthorized: false,
      });
      expect(result).toEqual(profile);
    });
  });

  describe("refresh token", () => {
    it("should handle token refresh via cookie", async () => {
      const mockResponse: BackendLoginResponse = {
        success: true,
        message: "Token refreshed",
        data: {
          token: "new-token",
          token_type: "Bearer",
          expiresIn: 3600,
          user: {
            id: "123",
            email: "test@example.com",
            name: "Test User",
            role: "user",
          },
        },
      };

      mockRequest.mockResolvedValueOnce(mockResponse);

      const result = await authApi.login("test@example.com", "1234");

      expect(result.access_token).toBe("new-token");
    });
  });

  describe("network errors", () => {
    it("should handle network timeout on login", async () => {
      mockRequest.mockRejectedValueOnce(new Error("Network timeout"));

      await expect(authApi.login("test@example.com", "1234")).rejects.toThrow(
        "Network timeout",
      );
    });

    it("should handle server error on login", async () => {
      mockRequest.mockRejectedValueOnce(new Error("500 Internal Server Error"));

      await expect(authApi.login("test@example.com", "1234")).rejects.toThrow(
        "500 Internal Server Error",
      );
    });

    it("should handle malformed response", async () => {
      mockRequest.mockResolvedValueOnce({
        success: true,
        message: "OK",
        data: null,
      });

      await expect(authApi.login("test@example.com", "1234")).rejects.toThrow(
        "OK",
      );
    });
  });

  describe("CSRF token handling", () => {
    it("should set CSRF token when provided", async () => {
      const mockResponse: BackendLoginResponse = {
        success: true,
        message: "Login successful",
        data: {
          token: "test-token",
          token_type: "Bearer",
          expiresIn: 3600,
          user: {
            id: "123",
            email: "test@example.com",
            name: "Test User",
            role: "user",
          },
          csrfToken: "csrf-123",
        },
      };

      mockRequest.mockResolvedValueOnce(mockResponse);

      await authApi.login("test@example.com", "1234");

      expect(mockClient.setCsrfToken).toHaveBeenCalledWith("csrf-123");
    });

    it("should not fail when CSRF token is missing", async () => {
      const mockResponse: BackendLoginResponse = {
        success: true,
        message: "Login successful",
        data: {
          token: "test-token",
          token_type: "Bearer",
          expiresIn: 3600,
          user: {
            id: "123",
            email: "test@example.com",
            name: "Test User",
            role: "user",
          },
        },
      };

      mockRequest.mockResolvedValueOnce(mockResponse);

      const result = await authApi.login("test@example.com", "1234");

      expect(result.access_token).toBe("test-token");
      expect(mockClient.setCsrfToken).not.toHaveBeenCalled();
    });
  });

  describe("edge cases", () => {
    it("should handle empty email", async () => {
      mockRequest.mockRejectedValueOnce(new Error("Email is required"));

      await expect(authApi.login("", "1234")).rejects.toThrow(
        "Email is required",
      );
    });

    it("should handle empty PIN", async () => {
      mockRequest.mockRejectedValueOnce(new Error("PIN is required"));

      await expect(authApi.login("test@example.com", "")).rejects.toThrow(
        "PIN is required",
      );
    });

    it("should handle account locked error", async () => {
      const mockResponse: BackendLoginResponse = {
        success: false,
        message: "Account locked due to too many failed attempts",
        data: undefined as any,
      };

      mockRequest.mockResolvedValueOnce(mockResponse);

      await expect(authApi.login("test@example.com", "1234")).rejects.toThrow(
        "Account locked due to too many failed attempts",
      );
    });
  });

  describe("verifyMagicLink", () => {
    it("exchanges a token for a session and persists it", async () => {
      const mockResponse: BackendLoginResponse = {
        success: true,
        message: "Login successful",
        data: {
          token: "magic-token",
          token_type: "Bearer",
          expiresIn: 43200,
          user: {
            id: "7",
            email: "client@example.com",
            name: "Client One",
            role: "client",
          },
          csrfToken: "csrf-magic",
        },
      };
      mockRequest.mockResolvedValueOnce(mockResponse);

      const result = await authApi.verifyMagicLink("raw token/with?chars");

      // token is URL-encoded into the path
      expect(mockRequest).toHaveBeenCalledWith(
        "/api/auth/verify-magic/raw%20token%2Fwith%3Fchars",
        { method: "GET" },
        90000,
      );
      expect(mockClient.setCsrfToken).toHaveBeenCalledWith("csrf-magic");
      expect(mockClient.setToken).toHaveBeenCalledWith("magic-token");
      expect(mockClient.setUserProfile).toHaveBeenCalledWith(
        mockResponse.data.user,
      );
      expect(result.access_token).toBe("magic-token");
    });

    it("throws on an invalid/expired token", async () => {
      const mockResponse: BackendLoginResponse = {
        success: false,
        message: "This sign-in link is invalid or expired.",
        data: undefined as any,
      };
      mockRequest.mockResolvedValueOnce(mockResponse);

      await expect(authApi.verifyMagicLink("bad")).rejects.toThrow(
        "invalid or expired",
      );
      expect(mockClient.setToken).not.toHaveBeenCalled();
    });
  });
});
