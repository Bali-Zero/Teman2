/**
 * Slim API client for mail.balizero.com
 *
 * AUTH STRATEGY:
 * - Primary: httpOnly cookies (set by kita.balizero.com on .balizero.com domain)
 * - Secondary: localStorage token (backward compat)
 * - Cookie name for auth check: "bz_session" (httpOnly, set by backend)
 * - All subdomains of .balizero.com share the same auth cookie
 */

import { logger } from "./logger";
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
} from "./email.types";

const ZOHO_PREFIX = "/api/integrations/zoho";

type RequestOptions = {
  method?: string;
  body?: BodyInit | null;
  headers?: Record<string, string>;
};

async function request<T>(
  endpoint: string,
  options: RequestOptions = {},
  timeoutMs: number = 30000,
): Promise<T> {
  const isFormData = options.body instanceof FormData;
  const headers: Record<string, string> = isFormData
    ? { ...(options.headers || {}) }
    : {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      };

  // Add CSRF token for state-changing requests
  const method = (options.method || "GET").toUpperCase();
  if (["POST", "PUT", "DELETE", "PATCH"].includes(method)) {
    if (typeof document !== "undefined") {
      const match = document.cookie.match(/nz_csrf_token=([^;]+)/);
      if (match) headers["X-CSRF-Token"] = match[1];
    }
  }

  // Add localStorage token for backward compat / WebSocket
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("auth_token");
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(endpoint, {
      ...options,
      headers,
      credentials: "include", // CRITICAL: Send httpOnly cookies for .balizero.com
      signal: controller.signal,
    });

    if (response.status === 401) {
      if (typeof window !== "undefined") {
        window.location.replace(
          "https://kita.balizero.com/login?redirect=https://mail.balizero.com",
        );
      }
      throw new Error("Authentication required");
    }

    if (!response.ok && response.status !== 204) {
      const error = await response
        .json()
        .catch(() => ({ detail: "Request failed" }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    if (
      response.status === 204 ||
      !response.headers.get("content-type")?.includes("application/json")
    ) {
      return {} as T;
    }

    return response.json();
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error("Request timeout");
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

export const emailApi = {
  async getAuthUrl(): Promise<ZohoAuthUrlResponse> {
    return request<ZohoAuthUrlResponse>(`${ZOHO_PREFIX}/auth/url`);
  },

  async getConnectionStatus(): Promise<ZohoConnectionStatus> {
    return request<ZohoConnectionStatus>(`${ZOHO_PREFIX}/status`);
  },

  async disconnect(): Promise<OperationResponse> {
    return request<OperationResponse>(`${ZOHO_PREFIX}/disconnect`, {
      method: "DELETE",
    });
  },

  async getFolders(): Promise<FoldersResponse> {
    return request<FoldersResponse>(`${ZOHO_PREFIX}/folders`);
  },

  async listEmails(params: EmailSearchParams = {}): Promise<EmailListResponse> {
    const queryParams = new URLSearchParams();
    if (params.folder_id) queryParams.append("folder_id", params.folder_id);
    if (params.query) queryParams.append("search", params.query);
    if (params.limit) queryParams.append("limit", params.limit.toString());
    if (params.offset) queryParams.append("offset", params.offset.toString());
    if (params.is_read !== undefined)
      queryParams.append("is_read", params.is_read.toString());
    if (params.is_flagged !== undefined)
      queryParams.append("is_flagged", params.is_flagged.toString());
    const qs = queryParams.toString();
    return request<EmailListResponse>(
      `${ZOHO_PREFIX}/emails${qs ? `?${qs}` : ""}`,
    );
  },

  async getEmail(messageId: string, folderId?: string): Promise<EmailDetail> {
    const params = folderId ? `?folder_id=${encodeURIComponent(folderId)}` : "";
    return request<EmailDetail>(`${ZOHO_PREFIX}/emails/${messageId}${params}`);
  },

  async sendEmail(params: SendEmailParams): Promise<SendEmailResponse> {
    return request<SendEmailResponse>(
      `${ZOHO_PREFIX}/emails`,
      { method: "POST", body: JSON.stringify(params) },
      60000,
    );
  },

  async replyEmail(
    messageId: string,
    params: ReplyEmailParams,
  ): Promise<SendEmailResponse> {
    return request<SendEmailResponse>(
      `${ZOHO_PREFIX}/emails/${messageId}/reply`,
      { method: "POST", body: JSON.stringify(params) },
      60000,
    );
  },

  async forwardEmail(
    messageId: string,
    params: ForwardEmailParams,
  ): Promise<SendEmailResponse> {
    return request<SendEmailResponse>(
      `${ZOHO_PREFIX}/emails/${messageId}/forward`,
      { method: "POST", body: JSON.stringify(params) },
      60000,
    );
  },

  async markRead(params: MarkReadParams): Promise<OperationResponse> {
    return request<OperationResponse>(`${ZOHO_PREFIX}/emails/mark-read`, {
      method: "PATCH",
      body: JSON.stringify(params),
    });
  },

  async toggleFlag(
    messageId: string,
    isFlagged: boolean,
  ): Promise<OperationResponse> {
    return request<OperationResponse>(
      `${ZOHO_PREFIX}/emails/${messageId}/flag`,
      { method: "PATCH", body: JSON.stringify({ is_flagged: isFlagged }) },
    );
  },

  async deleteEmails(messageIds: string[]): Promise<OperationResponse> {
    return request<OperationResponse>(`${ZOHO_PREFIX}/emails/delete`, {
      method: "POST",
      body: JSON.stringify({ message_ids: messageIds }),
    });
  },

  async saveDraft(params: SaveDraftParams): Promise<SaveDraftResponse> {
    return request<SaveDraftResponse>(`${ZOHO_PREFIX}/drafts`, {
      method: "POST",
      body: JSON.stringify(params),
    });
  },

  async downloadAttachment(
    messageId: string,
    attachmentId: string,
  ): Promise<Blob> {
    const headers: Record<string, string> = {};
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("auth_token");
      if (token) headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(
      `${ZOHO_PREFIX}/emails/${messageId}/attachments/${attachmentId}`,
      { method: "GET", headers, credentials: "include" },
    );

    if (!response.ok) throw new Error("Failed to download attachment");
    return response.blob();
  },

  async uploadAttachment(file: File): Promise<UploadAttachmentResponse> {
    const formData = new FormData();
    formData.append("file", file);

    return request<UploadAttachmentResponse>(
      `${ZOHO_PREFIX}/attachments`,
      {
        method: "POST",
        body: formData,
        headers: {},
      },
      120000,
    );
  },

  async getUnreadCount(): Promise<UnreadCountResponse> {
    return request<UnreadCountResponse>(`${ZOHO_PREFIX}/unread-count`);
  },

  // CRM: lookup client by email (used in EmailViewer)
  async getClientByEmail(
    email: string,
  ): Promise<{ id: string; full_name: string; client_type: string } | null> {
    try {
      return await request<{
        id: string;
        full_name: string;
        client_type: string;
      }>(`/api/crm/clients/by-email/${encodeURIComponent(email)}`);
    } catch {
      return null;
    }
  },

  // CRM: create client
  async createClient(
    data: { full_name: string; email: string },
    source: string,
  ): Promise<{ id: string; full_name: string }> {
    return request<{ id: string; full_name: string }>(`/api/crm/clients`, {
      method: "POST",
      body: JSON.stringify({ ...data, source }),
    });
  },
};

export { logger };
