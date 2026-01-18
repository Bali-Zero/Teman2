/**
 * Instagram API Client
 * Handles Instagram conversations and messages via CRM Interactions API
 */

import { logger } from '@/lib/logger';
import type { IApiClient } from '../types/api-client.types';
import type { Interaction } from '../crm/crm.types';
import type {
  InstagramConversation,
  InstagramMessage,
  InstagramInteraction,
} from './instagram.types';

export class InstagramApi {
  constructor(private client: IApiClient) {}

  /**
   * Get Instagram conversations (grouped by instagram_user_id)
   */
  async getConversations(
    params: {
      limit?: number;
      offset?: number;
    } = {}
  ): Promise<InstagramConversation[]> {
    // Get all Instagram interactions
    const interactions = await this.client.request<Interaction[]>(
      `/api/crm/interactions?interaction_type=instagram&limit=${params.limit || 50}&offset=${params.offset || 0}`
    );

    // Group by instagram_user_id (extracted from full_content or extracted_entities)
    const conversationsMap = new Map<string, InstagramConversation>();

    // Load client data for interactions with client_id
    const clientIds = new Set(interactions.filter((i) => i.client_id).map((i) => i.client_id!));
    const clientsMap = new Map<number, { instagram_user_id?: string; full_name?: string }>();

    // Fetch client data to get Instagram user IDs
    for (const clientId of clientIds) {
      try {
        const client = await this.client.request<{
          instagram_user_id?: string;
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
      // Try to get instagram_user_id from client first, then extract from interaction
      let instagramUserId: string | null = null;

      if (interaction.client_id) {
        const client = clientsMap.get(interaction.client_id);
        if (client?.instagram_user_id) {
          instagramUserId = client.instagram_user_id;
        }
      }

      // Fallback: extract from interaction content or extracted_entities
      if (!instagramUserId) {
        instagramUserId = this.extractInstagramUserIdFromInteraction(interaction);
      }

      if (!instagramUserId) continue;

      const existing = conversationsMap.get(instagramUserId);
      const interactionDate = new Date(interaction.interaction_date);

      if (!existing || interactionDate > new Date(existing.last_message_date)) {
        conversationsMap.set(instagramUserId, {
          id: interaction.id,
          instagram_user_id: instagramUserId,
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
   * Get messages for a specific instagram_user_id
   */
  async getMessages(instagramUserId: string, limit: number = 50): Promise<InstagramMessage[]> {
    // Get all Instagram interactions
    const interactions = await this.client.request<Interaction[]>(
      `/api/crm/interactions?interaction_type=instagram&limit=${limit}`
    );

    // Filter by instagram_user_id and convert to InstagramMessage format
    const messages: InstagramMessage[] = [];

    for (const interaction of interactions) {
      const interactionUserId = this.extractInstagramUserIdFromInteraction(interaction);
      if (interactionUserId !== instagramUserId) continue;

      // Extract message text from full_content or summary
      const messageText =
        interaction.full_content || interaction.summary || interaction.subject || '';

      // Extract media info if available
      let mediaUrl: string | undefined;
      let mediaType: 'image' | 'video' | 'story' | undefined;
      if (interaction.extracted_entities && typeof interaction.extracted_entities === 'object') {
        const entities = interaction.extracted_entities as Record<string, unknown>;
        if (entities.media_url && typeof entities.media_url === 'string') {
          mediaUrl = entities.media_url;
        }
        if (entities.media_type && typeof entities.media_type === 'string') {
          mediaType = entities.media_type as 'image' | 'video' | 'story';
        }
      }

      messages.push({
        id: interaction.id,
        interaction_id: interaction.id,
        instagram_user_id: interactionUserId!,
        message_text: messageText,
        direction: interaction.direction as 'inbound' | 'outbound',
        timestamp: interaction.interaction_date,
        status: interaction.read_receipt ? 'read' : 'sent',
        media_url: mediaUrl,
        media_type: mediaType,
      });
    }

    // Sort by timestamp (oldest first)
    return messages.sort(
      (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );
  }

  /**
   * Send an Instagram message
   * Note: This requires a backend endpoint to be created
   */
  async sendMessage(
    instagramUserId: string,
    text: string,
    replyToMessageId?: string
  ): Promise<{ success: boolean; message_id?: string }> {
    // TODO: Create backend endpoint /api/instagram/send
    // For now, create an interaction record
    const user = await this.client.request<{ email: string }>('/api/auth/profile');

    const interaction = await this.client.request<Interaction>('/api/crm/interactions/', {
      method: 'POST',
      body: JSON.stringify({
        interaction_type: 'instagram',
        channel: 'instagram',
        summary: text.substring(0, 200),
        full_content: text,
        team_member: user.email,
        direction: 'outbound',
        extracted_entities: {
          instagram_user_id: instagramUserId,
        },
      }),
    });

    return {
      success: true,
      message_id: interaction.id.toString(),
    };
  }

  /**
   * Extract instagram_user_id from interaction
   */
  private extractInstagramUserIdFromInteraction(interaction: Interaction): string | null {
    // Try extracted_entities first (most reliable)
    if (interaction.extracted_entities && typeof interaction.extracted_entities === 'object') {
      const entities = interaction.extracted_entities as Record<string, unknown>;
      if (entities.instagram_user_id && typeof entities.instagram_user_id === 'string') {
        return entities.instagram_user_id;
      }
    }

    // Try to extract from full_content (might contain user_id in metadata)
    if (interaction.full_content) {
      // Look for Instagram user ID pattern
      const userIdMatch = interaction.full_content.match(
        /instagram[_\s]*user[_\s]*id[:\s]*([\w-]+)/i
      );
      if (userIdMatch) {
        return userIdMatch[1];
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
      if (entities.instagram_username && typeof entities.instagram_username === 'string') {
        return entities.instagram_username;
      }
    }

    // Try to extract from full_content
    if (interaction.full_content) {
      const usernameMatch = interaction.full_content.match(/@([a-zA-Z0-9._]+)/);
      if (usernameMatch) {
        return usernameMatch[1];
      }
    }

    return undefined;
  }
}
