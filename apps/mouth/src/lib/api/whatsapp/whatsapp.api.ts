/**
 * WhatsApp API Client
 * Optimized for Omnichannel Dashboard using the conversations table.
 */

import type { IApiClient } from "../types/api-client.types";
import type { WhatsAppConversation, WhatsAppMessage } from "./whatsapp.types";

export class WhatsAppApi {
  constructor(private client: IApiClient) {}

  /**
   * Get WhatsApp conversations (grouped by phone number)
   */
  async getConversations(
    params: {
      limit?: number;
      offset?: number;
    } = {},
  ): Promise<WhatsAppConversation[]> {
    return await this.client.request<WhatsAppConversation[]>(
      `/api/whatsapp/conversations?limit=${params.limit || 50}&offset=${params.offset || 0}`,
    );
  }

  /**
   * Get messages for a specific phone number
   */
  async getMessages(
    phone: string,
    limit: number = 100,
  ): Promise<WhatsAppMessage[]> {
    return await this.client.request<WhatsAppMessage[]>(
      `/api/whatsapp/messages/${phone}?limit=${limit}`,
    );
  }

  /**
   * Send a WhatsApp message
   */
  async sendMessage(
    phone: string,
    text: string,
    replyToMessageId?: string,
  ): Promise<{ success: boolean; message_id?: string }> {
    return await this.client.request<{ success: boolean; message_id?: string }>(
      "/api/whatsapp/send",
      {
        method: "POST",
        body: JSON.stringify({
          phone,
          text,
          reply_to: replyToMessageId,
        }),
      },
    );
  }
}
