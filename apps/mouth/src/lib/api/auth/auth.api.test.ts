import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AuthApi } from './auth.api';
import { ApiClientBase } from '../client';
import type { BackendLoginResponse } from './auth.types';

describe('AuthApi', () => {
  let authApi: AuthApi;
  let mockClient: ApiClientBase;

  beforeEach(() => {
    mockClient = {
      request: vi.fn(),
      setToken: vi.fn(),
      setUserProfile: vi.fn(),
      setCsrfToken: vi.fn(),
      clearToken: vi.fn(),
    } as any;
    authApi = new AuthApi(mockClient);
  });

  describe('login', () => {
    it('should login successfully and set token/profile', async () => {
      const mockResponse: BackendLoginResponse = {
        success: true,
        message: 'Login successful',
        data: {
          token: 'test-token',
          token_type: 'Bearer',
          expiresIn: 3600,
          user: {
            id: '123',
            email: 'test@example.com',
            name: 'Test User',
            role: 'user',
          },
          csrfToken: 'csrf-token',
        },
      };

      (mockClient.request as any).mockResolvedValueOnce(mockResponse);

      const result = await authApi.login('test@example.com', '1234');

      expect(mockClient.request).toHaveBeenCalledWith('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email: 'test@example.com', pin: '1234' }),
      });
      expect(mockClient.setCsrfToken).toHaveBeenCalledWith('csrf-token');
      expect(mockClient.setToken).toHaveBeenCalledWith('test-token');
      expect(mockClient.setUserProfile).toHaveBeenCalledWith(mockResponse.data.user);
      expect(result).toEqual({
        access_token: 'test-token',
        token_type: 'Bearer',
        user: mockResponse.data.user,
      });
    });

    it('should throw error on failed login', async () => {
      const mockResponse: BackendLoginResponse = {
        success: false,
        message: 'Invalid credentials',
        data: undefined as any,
      };

      (mockClient.request as any).mockResolvedValueOnce(mockResponse);

      await expect(authApi.login('test@example.com', 'wrong')).rejects.toThrow(
        'Invalid credentials'
      );
    });

    it('should handle login without CSRF token', async () => {
      const mockResponse: BackendLoginResponse = {
        success: true,
        message: 'Login successful',
        data: {
          token: 'test-token',
          token_type: 'Bearer',
          expiresIn: 3600,
          user: {
            id: '123',
            email: 'test@example.com',
            name: 'Test User',
            role: 'user',
          },
        },
      };

      (mockClient.request as any).mockResolvedValueOnce(mockResponse);

      await authApi.login('test@example.com', '1234');

      expect(mockClient.setCsrfToken).not.toHaveBeenCalled();
    });
  });

  describe('logout', () => {
    it('should logout and clear token', async () => {
      (mockClient.request as any).mockResolvedValueOnce({});

      await authApi.logout();

      expect(mockClient.request).toHaveBeenCalledWith('/api/auth/logout', {
        method: 'POST',
      });
      expect(mockClient.clearToken).toHaveBeenCalled();
    });

    it('should clear token even if logout request fails', async () => {
      (mockClient.request as any).mockRejectedValueOnce(new Error('Network error'));

      await expect(authApi.logout()).rejects.toThrow('Network error');
      expect(mockClient.clearToken).toHaveBeenCalled();
    });
  });

  describe('getProfile', () => {
    it('should get and set user profile', async () => {
      const profile = {
        id: '123',
        email: 'test@example.com',
        name: 'Test User',
        role: 'user',
      };

      (mockClient.request as any).mockResolvedValueOnce(profile);

      const result = await authApi.getProfile();

      expect(mockClient.request).toHaveBeenCalledWith('/api/auth/profile');
      expect(mockClient.setUserProfile).toHaveBeenCalledWith(profile);
      expect(result).toEqual(profile);
    });
  });
});

