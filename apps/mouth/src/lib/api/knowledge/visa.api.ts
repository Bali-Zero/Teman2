/**
 * Visa Types API Client
 * Professional visa cards for Bali Zero Knowledge Base
 */

import { ApiClientBase } from '../client';
import type { VisaType, VisaTypeListResponse } from './visa.types';

// Use the base API URL from environment or default
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '/api';
const client = new ApiClientBase(API_BASE_URL);

export const visaApi = {
  /**
   * Get all visa types, optionally filtered by category
   */
  async getVisaTypes(category?: string): Promise<VisaTypeListResponse> {
    const params = category ? `?category=${encodeURIComponent(category)}` : '';
    const response = await client.request<VisaTypeListResponse>(`/knowledge/visa${params}`);
    return response;
  },

  /**
   * Get a specific visa type by ID
   */
  async getVisaById(id: number): Promise<VisaType> {
    const response = await client.request<VisaType>(`/knowledge/visa/${id}`);
    return response;
  },

  /**
   * Get a specific visa type by code (e.g., 'KITAS-312')
   */
  async getVisaByCode(code: string): Promise<VisaType> {
    const response = await client.request<VisaType>(`/knowledge/visa/code/${encodeURIComponent(code)}`);
    return response;
  },
};

export default visaApi;
