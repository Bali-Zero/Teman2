/**
 * Email Types for Zoho Mail Integration
 * Copied from apps/mouth/src/lib/api/email/email.types.ts
 */

export interface ZohoConnectionStatus {
  connected: boolean;
  email: string | null;
  account_id: string | null;
  expires_at: string | null;
  api_domain?: string;
}

export interface ZohoAuthUrlResponse {
  auth_url: string;
  state: string;
}

export interface EmailFolder {
  folder_id: string;
  folder_name: string;
  folder_path: string;
  folder_type: "inbox" | "sent" | "drafts" | "trash" | "spam" | "custom";
  unread_count: number;
  total_count: number;
}

export interface FoldersResponse {
  folders: EmailFolder[];
}

export interface EmailAddress {
  address: string;
  name?: string;
}

export interface EmailAttachment {
  attachment_id: string;
  filename: string;
  size: number;
  mime_type: string;
}

export interface AttachmentObject {
  attachment_id: string;
  store_name: string;
  attachment_path: string;
  attachment_name: string;
}

export interface EmailSummary {
  message_id: string;
  subject: string;
  from: EmailAddress;
  to: EmailAddress[];
  date: string;
  snippet: string;
  is_read: boolean;
  is_flagged: boolean;
  has_attachments: boolean;
  folder_id: string;
  labels?: string[];
}

export interface EmailDetail extends EmailSummary {
  cc?: EmailAddress[];
  bcc?: EmailAddress[];
  html_content: string;
  text_content?: string;
  reply_to?: EmailAddress;
  in_reply_to?: string;
  thread_id?: string;
  attachments: EmailAttachment[];
}

export interface EmailListResponse {
  emails: EmailSummary[];
  total: number;
  has_more: boolean;
  next_offset?: number;
}

export interface SendEmailParams {
  to: string[];
  cc?: string[];
  bcc?: string[];
  subject: string;
  html_content?: string;
  text_content?: string;
  attachment_ids?: AttachmentObject[];
  reply_to?: string;
}

export interface ReplyEmailParams {
  content: string;
  reply_all?: boolean;
  attachment_ids?: string[];
  to: string;
  cc?: string;
}

export interface ForwardEmailParams {
  to: string[];
  cc?: string[];
  content?: string;
  attachment_ids?: string[];
}

export interface MarkReadParams {
  message_ids: string[];
  is_read: boolean;
}

export interface SendEmailResponse {
  success: boolean;
  message_id: string;
}

export interface OperationResponse {
  success: boolean;
  message?: string;
}

export interface SaveDraftParams {
  to?: string[];
  cc?: string[];
  bcc?: string[];
  subject?: string;
  html_content?: string;
  text_content?: string;
  attachment_ids?: AttachmentObject[];
}

export interface SaveDraftResponse {
  success: boolean;
  draft_id: string;
}

export interface UploadAttachmentResponse {
  attachment_id: string;
  store_name: string;
  attachment_path: string;
  attachment_name: string;
}

export interface EmailSearchParams {
  query?: string;
  folder_id?: string;
  is_read?: boolean;
  is_flagged?: boolean;
  from_date?: string;
  to_date?: string;
  limit?: number;
  offset?: number;
}

export interface UnreadCountResponse {
  total_unread: number;
  by_folder: Record<string, number>;
}
