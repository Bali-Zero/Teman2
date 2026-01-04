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

// ============== CRUD Operation Types ==============

export interface UploadProgress {
  loaded: number;
  total: number;
  percentage: number;
}

export interface CreateFolderRequest {
  name: string;
  parent_id: string;
}

export interface CreateDocRequest {
  name: string;
  parent_id: string;
  doc_type: 'document' | 'spreadsheet' | 'presentation';
}

export interface RenameRequest {
  new_name: string;
}

export interface MoveRequest {
  new_parent_id: string;
  old_parent_id?: string;
}

export interface CopyRequest {
  new_name?: string;
  parent_folder_id?: string;
}

export interface OperationResponse {
  success: boolean;
  file?: FileItem;
  message?: string;
}

export interface BulkOperationResponse {
  success: boolean;
  results: Array<{
    file_id: string;
    success: boolean;
    message?: string;
  }>;
}

export type DocType = 'document' | 'spreadsheet' | 'presentation';

export interface UploadFile {
  file: File;
  parentId: string;
  onProgress?: (progress: UploadProgress) => void;
}

// ============== Permission Types (Board only) ==============

export type PermissionRole = 'owner' | 'writer' | 'commenter' | 'reader';

export interface PermissionItem {
  id: string;
  email: string;
  name: string;
  role: PermissionRole;
  type: 'user' | 'group' | 'domain' | 'anyone';
}

export interface AddPermissionRequest {
  email: string;
  role: PermissionRole;
  send_notification?: boolean;
}

export interface UpdatePermissionRequest {
  role: PermissionRole;
}
