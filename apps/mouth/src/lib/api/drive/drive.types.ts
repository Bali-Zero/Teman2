/**
 * Google Drive API Types
 */

export interface ConnectionStatus {
  connected: boolean;
  configured: boolean;
  root_folder_id: string | null;
}

export interface FileItem {
  id: string;
  name: string;
  mime_type: string;
  size?: number;
  modified_time?: string;
  icon_link?: string;
  web_view_link?: string;
  thumbnail_link?: string;
  is_folder: boolean;
}

export interface BreadcrumbItem {
  id: string;
  name: string;
}

export interface FileListResponse {
  files: FileItem[];
  next_page_token: string | null;
  breadcrumb: BreadcrumbItem[];
}

export interface UserFolderResponse {
  found: boolean;
  folder_id?: string;
  folder_name?: string;
  message?: string;
}

export interface AuthUrlResponse {
  auth_url: string;
}

export interface DisconnectResponse {
  success: boolean;
}
