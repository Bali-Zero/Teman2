import { ApiClientBase } from '../client';

/**
 * File upload API methods
 */
export class UploadApi {
  constructor(private client: ApiClientBase) {}

  async uploadFile(
    file: File
  ): Promise<{ success: boolean; url: string; filename: string; type: string }> {
    const formData = new FormData();
    formData.append('file', file);

    // Build headers with CSRF token (Content-Type is set automatically by fetch for FormData)
    const headers: Record<string, string> = {};

    // Add CSRF token for cookie-based auth
    const csrf = this.client.getCsrfToken();
    if (csrf) {
      headers['X-CSRF-Token'] = csrf;
    }

    // Keep Authorization header for backward compatibility
    const token = this.client.getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const baseUrl = this.client.getBaseUrl();
    const response = await fetch(`${baseUrl}/media/upload`, {
      method: 'POST',
      headers,
      body: formData,
      credentials: 'include', // Send httpOnly cookies
    });

    if (!response.ok) {
      throw new Error(`Upload failed: ${response.statusText}`);
    }

    return response.json();
  }
}

