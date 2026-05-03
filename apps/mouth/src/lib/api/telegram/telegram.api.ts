/**
 * Telegram API Client
 * Optimized for Omnichannel Dashboard using the conversations table.
 */

import type { IApiClient } from "../types/api-client.types";
import type { TelegramConversation, TelegramMessage } from "./telegram.types";

export class TelegramApi {
  constructor(private client: IApiClient) {}

  /**
   * Get Telegram conversations (grouped by chat_id)
   */
  async getConversations(
    params: {
      limit?: number;
      offset?: number;
    } = {},
  ): Promise<TelegramConversation[]> {
    return await this.client.request<TelegramConversation[]>(
      `/api/telegram/conversations?limit=${params.limit || 50}&offset=${params.offset || 0}`,
    );
  }

  /**
   * Get messages for a specific chat_id
   */
  async getMessages(
    chatId: string | number,
    limit: number = 100,
  ): Promise<TelegramMessage[]> {
    return await this.client.request<TelegramMessage[]>(
      `/api/telegram/messages/${chatId}?limit=${limit}`,
    );
  }

  /**
   * Send a Telegram message
   */
  async sendMessage(
    chatId: string | number,
    text: string,
    replyToMessageId?: string,
  ): Promise<{ success: boolean; message_id?: string }> {
    return await this.client.request<{ success: boolean; message_id?: string }>(
      "/api/telegram/send",
      {
        method: "POST",
        body: JSON.stringify({
          chat_id: String(chatId),
          text,
          reply_to: replyToMessageId,
        }),
      },
    );
  }
}
