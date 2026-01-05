import type { IApiClient } from '../types/api-client.types';
import { UserProfile } from '@/types';
import type { BackendLoginResponse, LoginResponse } from './auth.types';

/**
 * Authentication API methods
 */
export class AuthApi {
  constructor(private client: IApiClient) {}

  async login(email: string, pin: string): Promise<LoginResponse> {
    console.log('[AUTH] 🔐 Login attempt started', { email, pinLength: pin.length });
    console.log('[AUTH] 📱 Device info:', {
      userAgent: navigator.userAgent,
      platform: navigator.platform,
      cookieEnabled: navigator.cookieEnabled,
      storageAvailable: typeof localStorage !== 'undefined',
    });

    try {
      const response = await this.client.request<BackendLoginResponse>('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, pin }),
      });

      console.log('[AUTH] ✅ API response received:', {
        success: response.success,
        hasData: !!response.data,
        hasToken: !!response.data?.token,
        message: response.message,
      });

      if (!response.success || !response.data) {
        console.error('[AUTH] ❌ Login failed - invalid response:', response.message);
        throw new Error(response.message || 'Login failed');
      }

      // Save CSRF token from response (cookie is also set by backend)
      if (response.data.csrfToken) {
        console.log('[AUTH] 🔑 Setting CSRF token');
        this.client.setCsrfToken(response.data.csrfToken);
      }

      // Save token to localStorage (optional enhancement - httpOnly cookies are primary auth)
      console.log('[AUTH] 💾 Attempting to save token to localStorage (optional)');
      this.client.setToken(response.data.token);
      this.client.setUserProfile(response.data.user);

      console.log('[AUTH] 🎉 Login successful! (Auth via httpOnly cookies)');

      // Return frontend-friendly format
      return {
        access_token: response.data.token,
        token_type: response.data.token_type,
        user: response.data.user,
      };
    } catch (error) {
      console.error('[AUTH] 💥 Login error:', {
        error,
        message: error instanceof Error ? error.message : 'Unknown error',
        stack: error instanceof Error ? error.stack : undefined,
      });
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

