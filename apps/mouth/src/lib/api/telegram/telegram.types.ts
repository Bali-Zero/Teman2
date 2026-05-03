/**
 * Telegram Types
 * Types for Telegram conversations and messages
 */

export interface TelegramConversation {
  id: number;
  chat_id: string | number;
  username?: string;
  client_id?: number;
  client_name?: string;
  last_message?: string;
  last_message_date: string;
  unread_count?: number;
  interaction_count?: number;
}

export interface TelegramMessage {
  id: number;
  interaction_id: number;
  chat_id: string | number;
  message_text: string;
  direction: "inbound" | "outbound";
  timestamp: string;
  message_id?: string; // Telegram message ID
  status?: "sent" | "delivered" | "read" | "failed";
  reply_to_message_id?: string;
}

export interface TelegramInteraction extends TelegramMessage {
  client_id?: number;
  client_name?: string;
  team_member: string;
  sentiment?: "positive" | "neutral" | "negative" | "urgent";
  summary?: string;
  full_content?: string;
}
