import { UserProfile } from '@/types';

// Backend response types (aligned with actual backend)
export interface BackendLoginResponse {
  success: boolean;
  message: string;
  data: {
    token: string;
    token_type: string;
    expiresIn: number;
    user: UserProfile;
    csrfToken?: string; // CSRF token for httpOnly cookie auth
  };
}

// Frontend-friendly login response
export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: UserProfile;
}

