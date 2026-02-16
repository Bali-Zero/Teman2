/**
 * Twitter/X Types
 * Types for Twitter/X conversations and messages
 */

export interface TwitterConversation {
  id: number;
  twitter_user_id: string;
  username?: string;
  client_id?: number;
  client_name?: string;
  last_message?: string;
  last_message_date: string;
  unread_count?: number;
  interaction_count?: number;
}

export interface TwitterMessage {
  id: number;
  interaction_id: number;
  twitter_user_id: string;
  message_text: string;
  direction: "inbound" | "outbound";
  timestamp: string;
  message_id?: string; // Twitter/X message ID
  status?: "sent" | "delivered" | "read" | "failed";
  reply_to_message_id?: string;
  tweet_id?: string; // If this is a reply to a tweet
  media_url?: string; // For images/videos
  media_type?: "image" | "video" | "gif";
}

export interface TwitterInteraction extends TwitterMessage {
  client_id?: number;
  client_name?: string;
  team_member: string;
  sentiment?: "positive" | "neutral" | "negative" | "urgent";
  summary?: string;
  full_content?: string;
}
