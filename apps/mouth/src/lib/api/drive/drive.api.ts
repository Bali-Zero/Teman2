import type { IApiClient } from '../types/api-client.types';
import type {
  ConnectionStatus,
  FileItem,
  FileListResponse,
  UserFolderResponse,
  AuthUrlResponse,
  DisconnectResponse,
} from './drive.types';

/**
 * Google Drive API Client
 *
 * Handles OAuth flow and file operations for Google Drive integration.
 */
export class DriveApi {
  constructor(private client: IApiClient) {}

  /**
   * Get Google Drive connection status
   */
  async getStatus(): Promise<ConnectionStatus> {
    return this.client.request<ConnectionStatus>('/integrations/google-drive/status');
  }

  /**
   * Get OAuth authorization URL to connect Google Drive
   */
  async getAuthUrl(): Promise<AuthUrlResponse> {
    return this.client.request<AuthUrlResponse>('/integrations/google-drive/auth/url');
  }

  /**
   * Disconnect Google Drive
   */
  async disconnect(): Promise<DisconnectResponse> {
    return this.client.request<DisconnectResponse>('/integrations/google-drive/disconnect', {
      method: 'POST',
    });
  }

  /**
   * List files in a folder
   */
  async listFiles(params: {
    folder_id?: string;
    page_token?: string;
    page_size?: number;
  } = {}): Promise<FileListResponse> {
    const queryParams = new URLSearchParams();
    if (params.folder_id) queryParams.append('folder_id', params.folder_id);
    if (params.page_token) queryParams.append('page_token', params.page_token);
    if (params.page_size) queryParams.append('page_size', params.page_size.toString());

    const queryString = queryParams.toString();
    const url = `/integrations/google-drive/files${queryString ? `?${queryString}` : ''}`;

    return this.client.request<FileListResponse>(url);
  }

  /**
   * Get file metadata
   */
  async getFile(fileId: string): Promise<FileItem> {
    return this.client.request<FileItem>(`/integrations/google-drive/files/${fileId}`);
  }

  /**
   * Search files by name
   */
  async searchFiles(query: string, pageSize = 20): Promise<FileItem[]> {
    const queryParams = new URLSearchParams();
    queryParams.append('q', query);
    queryParams.append('page_size', pageSize.toString());

    return this.client.request<FileItem[]>(
      `/integrations/google-drive/search?${queryParams.toString()}`
    );
  }

  /**
   * Get current user's personal folder
   */
  async getMyFolder(): Promise<UserFolderResponse> {
    return this.client.request<UserFolderResponse>('/integrations/google-drive/my-folder');
  }
}
