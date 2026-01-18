/**
 * Twitter/X API Client
 * Handles Twitter/X conversations and messages via CRM Interactions API
 */

import { logger } from '@/lib/logger';
import type { IApiClient } from '../types/api-client.types';
import type { Interaction } from '../crm/crm.types';
import type { TwitterConversation, TwitterMessage, TwitterInteraction } from './twitter.types';

export class TwitterApi {
  constructor(private client: IApiClient) {}

  /**
   * Get Twitter/X conversations (grouped by twitter_user_id)
   */
  async getConversations(
    params: {
      limit?: number;
      offset?: number;
    } = {}
  ): Promise<TwitterConversation[]> {
    // Get all Twitter/X interactions
    // Note: Backend might use 'twitter' or 'x' as interaction_type
    const interactions = await this.client.request<Interaction[]>(
      `/api/crm/interactions?interaction_type=twitter&limit=${params.limit || 50}&offset=${params.offset || 0}`
    );

    // Group by twitter_user_id (extracted from full_content or extracted_entities)
    const conversationsMap = new Map<string, TwitterConversation>();

    // Load client data for interactions with client_id
    const clientIds = new Set(interactions.filter((i) => i.client_id).map((i) => i.client_id!));
    const clientsMap = new Map<number, { twitter_user_id?: string; full_name?: string }>();

    // Fetch client data to get Twitter user IDs
    for (const clientId of clientIds) {
      try {
        const client = await this.client.request<{ twitter_user_id?: string; full_name?: string }>(
          `/api/crm/clients/${clientId}`
        );
        if (client) {
          clientsMap.set(clientId, client);
        }
      } catch (error) {
        logger.warn(`Failed to fetch client ${clientId}:`, {}, error as Error);
      }
    }

    for (const interaction of interactions) {
      // Try to get twitter_user_id from client first, then extract from interaction
      let twitterUserId: string | null = null;

      if (interaction.client_id) {
        const client = clientsMap.get(interaction.client_id);
        if (client?.twitter_user_id) {
          twitterUserId = client.twitter_user_id;
        }
      }

      // Fallback: extract from interaction content or extracted_entities
      if (!twitterUserId) {
        twitterUserId = this.extractTwitterUserIdFromInteraction(interaction);
      }

      if (!twitterUserId) continue;

      const existing = conversationsMap.get(twitterUserId);
      const interactionDate = new Date(interaction.interaction_date);

      if (!existing || interactionDate > new Date(existing.last_message_date)) {
        conversationsMap.set(twitterUserId, {
          id: interaction.id,
          twitter_user_id: twitterUserId,
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
   * Get messages for a specific twitter_user_id
   */
  async getMessages(twitterUserId: string, limit: number = 50): Promise<TwitterMessage[]> {
    // Get all Twitter/X interactions
    const interactions = await this.client.request<Interaction[]>(
      `/api/crm/interactions?interaction_type=twitter&limit=${limit}`
    );

    // Filter by twitter_user_id and convert to TwitterMessage format
    const messages: TwitterMessage[] = [];

    for (const interaction of interactions) {
      const interactionUserId = this.extractTwitterUserIdFromInteraction(interaction);
      if (interactionUserId !== twitterUserId) continue;

      // Extract message text from full_content or summary
      const messageText =
        interaction.full_content || interaction.summary || interaction.subject || '';

      // Extract media info if available
      let mediaUrl: string | undefined;
      let mediaType: 'image' | 'video' | 'gif' | undefined;
      let tweetId: string | undefined;
      if (interaction.extracted_entities && typeof interaction.extracted_entities === 'object') {
        const entities = interaction.extracted_entities as Record<string, unknown>;
        if (entities.media_url && typeof entities.media_url === 'string') {
          mediaUrl = entities.media_url;
        }
        if (entities.media_type && typeof entities.media_type === 'string') {
          mediaType = entities.media_type as 'image' | 'video' | 'gif';
        }
        if (entities.tweet_id && typeof entities.tweet_id === 'string') {
          tweetId = entities.tweet_id;
        }
      }

      messages.push({
        id: interaction.id,
        interaction_id: interaction.id,
        twitter_user_id: interactionUserId!,
        message_text: messageText,
        direction: interaction.direction as 'inbound' | 'outbound',
        timestamp: interaction.interaction_date,
        status: interaction.read_receipt ? 'read' : 'sent',
        media_url: mediaUrl,
        media_type: mediaType,
        tweet_id: tweetId,
      });
    }

    // Sort by timestamp (oldest first)
    return messages.sort(
      (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );
  }

  /**
   * Send a Twitter/X message
   * Note: This requires a backend endpoint to be created
   */
  async sendMessage(
    twitterUserId: string,
    text: string,
    replyToMessageId?: string
  ): Promise<{ success: boolean; message_id?: string }> {
    // TODO: Create backend endpoint /api/twitter/send
    // For now, create an interaction record
    const user = await this.client.request<{ email: string }>('/api/auth/profile');

    const interaction = await this.client.request<Interaction>('/api/crm/interactions/', {
      method: 'POST',
      body: JSON.stringify({
        interaction_type: 'twitter',
        channel: 'twitter',
        summary: text.substring(0, 200),
        full_content: text,
        team_member: user.email,
        direction: 'outbound',
        extracted_entities: {
          twitter_user_id: twitterUserId,
        },
      }),
    });

    return {
      success: true,
      message_id: interaction.id.toString(),
    };
  }

  /**
   * Extract twitter_user_id from interaction
   */
  private extractTwitterUserIdFromInteraction(interaction: Interaction): string | null {
    // Try extracted_entities first (most reliable)
    if (interaction.extracted_entities && typeof interaction.extracted_entities === 'object') {
      const entities = interaction.extracted_entities as Record<string, unknown>;
      if (entities.twitter_user_id && typeof entities.twitter_user_id === 'string') {
        return entities.twitter_user_id;
      }
      if (entities.x_user_id && typeof entities.x_user_id === 'string') {
        return entities.x_user_id;
      }
    }

    // Try to extract from full_content (might contain user_id in metadata)
    if (interaction.full_content) {
      // Look for Twitter user ID pattern
      const userIdMatch = interaction.full_content.match(
        /(?:twitter|x)[_\s]*user[_\s]*id[:\s]*([\w-]+)/i
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
      if (entities.twitter_username && typeof entities.twitter_username === 'string') {
        return entities.twitter_username;
      }
      if (entities.x_username && typeof entities.x_username === 'string') {
        return entities.x_username;
      }
    }

    // Try to extract from full_content
    if (interaction.full_content) {
      const usernameMatch = interaction.full_content.match(/@([a-zA-Z0-9_]+)/);
      if (usernameMatch) {
        return usernameMatch[1];
      }
    }

    return undefined;
  }
}
