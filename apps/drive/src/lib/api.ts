import { logger } from "@/lib/logger";
import type {
  ConnectionStatus,
  FileItem,
  FileListResponse,
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
} from "./api/drive/drive.types";

export type { DocType };

const BACKEND_URL =
  process.env.NEXT_PUBLIC_API_URL || "https://nuzantara-rag.fly.dev";

interface ApiRequestOptions extends Omit<RequestInit, "headers"> {
  headers?: Record<string, string>;
}

class ApiClient {
  private token: string | null = null;
  private csrfToken: string | null = null;
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
    if (typeof document !== "undefined") {
      this.csrfToken =
        document.cookie
          .split("; ")
          .find((row) => row.startsWith("nz_csrf_token="))
          ?.split("=")[1] ?? null;
    }
  }

  getBaseUrl(): string {
    return this.baseUrl;
  }

  getToken(): string | null {
    if (typeof document !== "undefined" && !this.token) {
      const match = document.cookie
        .split("; ")
        .find((row) => row.startsWith("nz_auth_token="));
      if (match) this.token = match.split("=")[1];
    }
    return this.token;
  }

  setToken(token: string): void {
    this.token = token;
  }

  clearToken(): void {
    this.token = null;
  }

  async request<T>(
    endpoint: string,
    options: ApiRequestOptions = {},
    timeoutMs = 30000,
  ): Promise<T> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...options.headers,
    };

    const token = this.getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const csrfCookie =
      typeof document !== "undefined"
        ? document.cookie
            .split("; ")
            .find((row) => row.startsWith("nz_csrf_token="))
            ?.split("=")[1]
        : null;
    if (csrfCookie) headers["X-CSRF-Token"] = csrfCookie;

    const url = endpoint.startsWith("http")
      ? endpoint
      : `${this.baseUrl}${endpoint}`;

    try {
      const response = await fetch(url, {
        ...options,
        headers,
        credentials: "include",
        signal: controller.signal,
      });

      clearTimeout(timeout);

      if (!response.ok) {
        const errorText = await response.text().catch(() => "Unknown error");
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      return response.json() as Promise<T>;
    } catch (error) {
      clearTimeout(timeout);
      throw error;
    }
  }
}

const client = new ApiClient(BACKEND_URL);

/**
 * Google Drive API
 */
