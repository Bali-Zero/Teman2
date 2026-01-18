/**
 * Telegram API Client
 * Handles Telegram conversations and messages via CRM Interactions API
 */

import { logger } from '@/lib/logger';
import type { IApiClient } from '../types/api-client.types';
import type { Interaction } from '../crm/crm.types';
import type { TelegramConversation, TelegramMessage, TelegramInteraction } from './telegram.types';

export class TelegramApi {
  constructor(private client: IApiClient) {}

  /**
   * Get Telegram conversations (grouped by chat_id)
   */
  async getConversations(
    params: {
      limit?: number;
      offset?: number;
    } = {}
  ): Promise<TelegramConversation[]> {
    // Get all Telegram interactions
    const interactions = await this.client.request<Interaction[]>(
      `/api/crm/interactions?interaction_type=telegram&limit=${params.limit || 50}&offset=${params.offset || 0}`
    );

    // Group by chat_id (extracted from full_content or extracted_entities)
    const conversationsMap = new Map<string | number, TelegramConversation>();

    // Load client data for interactions with client_id
    const clientIds = new Set(interactions.filter((i) => i.client_id).map((i) => i.client_id!));
    const clientsMap = new Map<
      number,
      { telegram_chat_id?: string | number; full_name?: string }
    >();

    // Fetch client data to get Telegram chat IDs
    for (const clientId of clientIds) {
      try {
        const client = await this.client.request<{
          telegram_chat_id?: string | number;
          full_name?: string;
        }>(`/api/crm/clients/${clientId}`);
        if (client) {
          clientsMap.set(clientId, client);
        }
      } catch (error) {
        logger.warn(`Failed to fetch client ${clientId}:`, {}, error as Error);
      }
    }

    for (const interaction of interactions) {
      // Try to get chat_id from client first, then extract from interaction
      let chatId: string | number | null = null;

      if (interaction.client_id) {
        const client = clientsMap.get(interaction.client_id);
        if (client?.telegram_chat_id) {
          chatId = client.telegram_chat_id;
        }
      }

      // Fallback: extract from interaction content or extracted_entities
      if (!chatId) {
        chatId = this.extractChatIdFromInteraction(interaction);
      }

      if (!chatId) continue;

      const existing = conversationsMap.get(chatId);
      const interactionDate = new Date(interaction.interaction_date);

      if (!existing || interactionDate > new Date(existing.last_message_date)) {
        conversationsMap.set(chatId, {
          id: interaction.id,
          chat_id: chatId,
          username: this.extractUsernameFromInteraction(interaction),
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
   * Get messages for a specific chat_id
   */
  async getMessages(chatId: string | number, limit: number = 50): Promise<TelegramMessage[]> {
    // Get all Telegram interactions
    const interactions = await this.client.request<Interaction[]>(
      `/api/crm/interactions?interaction_type=telegram&limit=${limit}`
    );

    // Filter by chat_id and convert to TelegramMessage format
    const messages: TelegramMessage[] = [];

    for (const interaction of interactions) {
      const interactionChatId = this.extractChatIdFromInteraction(interaction);
      if (String(interactionChatId) !== String(chatId)) continue;

      // Extract message text from full_content or summary
      const messageText =
        interaction.full_content || interaction.summary || interaction.subject || '';

      messages.push({
        id: interaction.id,
        interaction_id: interaction.id,
        chat_id: interactionChatId!,
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
   * Send a Telegram message
   * Note: This requires a backend endpoint to be created
   */
  async sendMessage(
    chatId: string | number,
    text: string,
    replyToMessageId?: string
  ): Promise<{ success: boolean; message_id?: string }> {
    // TODO: Create backend endpoint /api/telegram/send
    // For now, create an interaction record
    const user = await this.client.request<{ email: string }>('/api/auth/profile');

    const interaction = await this.client.request<Interaction>('/api/crm/interactions/', {
      method: 'POST',
      body: JSON.stringify({
        interaction_type: 'telegram',
        channel: 'telegram',
        summary: text.substring(0, 200),
        full_content: text,
        team_member: user.email,
        direction: 'outbound',
        extracted_entities: {
          telegram_chat_id: chatId,
        },
      }),
    });

    return {
      success: true,
      message_id: interaction.id.toString(),
    };
  }

  /**
   * Extract chat_id from interaction
   */
  private extractChatIdFromInteraction(interaction: Interaction): string | number | null {
    // Try extracted_entities first (most reliable)
    if (interaction.extracted_entities && typeof interaction.extracted_entities === 'object') {
      const entities = interaction.extracted_entities as Record<string, unknown>;
      if (entities.telegram_chat_id) {
        return entities.telegram_chat_id as string | number;
      }
    }

    // Try to extract from full_content (might contain chat_id in metadata)
    if (interaction.full_content) {
      // Look for numeric chat_id pattern
      const chatIdMatch = interaction.full_content.match(/chat[_\s]*id[:\s]*(\d+)/i);
      if (chatIdMatch) {
        return parseInt(chatIdMatch[1], 10);
      }
    }

    return null;
  }

  /**
   * Extract username from interaction
   */
  private extractUsernameFromInteraction(interaction: Interaction): string | undefined {
    if (interaction.extracted_entities && typeof interaction.extracted_entities === 'object') {
      const entities = interaction.extracted_entities as Record<string, unknown>;
      if (entities.username && typeof entities.username === 'string') {
        return entities.username;
      }
    }

    // Try to extract from full_content
    if (interaction.full_content) {
      const usernameMatch = interaction.full_content.match(/@(\w+)/);
      if (usernameMatch) {
        return usernameMatch[1];
      }
    }

    return undefined;
  }
}
