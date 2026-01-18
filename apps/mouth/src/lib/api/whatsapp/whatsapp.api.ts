/**
 * WhatsApp API Client
 * Handles WhatsApp conversations and messages via CRM Interactions API
 */

import { logger } from '@/lib/logger';
import type { IApiClient } from '../types/api-client.types';
import type { Interaction } from '../crm/crm.types';
import type { WhatsAppConversation, WhatsAppMessage, WhatsAppInteraction } from './whatsapp.types';

export class WhatsAppApi {
  constructor(private client: IApiClient) {}

  /**
   * Get WhatsApp conversations (grouped by phone number)
   */
  async getConversations(
    params: {
      limit?: number;
      offset?: number;
    } = {}
  ): Promise<WhatsAppConversation[]> {
    // Get all WhatsApp interactions
    const interactions = await this.client.request<Interaction[]>(
      `/api/crm/interactions?interaction_type=whatsapp&limit=${params.limit || 50}&offset=${params.offset || 0}`
    );

    // Group by phone number (extracted from full_content or subject)
    const conversationsMap = new Map<string, WhatsAppConversation>();

    // Load client data for interactions with client_id to get WhatsApp numbers
    const clientIds = new Set(interactions.filter((i) => i.client_id).map((i) => i.client_id!));
    const clientsMap = new Map<number, { whatsapp?: string; full_name?: string }>();

    // Fetch client data to get WhatsApp numbers
    for (const clientId of clientIds) {
      try {
        const client = await this.client.request<{ whatsapp?: string; full_name?: string }>(
          `/api/crm/clients/${clientId}`
        );
        if (client) {
          clientsMap.set(clientId, client);
        }
      } catch (error) {
        // Continue without client data - will extract from interaction content
        logger.warn(`Failed to fetch client ${clientId}:`, {}, error as Error);
      }
    }

    for (const interaction of interactions) {
      // Try to get phone from client first, then extract from interaction
      let phone: string | null = null;

      if (interaction.client_id) {
        const client = clientsMap.get(interaction.client_id);
        if (client?.whatsapp) {
          phone = client.whatsapp;
        }
      }

      // Fallback: extract from interaction content
      if (!phone) {
        phone = this.extractPhoneFromInteraction(interaction);
      }

      if (!phone) continue;

      const existing = conversationsMap.get(phone);
      const interactionDate = new Date(interaction.interaction_date);

      if (!existing || interactionDate > new Date(existing.last_message_date)) {
        conversationsMap.set(phone, {
          id: interaction.id,
          phone,
          client_id: interaction.client_id,
          client_name: interaction.client_name,
          last_message: interaction.summary || interaction.subject || '',
          last_message_date: interaction.interaction_date,
          unread_count: interaction.read_receipt === false ? 1 : 0,
          interaction_count: 1,
        });
      } else {
        // Update existing conversation
        existing.interaction_count = (existing.interaction_count || 0) + 1;
        if (interaction.read_receipt === false) {
          existing.unread_count = (existing.unread_count || 0) + 1;
        }
      }
    }

    return Array.from(conversationsMap.values()).sort(
      (a, b) => new Date(b.last_message_date).getTime() - new Date(a.last_message_date).getTime()
    );
  }

  /**
   * Get messages for a specific phone number
   */
  async getMessages(phone: string, limit: number = 50): Promise<WhatsAppMessage[]> {
    // Get all WhatsApp interactions for this phone
    const interactions = await this.client.request<Interaction[]>(
      `/api/crm/interactions?interaction_type=whatsapp&limit=${limit}`
    );

    // Filter by phone and convert to WhatsAppMessage format
    const messages: WhatsAppMessage[] = [];

    for (const interaction of interactions) {
      const interactionPhone = this.extractPhoneFromInteraction(interaction);
      if (interactionPhone !== phone) continue;

      // Extract message text from full_content or summary
      const messageText =
        interaction.full_content || interaction.summary || interaction.subject || '';

      messages.push({
        id: interaction.id,
        interaction_id: interaction.id,
        phone: interactionPhone,
        message_text: messageText,
        direction: interaction.direction as 'inbound' | 'outbound',
        timestamp: interaction.interaction_date,
        status: interaction.read_receipt ? 'read' : 'sent',
      });
    }

    // Sort by timestamp (oldest first)
    return messages.sort(
      (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );
  }

  /**
   * Send a WhatsApp message
   * Note: This requires a backend endpoint to be created
   */
  async sendMessage(
    phone: string,
    text: string,
    replyToMessageId?: string
  ): Promise<{ success: boolean; message_id?: string }> {
    // TODO: Create backend endpoint /api/whatsapp/send
    // For now, create an interaction record
    const user = await this.client.request<{ email: string }>('/api/auth/profile');

    const interaction = await this.client.request<Interaction>('/api/crm/interactions/', {
      method: 'POST',
      body: JSON.stringify({
        interaction_type: 'whatsapp',
        channel: 'whatsapp',
        summary: text.substring(0, 200),
        full_content: text,
        team_member: user.email,
        direction: 'outbound',
      }),
    });

    return {
      success: true,
      message_id: interaction.id.toString(),
    };
  }

  /**
   * Extract phone number from interaction
   * Uses client WhatsApp number if available, otherwise extracts from content
   */
  private extractPhoneFromInteraction(interaction: Interaction): string | null {
    // First, try to get phone from client if client_id is available
    // Note: We'll need to fetch client data separately if needed
    // For now, we extract from content

    // Try to extract from full_content (might contain phone in metadata)
    if (interaction.full_content) {
      // Look for phone pattern in content (Indonesian format)
      const phoneMatch = interaction.full_content.match(/(?:\+?62|0)[0-9]{9,12}/);
      if (phoneMatch) {
        let phone = phoneMatch[0];
        // Normalize to +62 format
        if (phone.startsWith('0')) {
          phone = '+62' + phone.substring(1);
        } else if (!phone.startsWith('+')) {
          phone = '+62' + phone;
        }
        return phone;
      }
    }

    // Try extracted_entities if available (check if it's a dict with phone field)
    // Note: extracted_entities structure depends on backend implementation
    // If interaction has extracted_entities with phone field, use that

    return null;
  }
}
