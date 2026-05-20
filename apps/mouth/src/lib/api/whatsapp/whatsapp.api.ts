/**
 * WhatsApp API Client
 * Optimized for Omnichannel Dashboard using the conversations table.
 */

import type { IApiClient } from "../types/api-client.types";
import type {
  WhatsAppConversation,
  WhatsAppMessage,
  WaMirrorMessagesResponse,
} from "./whatsapp.types";

export class WhatsAppApi {
  constructor(private client: IApiClient) {}

  /**
   * Get wa-mirror (Baileys) messages tied to a CRM client or practice.
   * Backend route: /api/wa/messages (CRM-safe allowlist, RBAC enforced).
   */
  async getMirrorMessages(params: {
    clientId?: number;
    practiceId?: number;
    limit?: number;
    offset?: number;
  }): Promise<WaMirrorMessagesResponse> {
    const qs = new URLSearchParams();
    if (params.clientId != null) qs.set("client_id", String(params.clientId));
    if (params.practiceId != null)
      qs.set("practice_id", String(params.practiceId));
    qs.set("limit", String(params.limit ?? 50));
    qs.set("offset", String(params.offset ?? 0));
    return await this.client.request<WaMirrorMessagesResponse>(
      `/api/wa/messages?${qs.toString()}`,
    );
  }

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
