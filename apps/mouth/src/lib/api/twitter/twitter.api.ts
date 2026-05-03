/**
 * Twitter/X API Client
 * Optimized for Omnichannel Dashboard using the conversations table.
 */

import type { IApiClient } from "../types/api-client.types";
import type { TwitterConversation, TwitterMessage } from "./twitter.types";

export class TwitterApi {
  constructor(private client: IApiClient) {}

  /**
   * Get Twitter/X conversations (grouped by twitter_user_id)
   */
  async getConversations(
    params: {
      limit?: number;
      offset?: number;
    } = {},
  ): Promise<TwitterConversation[]> {
    return await this.client.request<TwitterConversation[]>(
      `/api/twitter/conversations?limit=${params.limit || 50}&offset=${params.offset || 0}`,
    );
  }

  /**
   * Get messages for a specific twitter_user_id
   */
  async getMessages(
    twitterUserId: string,
    limit: number = 100,
  ): Promise<TwitterMessage[]> {
    return await this.client.request<TwitterMessage[]>(
      `/api/twitter/messages/${twitterUserId}?limit=${limit}`,
    );
  }

  /**
   * Send a Twitter/X message
   */
  async sendMessage(
    twitterUserId: string,
    text: string,
    replyToMessageId?: string,
  ): Promise<{ success: boolean; message_id?: string }> {
    return await this.client.request<{ success: boolean; message_id?: string }>(
      "/api/twitter/send",
      {
        method: "POST",
        body: JSON.stringify({
          twitter_user_id: twitterUserId,
          text,
          reply_to: replyToMessageId,
        }),
      },
    );
  }
}
