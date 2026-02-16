/**
 * Omnichannel 2.0 Types
 * Extends the basic API types with UI-specific fields for the Command Center.
 */

import { WhatsAppConversation } from "@/lib/api/whatsapp/whatsapp.types";

export type ChannelType = "whatsapp" | "telegram" | "instagram" | "email";

export type ConversationStatus = "new" | "open" | "pending" | "closed";

export type LeadPriority = "low" | "medium" | "high" | "urgent";

export interface EnrichedConversation {
  id: number;
  phone: string;
  client_name: string;
  last_message: string;
  last_message_date: string;
  channel: ChannelType;
  status: ConversationStatus;
  priority: LeadPriority;
  assignedTo?: string;
  tags: string[];
  unreadCount: number;
  crmData?: {
    dealValue?: string;
    company?: string;
    lastInteraction?: string;
    sentiment?: "positive" | "neutral" | "negative";
  };
}

export interface Message {
  id: string;
  text: string;
  sender: "user" | "agent" | "system" | "ai";
  timestamp: string;
  isInternalNote?: boolean; // True if it's a team note
  attachments?: string[];
}
