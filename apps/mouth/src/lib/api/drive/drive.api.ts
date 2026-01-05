import type { IApiClient } from '../types/api-client.types';
import type {
  ConnectionStatus,
  FileItem,
  FileListResponse,
  UserFolderResponse,
  AuthUrlResponse,
  DisconnectResponse,
  CreateFolderRequest,
  CreateDocRequest,
  OperationResponse,
  UploadProgress,
  DocType,
  PermissionItem,
  AddPermissionRequest,
  UpdatePermissionRequest,
} from './drive.types';

/**
 * Google Drive API Client
 *
 * Uses Team Drive with Service Account - no individual OAuth needed.
 * All authenticated team members can access shared company files.
 */
export class DriveApi {
  constructor(private client: IApiClient) {}

  /**
   * Get Google Drive connection status
   * Uses Team Drive (Service Account) - always connected if configured
   */
  async getStatus(): Promise<ConnectionStatus> {
    try {
      const response = await this.client.request<{
        status: string;
        service_account: string;
        files_accessible: boolean;
      }>('/api/drive/status');

      return {
        connected: response.status === 'connected',
        configured: true,
        root_folder_id: null,
      };
    } catch (error) {
      // If Team Drive not available, fallback to old OAuth system
      try {
        return this.client.request<ConnectionStatus>('/integrations/google-drive/status');
      } catch {
        return {
          connected: false,
          configured: false,
          root_folder_id: null,
        };
      }
    }
  }

  /**
   * Get OAuth authorization URL (legacy - not needed with Team Drive)
   */
  async getAuthUrl(): Promise<AuthUrlResponse> {
    return this.client.request<AuthUrlResponse>('/integrations/google-drive/auth/url');
  }

  /**
   * Disconnect Google Drive (legacy - Team Drive doesn't need disconnect)
   */
  async disconnect(): Promise<DisconnectResponse> {
    // Team Drive uses Service Account - no individual disconnect
    return { success: true };
  }

  /**
   * List files in a folder
   * Uses new Team Drive endpoint
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
    const url = `/api/drive/files${queryString ? `?${queryString}` : ''}`;

    const response = await this.client.request<{
      files: Array<{
        id: string;
        name: string;
        type: string;
        mimeType: string;
        size: number;
        modifiedTime?: string;
        webViewLink?: string;
        thumbnailLink?: string;
      }>;
      next_page_token: string | null;
    }>(url);

    // Transform to frontend format
    const files: FileItem[] = response.files.map((f) => ({
      id: f.id,
      name: f.name,
      mime_type: f.mimeType,
      size: f.size,
      modified_time: f.modifiedTime,
      web_view_link: f.webViewLink,
      thumbnail_link: f.thumbnailLink,
      is_folder: f.type === 'folder',
    }));

    // Get breadcrumb if in a folder
    let breadcrumb: { id: string; name: string }[] = [];
    if (params.folder_id) {
      try {
        breadcrumb = await this.client.request<{ id: string; name: string }[]>(
          `/api/drive/folders/${params.folder_id}/path`
        );
      } catch {
        // Ignore breadcrumb errors
      }
    }

    return {
      files,
      next_page_token: response.next_page_token,
      breadcrumb,
    };
  }

  /**
   * Get file metadata
   */
  async getFile(fileId: string): Promise<FileItem> {
    const response = await this.client.request<{
      id: string;
      name: string;
      type: string;
      mimeType: string;
      size: number;
      modifiedTime?: string;
      webViewLink?: string;
      thumbnailLink?: string;
    }>(`/api/drive/files/${fileId}`);

    return {
      id: response.id,
      name: response.name,
      mime_type: response.mimeType,
      size: response.size,
      modified_time: response.modifiedTime,
      web_view_link: response.webViewLink,
      thumbnail_link: response.thumbnailLink,
      is_folder: response.type === 'folder',
    };
  }

  /**
   * Search files by name
   */
  async searchFiles(query: string, pageSize = 20): Promise<FileItem[]> {
    const queryParams = new URLSearchParams();
    queryParams.append('q', query);
    queryParams.append('page_size', pageSize.toString());

    const response = await this.client.request<{
      query: string;
      results: Array<{
        id: string;
        name: string;
        type: string;
        mimeType: string;
        size: number;
        modifiedTime?: string;
        webViewLink?: string;
      }>;
      count: number;
    }>(`/api/drive/search?${queryParams.toString()}`);

    return response.results.map((f) => ({
      id: f.id,
      name: f.name,
      mime_type: f.mimeType,
      size: f.size,
      modified_time: f.modifiedTime,
      web_view_link: f.webViewLink,
      is_folder: f.type === 'folder',
    }));
  }

