import type { IApiClient } from '../types/api-client.types';
import { UserProfile } from '@/types';
import type { BackendLoginResponse, LoginResponse } from './auth.types';

/**
 * Authentication API methods
 */
export class AuthApi {
  constructor(private client: IApiClient) {}

  async login(email: string, pin: string): Promise<LoginResponse> {
    const response = await this.client.request<BackendLoginResponse>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, pin }),
    });

    if (!response.success || !response.data) {
      throw new Error(response.message || 'Login failed');
    }

    // Save CSRF token from response (cookie is also set by backend)
    if (response.data.csrfToken) {
      this.client.setCsrfToken(response.data.csrfToken);
    }

    // Keep token in localStorage for WebSocket backward compatibility
    this.client.setToken(response.data.token);
    this.client.setUserProfile(response.data.user);

    // Return frontend-friendly format
    return {
      access_token: response.data.token,
      token_type: response.data.token_type,
      user: response.data.user,
    };
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

