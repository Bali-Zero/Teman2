import type { IApiClient } from '../types/api-client.types';
import { UserProfile } from '@/types';
import type { BackendLoginResponse, LoginResponse } from './auth.types';
import { logger } from '@/lib/logger';

/**
 * Authentication API methods
 */
export class AuthApi {
  constructor(private client: IApiClient) {}

  async login(email: string, pin: string): Promise<LoginResponse> {
    logger.debug('Login attempt started', {
      component: 'AuthApi',
      action: 'login',
      metadata: {
        email,
        pinLength: pin.length,
        userAgent: navigator.userAgent,
        platform: navigator.platform,
        cookieEnabled: navigator.cookieEnabled,
        storageAvailable: typeof localStorage !== 'undefined',
      },
    });

    try {
      const response = await this.client.request<BackendLoginResponse>('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, pin }),
      });

      logger.debug('API response received', {
        component: 'AuthApi',
        action: 'login_response',
        metadata: {
          success: response.success,
          hasData: !!response.data,
          hasToken: !!response.data?.token,
          message: response.message,
        },
      });

      if (!response.success || !response.data) {
        logger.error('Login failed - invalid response', {
          component: 'AuthApi',
          action: 'login_failed',
          metadata: { message: response.message },
        });
        throw new Error(response.message || 'Login failed');
      }

      // Save CSRF token from response (cookie is also set by backend)
      if (response.data.csrfToken) {
        logger.debug('Setting CSRF token', {
          component: 'AuthApi',
          action: 'set_csrf',
        });
        this.client.setCsrfToken(response.data.csrfToken);
      }

      // Save token to localStorage (optional enhancement - httpOnly cookies are primary auth)
      logger.debug('Saving token to localStorage (optional)', {
        component: 'AuthApi',
        action: 'save_token',
      });
      this.client.setToken(response.data.token);
      this.client.setUserProfile(response.data.user);

      logger.info('Login successful', {
        component: 'AuthApi',
        action: 'login_success',
        user: response.data.user.email,
      });

      // Return frontend-friendly format
      return {
        access_token: response.data.token,
        token_type: response.data.token_type,
        user: response.data.user,
      };
    } catch (error) {
      logger.error('Login error', {
        component: 'AuthApi',
        action: 'login_error',
        metadata: {
          message: error instanceof Error ? error.message : 'Unknown error',
        },
      }, error instanceof Error ? error : new Error(String(error)));
      throw error;
    }
  }

  async logout(): Promise<void> {
    try {
      await this.client.request<void>('/api/auth/logout', { method: 'POST' });
    } finally {
      this.client.clearToken();
    }
  }

  async getProfile(): Promise<UserProfile> {
    const profile = await this.client.request<UserProfile>('/api/auth/profile');
    this.client.setUserProfile(profile);
    return profile;
  }
}

