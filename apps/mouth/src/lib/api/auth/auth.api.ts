import { ApiClientBase } from '../client';
import { UserProfile } from '@/types';
import type { BackendLoginResponse, LoginResponse } from './auth.types';

/**
 * Authentication API methods
 */
export class AuthApi {
  constructor(private client: ApiClientBase) {}

  async login(email: string, pin: string): Promise<LoginResponse> {
    // Access protected request method via type assertion
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const response = await (this.client as any).request('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, pin }),
    }) as BackendLoginResponse;

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
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      await (this.client as any).request('/api/auth/logout', { method: 'POST' });
    } finally {
      this.client.clearToken();
    }
  }

  async getProfile(): Promise<UserProfile> {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const profile = await (this.client as any).request('/api/auth/profile') as UserProfile;
    this.client.setUserProfile(profile);
    return profile;
  }
}

