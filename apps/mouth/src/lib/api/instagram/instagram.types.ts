/**
 * Instagram Types
 * Types for Instagram conversations and messages
 */

export interface InstagramConversation {
  id: number;
  instagram_user_id: string;
  username?: string;
  client_id?: number;
  client_name?: string;
  last_message?: string;
  last_message_date: string;
  unread_count?: number;
  interaction_count?: number;
}

export interface InstagramMessage {
  id: number;
  interaction_id: number;
  instagram_user_id: string;
  message_text: string;
  direction: "inbound" | "outbound";
  timestamp: string;
  message_id?: string; // Instagram message ID
  status?: "sent" | "delivered" | "read" | "failed";
  reply_to_message_id?: string;
  media_url?: string; // For images/videos
  media_type?: "image" | "video" | "story";
}

export interface InstagramInteraction extends InstagramMessage {
  client_id?: number;
  client_name?: string;
  team_member: string;
  sentiment?: "positive" | "neutral" | "negative" | "urgent";
  summary?: string;
  full_content?: string;
}
