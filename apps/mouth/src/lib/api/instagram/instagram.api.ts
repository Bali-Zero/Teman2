/**
 * Instagram API Client
 * Optimized for Omnichannel Dashboard using the conversations table.
 */

import type { IApiClient } from "../types/api-client.types";
import type {
  InstagramConversation,
  InstagramMessage,
} from "./instagram.types";

export class InstagramApi {
  constructor(private client: IApiClient) {}

  /**
   * Get Instagram conversations (grouped by instagram_user_id)
   */
  async getConversations(
    params: {
      limit?: number;
      offset?: number;
    } = {},
  ): Promise<InstagramConversation[]> {
    return await this.client.request<InstagramConversation[]>(
      `/api/instagram/conversations?limit=${params.limit || 50}&offset=${params.offset || 0}`,
    );
  }

  /**
   * Get messages for a specific instagram_user_id
   */
  async getMessages(
    instagramUserId: string,
    limit: number = 100,
  ): Promise<InstagramMessage[]> {
    return await this.client.request<InstagramMessage[]>(
      `/api/instagram/messages/${instagramUserId}?limit=${limit}`,
    );
  }

  /**
   * Send an Instagram message
   */
  async sendMessage(
    instagramUserId: string,
    text: string,
    replyToMessageId?: string,
  ): Promise<{ success: boolean; message_id?: string }> {
    return await this.client.request<{ success: boolean; message_id?: string }>(
      "/api/instagram/send",
      {
        method: "POST",
        body: JSON.stringify({
          instagram_user_id: instagramUserId,
          text,
          reply_to: replyToMessageId,
        }),
      },
    );
  }
}
