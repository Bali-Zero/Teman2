import type { IApiClient } from '../types/api-client.types';
import type {
  ZohoConnectionStatus,
  ZohoAuthUrlResponse,
  FoldersResponse,
  EmailListResponse,
  EmailDetail,
  SendEmailParams,
  SendEmailResponse,
  ReplyEmailParams,
  ForwardEmailParams,
  MarkReadParams,
  OperationResponse,
  SaveDraftParams,
  SaveDraftResponse,
  UploadAttachmentResponse,
  EmailSearchParams,
  UnreadCountResponse,
} from './email.types';

const API_PREFIX = '/api/integrations/zoho';

/**
 * Email API client for Zoho Mail integration
 */
export class EmailApi {
  constructor(private client: IApiClient) {}

  // ============================================================================
  // OAuth & Connection
  // ============================================================================

  /**
   * Get OAuth authorization URL to connect Zoho account
   */
  async getAuthUrl(): Promise<ZohoAuthUrlResponse> {
    return this.client.request<ZohoAuthUrlResponse>(`${API_PREFIX}/auth/url`);
  }

  /**
   * Get current Zoho connection status
   */
  async getConnectionStatus(): Promise<ZohoConnectionStatus> {
    return this.client.request<ZohoConnectionStatus>(`${API_PREFIX}/status`);
  }

  /**
   * Disconnect Zoho account
   */
  async disconnect(): Promise<OperationResponse> {
    return this.client.request<OperationResponse>(`${API_PREFIX}/disconnect`, {
      method: 'DELETE',
    });
  }

  // ============================================================================
  // Folders
  // ============================================================================

  /**
   * Get all email folders
   */
  async getFolders(): Promise<FoldersResponse> {
    return this.client.request<FoldersResponse>(`${API_PREFIX}/folders`);
  }

  // ============================================================================
  // Email List & Detail
  // ============================================================================

  /**
   * List emails with optional filtering
   */
  async listEmails(params: EmailSearchParams = {}): Promise<EmailListResponse> {
    const queryParams = new URLSearchParams();

    if (params.folder_id) queryParams.append('folder_id', params.folder_id);
    if (params.query) queryParams.append('search', params.query);
    if (params.limit) queryParams.append('limit', params.limit.toString());
    if (params.offset) queryParams.append('offset', params.offset.toString());
    if (params.is_read !== undefined) queryParams.append('is_read', params.is_read.toString());
    if (params.is_flagged !== undefined) queryParams.append('is_flagged', params.is_flagged.toString());

    const queryString = queryParams.toString();
    const url = `${API_PREFIX}/emails${queryString ? `?${queryString}` : ''}`;

    return this.client.request<EmailListResponse>(url);
  }

  /**
   * Get single email with full content
   */
  async getEmail(messageId: string, folderId?: string): Promise<EmailDetail> {
    const params = folderId ? `?folder_id=${encodeURIComponent(folderId)}` : '';
    return this.client.request<EmailDetail>(`${API_PREFIX}/emails/${messageId}${params}`);
  }

  // ============================================================================
  // Email Operations
  // ============================================================================

  /**
   * Send a new email
   */
  async sendEmail(params: SendEmailParams): Promise<SendEmailResponse> {
    return this.client.request<SendEmailResponse>(
      `${API_PREFIX}/emails`,
      {
        method: 'POST',
        body: JSON.stringify(params),
      },
      60000 // 60s timeout for sending
    );
  }

  /**
   * Reply to an email
   */
  async replyEmail(messageId: string, params: ReplyEmailParams): Promise<SendEmailResponse> {
    return this.client.request<SendEmailResponse>(
      `${API_PREFIX}/emails/${messageId}/reply`,
      {
        method: 'POST',
        body: JSON.stringify(params),
      },
      60000
    );
  }

  /**
   * Forward an email
   */
  async forwardEmail(messageId: string, params: ForwardEmailParams): Promise<SendEmailResponse> {
    return this.client.request<SendEmailResponse>(
      `${API_PREFIX}/emails/${messageId}/forward`,
      {
        method: 'POST',
        body: JSON.stringify(params),
      },
      60000
    );
  }

  /**
   * Mark emails as read/unread
   */
  async markRead(params: MarkReadParams): Promise<OperationResponse> {
    return this.client.request<OperationResponse>(
      `${API_PREFIX}/emails/mark-read`,
      {
        method: 'PATCH',
        body: JSON.stringify(params),
      }
    );
  }

  /**
   * Toggle flag/star on an email
   */
  async toggleFlag(messageId: string, isFlagged: boolean): Promise<OperationResponse> {
    return this.client.request<OperationResponse>(
      `${API_PREFIX}/emails/${messageId}/flag`,
      {
        method: 'PATCH',
        body: JSON.stringify({ is_flagged: isFlagged }),
      }
    );
  }

  /**
   * Delete emails (move to trash)
   */
  async deleteEmails(messageIds: string[]): Promise<OperationResponse> {
    const queryParams = new URLSearchParams();
    messageIds.forEach(id => queryParams.append('message_ids', id));

    return this.client.request<OperationResponse>(
      `${API_PREFIX}/emails?${queryParams.toString()}`,
      {
        method: 'DELETE',
      }
    );
  }

  // ============================================================================
  // Drafts
  // ============================================================================

  /**
   * Save a draft email
   */
  async saveDraft(params: SaveDraftParams): Promise<SaveDraftResponse> {
    return this.client.request<SaveDraftResponse>(
      `${API_PREFIX}/drafts`,
      {
        method: 'POST',
        body: JSON.stringify(params),
      }
    );
  }

  // ============================================================================
  // Attachments
  // ============================================================================

  /**
   * Download an attachment
   */
  async downloadAttachment(messageId: string, attachmentId: string): Promise<Blob> {
    const baseUrl = this.client.getBaseUrl();
    const headers: Record<string, string> = {};

    // Add Authorization header
    const token = this.client.getToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(
      `${baseUrl}${API_PREFIX}/emails/${messageId}/attachments/${attachmentId}`,
      {
        method: 'GET',
        headers,
        credentials: 'include',
      }
    );

    if (!response.ok) {
      throw new Error('Failed to download attachment');
    }

    return response.blob();
  }

  /**
   * Upload an attachment
   */
  async uploadAttachment(file: File): Promise<UploadAttachmentResponse> {
    const formData = new FormData();
    formData.append('file', file);

    return this.client.request<UploadAttachmentResponse>(
      `${API_PREFIX}/attachments`,
      {
        method: 'POST',
        body: formData,
        headers: {}, // Let browser set content-type for FormData
      },
      120000
    );
  }

  // ============================================================================
  // Statistics
  // ============================================================================

  /**
   * Get unread email counts
   */
  async getUnreadCount(): Promise<UnreadCountResponse> {
    return this.client.request<UnreadCountResponse>(`${API_PREFIX}/unread-count`);
  }
}
