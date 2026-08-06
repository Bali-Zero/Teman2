import type { IApiClient } from "../types/api-client.types";
import { UserProfile } from "@/types";
import type { BackendLoginResponse, LoginResponse } from "./auth.types";
import { logger } from "@/lib/logger";

type AuthApiClient = Pick<
  IApiClient,
  "request" | "setToken" | "setUserProfile" | "setCsrfToken" | "clearToken"
>;

/**
 * Authentication API methods
 */
export class AuthApi {
  constructor(private client: AuthApiClient) {}

  async login(email: string, pin: string): Promise<LoginResponse> {
    logger.debug("Login attempt started", {
      component: "AuthApi",
      action: "login",
    });

    try {
      const response = await this.client.request<BackendLoginResponse>(
        "/api/auth/login",
        {
          method: "POST",
          body: JSON.stringify({ email, pin }),
        },
        90000, // 90s timeout — backend may cold-start on Fly.io
      );

      logger.debug("API response received", {
        component: "AuthApi",
        action: "login_response",
      });

      if (!response.success || !response.data) {
        logger.error("Login failed - invalid response", {
          component: "AuthApi",
          action: "login_failed",
        });
        throw new Error(response.message || "Login failed");
      }

      // Save CSRF token from response (cookie is also set by backend)
      if (response.data.csrfToken) {
        logger.debug("Setting CSRF token", {
          component: "AuthApi",
          action: "set_csrf",
        });
        this.client.setCsrfToken(response.data.csrfToken);
      }

      // Save token to localStorage (optional enhancement - httpOnly cookies are primary auth)
      logger.debug("Saving token to localStorage (optional)", {
        component: "AuthApi",
        action: "save_token",
      });
      this.client.setToken(response.data.token);
      this.client.setUserProfile(response.data.user);

      logger.info("Login successful", {
        component: "AuthApi",
        action: "login_success",
      });

      // Return frontend-friendly format
      return {
        access_token: response.data.token,
        token_type: response.data.token_type,
        user: response.data.user,
      };
    } catch (error) {
      logger.error("Login error", {
        component: "AuthApi",
        action: "login_error",
      });
      throw error;
    }
  }

  /**
   * FASE 6 — consume a passwordless magic-link token and establish a session.
   *
   * Mirrors `login`: the backend sets the httpOnly cookie and returns the same
   * payload (token + csrfToken + user), which we persist the same way.
   */
  async verifyMagicLink(token: string): Promise<LoginResponse> {
    const response = await this.client.request<BackendLoginResponse>(
      `/api/auth/verify-magic/${encodeURIComponent(token)}`,
      { method: "GET" },
      90000,
    );

    if (!response.success || !response.data) {
      throw new Error(
        response.message || "This sign-in link is invalid or expired.",
      );
    }

    if (response.data.csrfToken) {
      this.client.setCsrfToken(response.data.csrfToken);
    }
    this.client.setToken(response.data.token);
    this.client.setUserProfile(response.data.user);

    return {
      access_token: response.data.token,
      token_type: response.data.token_type,
      user: response.data.user,
    };
  }

  async logout(): Promise<void> {
    // Start the authenticated request before clearing local state so the
    // request captures the current Authorization/CSRF credentials. Do not wait
    // for the network before invalidating the in-memory and persisted session.
    const serverInvalidation = this.client.request<void>("/api/auth/logout", {
      method: "POST",
    });
    this.client.clearToken();
    await serverInvalidation;
  }

  async getProfile(): Promise<UserProfile> {
    const profile = await this.client.request<UserProfile>("/api/auth/profile");
    this.client.setUserProfile(profile);
    return profile;
  }
}
