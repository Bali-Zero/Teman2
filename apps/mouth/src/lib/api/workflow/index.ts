/**
 * Workflow API for Omnichannel 2.0
 */
import { axiosInstance } from '../axios';

export const workflowApi = {
  getEnrichment: async (id: number) => {
    const response = await axiosInstance.get(`/api/workflow/conversations/${id}/enrichment`);
    return response.data;
  },
  
  assign: async (id: number, userId: string) => {
    const response = await axiosInstance.patch(`/api/workflow/conversations/${id}/assign`, {
      assigned_to: userId
    });
    return response.data;
  },
  
  updateStatus: async (id: number, status: string) => {
    const response = await axiosInstance.patch(`/api/workflow/conversations/${id}/status`, {
      status
    });
    return response.data;
  },
  
  getNotes: async (id: number) => {
    const response = await axiosInstance.get(`/api/workflow/conversations/${id}/notes`);
    return response.data;
  },
  
  addNote: async (id: number, content: string, authorId: string, authorName: string) => {
    const response = await axiosInstance.post(`/api/workflow/conversations/${id}/notes`, {
      content,
      author_id: authorId,
      author_name: authorName
    });
    return response.data;
  }
};