export const driveApi = {
  async getStatus(): Promise<ConnectionStatus> {
    const response = await client.request<{
      status: string;
      files_accessible: boolean;
    }>("/api/drive/status");

    return {
      connected: response.status === "connected",
      configured: true,
      root_folder_id: null,
    };
  },

  async getAuthUrl(): Promise<AuthUrlResponse> {
    return client.request<AuthUrlResponse>(
      "/integrations/google-drive/auth/url",
    );
  },

  async disconnect(): Promise<DisconnectResponse> {
    return { success: true };
  },

  async listFiles(
    params: {
      folder_id?: string;
      page_token?: string;
      page_size?: number;
    } = {},
  ): Promise<FileListResponse> {
    const queryParams = new URLSearchParams();
    if (params.folder_id) queryParams.append("folder_id", params.folder_id);
    if (params.page_token) queryParams.append("page_token", params.page_token);
    if (params.page_size)
      queryParams.append("page_size", params.page_size.toString());

    const queryString = queryParams.toString();
    const url = `/api/drive/files${queryString ? `?${queryString}` : ""}`;

    const response = await client.request<{
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

    const files: FileItem[] = response.files.map((f) => ({
      id: f.id,
      name: f.name,
      mime_type: f.mimeType,
      size: f.size,
      modified_time: f.modifiedTime,
      web_view_link: f.webViewLink,
      thumbnail_link: f.thumbnailLink,
      is_folder: f.type === "folder",
    }));

    let breadcrumb: { id: string; name: string }[] = [];
    if (params.folder_id) {
      try {
        breadcrumb = await client.request<{ id: string; name: string }[]>(
          `/api/drive/folders/${params.folder_id}/path`,
        );
      } catch {
        // ignore breadcrumb errors
      }
    }

    return { files, next_page_token: response.next_page_token, breadcrumb };
  },

  async searchFiles(query: string, pageSize = 20): Promise<FileItem[]> {
    const queryParams = new URLSearchParams();
    queryParams.append("q", query);
    queryParams.append("page_size", pageSize.toString());

    const response = await client.request<{
      results: Array<{
        id: string;
        name: string;
        type: string;
        mimeType: string;
        size: number;
        modifiedTime?: string;
        webViewLink?: string;
      }>;
    }>(`/api/drive/search?${queryParams.toString()}`);

    return response.results.map((f) => ({
      id: f.id,
      name: f.name,
      mime_type: f.mimeType,
      size: f.size,
      modified_time: f.modifiedTime,
      web_view_link: f.webViewLink,
      is_folder: f.type === "folder",
    }));
  },

  getDownloadUrl(fileId: string): string {
    return `${BACKEND_URL}/api/drive/files/${fileId}/download`;
  },

  async downloadFile(fileId: string, fileName?: string): Promise<void> {
    const token = client.getToken();
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const csrfCookie =
      typeof document !== "undefined"
        ? document.cookie
            .split("; ")
            .find((row) => row.startsWith("nz_csrf_token="))
            ?.split("=")[1]
        : null;
    if (csrfCookie) headers["X-CSRF-Token"] = csrfCookie;

    const response = await fetch(
      `${BACKEND_URL}/api/drive/files/${fileId}/download`,
      { method: "GET", credentials: "include", headers },
    );

    if (!response.ok) {
      throw new Error(`Download failed: ${response.status}`);
    }

    let downloadName = fileName || "download";
    const contentDisposition = response.headers.get("Content-Disposition");
    if (contentDisposition) {
      const match = contentDisposition.match(/filename="?([^";\n]+)"?/);
      if (match) downloadName = match[1];
    }

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = downloadName;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  },

  async uploadFile(
    file: File,
    parentId: string,
    onProgress?: (progress: UploadProgress) => void,
    signal?: AbortSignal,
  ): Promise<OperationResponse> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("parent_id", parentId);

    const fileSizeMB = file.size / (1024 * 1024);
    const timeoutMs = Math.min(
      5 * 60 * 1000 + Math.ceil(fileSizeMB / 100) * 60 * 1000,
      30 * 60 * 1000,
    );

    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.timeout = timeoutMs;

      if (signal) {
        const abortHandler = () => {
          xhr.abort();
          reject(new Error("Upload cancelled by user"));
        };
        if (signal.aborted) {
          abortHandler();
          return;
        }
        signal.addEventListener("abort", abortHandler);
        xhr.addEventListener("loadend", () =>
          signal.removeEventListener("abort", abortHandler),
        );
      }

      xhr.upload.addEventListener("progress", (event) => {
        if (event.lengthComputable && onProgress) {
          onProgress({
            loaded: event.loaded,
            total: event.total,
            percentage: Math.round((event.loaded / event.total) * 100),
          });
        }
      });

      xhr.addEventListener("load", () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const r = JSON.parse(xhr.responseText);
            resolve({ success: true, message: r.message });
          } catch {
            resolve({ success: true });
          }
        } else {
          try {
            const e = JSON.parse(xhr.responseText);
            reject(new Error(e.detail || "Upload failed"));
          } catch {
            reject(new Error(`Upload failed with status ${xhr.status}`));
          }
        }
      });

      xhr.addEventListener("error", () =>
        reject(new Error("Network error during upload")),
      );
      xhr.addEventListener("abort", () =>
        reject(new Error("Upload cancelled")),
      );
      xhr.addEventListener("timeout", () =>
        reject(
          new Error(
            `Upload timeout after ${Math.ceil(timeoutMs / 60000)} minutes`,
          ),
        ),
      );

      xhr.open("POST", `${BACKEND_URL}/api/drive/files/upload`);
      const token = client.getToken();
      if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);

      xhr.withCredentials = true;
      const csrfCookie =
        typeof document !== "undefined"
          ? document.cookie
              .split("; ")
              .find((row) => row.startsWith("nz_csrf_token="))
              ?.split("=")[1]
          : null;
      if (csrfCookie) xhr.setRequestHeader("X-CSRF-Token", csrfCookie);

      xhr.send(formData);
    });
  },

  async createFolder(request: CreateFolderRequest): Promise<OperationResponse> {
    return client.request<OperationResponse>("/api/drive/folders", {
      method: "POST",
      body: JSON.stringify(request),
    });
  },

  async createDoc(request: CreateDocRequest): Promise<OperationResponse> {
    return client.request<OperationResponse>("/api/drive/files/create", {
      method: "POST",
      body: JSON.stringify(request),
    });
  },

  async renameFile(
    fileId: string,
    newName: string,
  ): Promise<OperationResponse> {
    return client.request<OperationResponse>(
      `/api/drive/files/${fileId}/rename`,
      { method: "PATCH", body: JSON.stringify({ new_name: newName }) },
    );
  },

  async deleteFile(fileId: string): Promise<OperationResponse> {
    return client.request<OperationResponse>(`/api/drive/files/${fileId}`, {
      method: "DELETE",
    });
  },

  async moveFiles(
    fileIds: string[],
    newParentId: string,
  ): Promise<{ success: boolean; failed: string[] }> {
    const failed: string[] = [];
    await Promise.all(
      fileIds.map(async (id) => {
        try {
          await client.request(`/api/drive/files/${id}/move`, {
            method: "PATCH",
            body: JSON.stringify({ new_parent_id: newParentId }),
          });
        } catch {
          failed.push(id);
        }
      }),
    );
    return { success: failed.length === 0, failed };
  },

  async listPermissions(fileId: string): Promise<PermissionItem[]> {
    return client.request<PermissionItem[]>(
      `/api/drive/files/${fileId}/permissions`,
    );
  },

  async addPermission(
    fileId: string,
    request: AddPermissionRequest,
  ): Promise<PermissionItem> {
    return client.request<PermissionItem>(
      `/api/drive/files/${fileId}/permissions`,
      { method: "POST", body: JSON.stringify(request) },
    );
  },

  async updatePermission(
    fileId: string,
    permissionId: string,
    request: UpdatePermissionRequest,
  ): Promise<PermissionItem> {
    return client.request<PermissionItem>(
      `/api/drive/files/${fileId}/permissions/${permissionId}`,
      { method: "PATCH", body: JSON.stringify(request) },
    );
  },

  async removePermission(
    fileId: string,
    permissionId: string,
  ): Promise<{ success: boolean }> {
    return client.request<{ success: boolean }>(
      `/api/drive/files/${fileId}/permissions/${permissionId}`,
      { method: "DELETE" },
    );
  },
};

// Legacy named export for backward compat with documents page
export const api = { drive: driveApi };

export { logger };
