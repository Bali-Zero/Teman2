/**
 * WhatsApp Types
 * Types for WhatsApp conversations and messages
 */

export interface WhatsAppConversation {
  id: number;
  phone: string;
  client_id?: number;
  client_name?: string;
  last_message?: string;
  last_message_date: string;
  unread_count?: number;
  interaction_count?: number;
}

export interface WhatsAppMessage {
  id: number;
  interaction_id: number;
  phone: string;
  message_text: string;
  direction: "inbound" | "outbound";
  timestamp: string;
  message_id?: string; // WhatsApp message ID from Meta API
  status?: "sent" | "delivered" | "read" | "failed";
  reply_to_message_id?: string;
}

export interface WhatsAppInteraction extends WhatsAppMessage {
  client_id?: number;
  client_name?: string;
  team_member: string;
  sentiment?: "positive" | "neutral" | "negative" | "urgent";
  summary?: string;
  full_content?: string;
}

/**
 * wa-mirror (Baileys) message — backend route /api/wa/messages.
 * Mirrors WaMirrorMessageResponse in apps/backend-rag/backend/app/routers/wa_mirror_messages.py.
 */
export interface WaMirrorMessage {
  id: number;
  client_id: number | null;
  practice_id: number | null;
  direction: "inbound" | "outbound";
  team_member_phone: string | null;
  counterpart_phone: string | null;
  body: string;
  body_truncated: boolean;
  message_date: string;
  media_type: string;
  media_mime: string | null;
  has_media: boolean;
  has_ocr: boolean;
  source: string;
  attention_priority: "HIGH" | "MEDIUM" | "LOW" | null;
  attention_reason: string[] | null;
  attention_resolved: boolean;
}

export interface WaMirrorMessagesResponse {
  items: WaMirrorMessage[];
  limit: number;
  offset: number;
}