  /**
   * Get current user's personal folder
   */
  async getMyFolder(): Promise<UserFolderResponse> {
    // With Team Drive, users can navigate to their folder manually
    return {
      found: false,
      message: 'Navigate to your folder in the file browser',
    };
  }

  /**
   * Get download URL for a file
   */
  getDownloadUrl(fileId: string): string {
    // This will be called from the frontend to download files
    return `/api/drive/files/${fileId}/download`;
  }

  // ============== CRUD Operations ==============

  /**
   * Upload a file to Google Drive
   */
  async uploadFile(
    file: File,
    parentId: string,
    onProgress?: (progress: UploadProgress) => void
  ): Promise<OperationResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('parent_id', parentId);

    // Use XMLHttpRequest for progress tracking
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();

      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable && onProgress) {
          onProgress({
            loaded: event.loaded,
            total: event.total,
            percentage: Math.round((event.loaded / event.total) * 100),
          });
        }
      });

      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const response = JSON.parse(xhr.responseText);
            resolve({
              success: true,
              file: response.file ? this.transformFileResponse(response.file) : undefined,
              message: response.message,
            });
          } catch {
            resolve({ success: true });
          }
        } else {
          try {
            const error = JSON.parse(xhr.responseText);
            reject(new Error(error.detail || 'Upload failed'));
          } catch {
            reject(new Error(`Upload failed with status ${xhr.status}`));
          }
        }
      });

      xhr.addEventListener('error', () => {
        reject(new Error('Network error during upload'));
      });

      // Get auth token from client
      const baseUrl = (this.client as unknown as { baseUrl: string }).baseUrl || '';
      xhr.open('POST', `${baseUrl}/api/drive/files/upload`);

      // Set Authorization header
      const token = this.client.getToken();
      if (token) {
        xhr.setRequestHeader('Authorization', `Bearer ${token}`);
      }

      // Copy auth headers if available
      if (typeof document !== 'undefined') {
        // Browser: cookies will be sent automatically with credentials
        xhr.withCredentials = true;

        // CRITICAL: Add CSRF token for cookie-based auth (required by backend middleware)
        const csrfCookie = document.cookie.split('; ').find(row => row.startsWith('nz_csrf_token='));
        if (csrfCookie) {
          const csrfToken = csrfCookie.split('=')[1];
          xhr.setRequestHeader('X-CSRF-Token', csrfToken);
        }
      }

      xhr.send(formData);
    });
  }

  /**
   * Create a new folder
   */
  async createFolder(request: CreateFolderRequest): Promise<OperationResponse> {
    const response = await this.client.request<{
      success: boolean;
      file?: {
        id: string;
        name: string;
        type: string;
        mimeType: string;
        webViewLink?: string;
      };
      message?: string;
    }>('/api/drive/folders', {
      method: 'POST',
      body: JSON.stringify(request),
    });

    return {
      success: response.success,
      file: response.file ? this.transformFileResponse(response.file) : undefined,
      message: response.message,
    };
  }

  /**
   * Create a new Google Doc/Sheet/Slides
   */
  async createDoc(request: CreateDocRequest): Promise<OperationResponse> {
    const response = await this.client.request<{
      success: boolean;
      file?: {
        id: string;
        name: string;
        type: string;
        mimeType: string;
        webViewLink?: string;
      };
      message?: string;
    }>('/api/drive/files/create', {
      method: 'POST',
      body: JSON.stringify(request),
    });

    return {
      success: response.success,
      file: response.file ? this.transformFileResponse(response.file) : undefined,
      message: response.message,
    };
  }

  /**
   * Rename a file or folder
   */
  async renameFile(fileId: string, newName: string): Promise<OperationResponse> {
    const response = await this.client.request<{
      success: boolean;
      file?: {
        id: string;
        name: string;
        type: string;
        mimeType: string;
        webViewLink?: string;
      };
      message?: string;
    }>(`/api/drive/files/${fileId}/rename`, {
      method: 'PATCH',
      body: JSON.stringify({ new_name: newName }),
    });

    return {
      success: response.success,
      file: response.file ? this.transformFileResponse(response.file) : undefined,
      message: response.message,
    };
  }

  /**
   * Delete a file or folder (move to trash)
   */
  async deleteFile(fileId: string): Promise<OperationResponse> {
    const response = await this.client.request<{
      success: boolean;
      message?: string;
    }>(`/api/drive/files/${fileId}`, {
      method: 'DELETE',
    });

    return {
      success: response.success,
      message: response.message,
    };
  }

  /**
   * Move a file or folder to a new parent
   */
  async moveFile(
    fileId: string,
    newParentId: string,
    oldParentId?: string
  ): Promise<OperationResponse> {
    const response = await this.client.request<{
      success: boolean;
      file?: {
        id: string;
        name: string;
        type: string;
        mimeType: string;
        webViewLink?: string;
      };
      message?: string;
    }>(`/api/drive/files/${fileId}/move`, {
      method: 'PATCH',
      body: JSON.stringify({
        new_parent_id: newParentId,
        old_parent_id: oldParentId,
      }),
    });

    return {
      success: response.success,
      file: response.file ? this.transformFileResponse(response.file) : undefined,
      message: response.message,
    };
  }

  /**
   * Copy a file
   */
  async copyFile(
    fileId: string,
    newName?: string,
    parentFolderId?: string
  ): Promise<OperationResponse> {
    const response = await this.client.request<{
      success: boolean;
      file?: {
        id: string;
        name: string;
        type: string;
        mimeType: string;
        webViewLink?: string;
      };
      message?: string;
    }>(`/api/drive/files/${fileId}/copy`, {
      method: 'POST',
      body: JSON.stringify({
        new_name: newName,
        parent_folder_id: parentFolderId,
      }),
    });

    return {
      success: response.success,
      file: response.file ? this.transformFileResponse(response.file) : undefined,
      message: response.message,
    };
  }

  // ============== Bulk Operations ==============

  /**
   * Delete multiple files
   */
  async deleteFiles(fileIds: string[]): Promise<{ success: boolean; failed: string[] }> {
    const failed: string[] = [];

    await Promise.all(
      fileIds.map(async (id) => {
        try {
          await this.deleteFile(id);
        } catch {
          failed.push(id);
        }
      })
    );

    return {
      success: failed.length === 0,
      failed,
    };
  }

  /**
   * Move multiple files
   */
  async moveFiles(
    fileIds: string[],
    newParentId: string
  ): Promise<{ success: boolean; failed: string[] }> {
    const failed: string[] = [];

    await Promise.all(
      fileIds.map(async (id) => {
        try {
          await this.moveFile(id, newParentId);
        } catch {
          failed.push(id);
        }
      })
    );

    return {
      success: failed.length === 0,
      failed,
    };
  }

  // ============== Helper Methods ==============

  /**
   * Transform backend file response to FileItem
   */
  private transformFileResponse(file: {
    id: string;
    name: string;
    type?: string;
    mimeType?: string;
    size?: number;
    modifiedTime?: string;
    webViewLink?: string;
    thumbnailLink?: string;
  }): FileItem {
    return {
      id: file.id,
      name: file.name,
      mime_type: file.mimeType || '',
      size: file.size,
      modified_time: file.modifiedTime,
      web_view_link: file.webViewLink,
      thumbnail_link: file.thumbnailLink,
      is_folder: file.type === 'folder' || file.mimeType === 'application/vnd.google-apps.folder',
    };
  }

  /**
   * Get human-readable doc type label
   */
  static getDocTypeLabel(docType: DocType): string {
    const labels: Record<DocType, string> = {
      document: 'Google Docs',
      spreadsheet: 'Google Sheets',
      presentation: 'Google Slides',
    };
    return labels[docType];
  }

  /**
   * Get doc type icon
   */
  static getDocTypeIcon(docType: DocType): string {
    const icons: Record<DocType, string> = {
      document: '📄',
      spreadsheet: '📊',
      presentation: '📽️',
    };
    return icons[docType];
  }

  // ============== Permission Management (Board only) ==============

  /**
   * List permissions for a file/folder
   */
  async listPermissions(fileId: string): Promise<PermissionItem[]> {
    return this.client.request<PermissionItem[]>(`/api/drive/files/${fileId}/permissions`);
  }

  /**
   * Add permission for a user
   */
  async addPermission(fileId: string, request: AddPermissionRequest): Promise<PermissionItem> {
    return this.client.request<PermissionItem>(`/api/drive/files/${fileId}/permissions`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  /**
   * Update permission role
   */
  async updatePermission(
    fileId: string,
    permissionId: string,
    request: UpdatePermissionRequest
  ): Promise<PermissionItem> {
    return this.client.request<PermissionItem>(
      `/api/drive/files/${fileId}/permissions/${permissionId}`,
      {
        method: 'PATCH',
        body: JSON.stringify(request),
      }
    );
  }

  /**
   * Remove permission
   */
  async removePermission(fileId: string, permissionId: string): Promise<{ success: boolean }> {
    return this.client.request<{ success: boolean }>(
      `/api/drive/files/${fileId}/permissions/${permissionId}`,
      {
        method: 'DELETE',
      }
    );
  }
}
