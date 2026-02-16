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
