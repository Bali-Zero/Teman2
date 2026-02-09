/**
 * Omnichannel 2.0 Types
 * Extends the basic API types with UI-specific fields for the Command Center.
 */

import { WhatsAppConversation } from "@/lib/api/whatsapp/whatsapp.types";

export type ChannelType = 'whatsapp' | 'telegram' | 'instagram' | 'email';

export type ConversationStatus = 'new' | 'open' | 'pending' | 'closed';

export type LeadPriority = 'low' | 'medium' | 'high' | 'urgent';

export interface EnrichedConversation extends WhatsAppConversation {
  // Enhanced fields for UI (to be populated by backend in Phase 2)
  channel: ChannelType;
  status: ConversationStatus;
  priority: LeadPriority;
  assignedTo?: string; // User ID
  tags: string[];
  unreadCount: number;
  
  // CRM Data (Mocked for now)
  crmData?: {
    dealValue?: string;
    company?: string;
    lastInteraction?: string;
    sentiment?: 'positive' | 'neutral' | 'negative';
  };
}

export interface Message {
  id: string;
  text: string;
  sender: 'user' | 'agent' | 'system' | 'ai';
  timestamp: string;
  isInternalNote?: boolean; // True if it's a team note
  attachments?: string[];
}
