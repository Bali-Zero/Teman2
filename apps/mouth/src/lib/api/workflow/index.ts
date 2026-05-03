import type { IApiClient } from "../types/api-client.types";

export class WorkflowApi {
  constructor(private client: IApiClient) {}

  async getEnrichment(id: number) {
    return this.client.request<any>(
      `/api/workflow/conversations/${id}/enrichment`,
      {
        method: "GET",
      },
    );
  }

  async assign(id: number, userId: string) {
    return this.client.request<any>(
      `/api/workflow/conversations/${id}/assign`,
      {
        method: "PATCH",
        body: JSON.stringify({ assigned_to: userId }),
      },
    );
  }

  async updateStatus(id: number, status: string) {
    return this.client.request<any>(
      `/api/workflow/conversations/${id}/status`,
      {
        method: "PATCH",
        body: JSON.stringify({ status }),
      },
    );
  }

  async getNotes(id: number) {
    return this.client.request<any>(`/api/workflow/conversations/${id}/notes`, {
      method: "GET",
    });
  }

  async addNote(
    id: number,
    content: string,
    authorId: string,
    authorName: string,
  ) {
    return this.client.request<any>(`/api/workflow/conversations/${id}/notes`, {
      method: "POST",
      body: JSON.stringify({
        content,
        author_id: authorId,
        author_name: authorName,
      }),
    });
  }
}
