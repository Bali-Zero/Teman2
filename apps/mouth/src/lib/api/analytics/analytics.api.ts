/**
 * Analytics API Client
 * API calls for the Founder-only analytics dashboard
 */

import type {
  AllAnalytics,
  OverviewStats,
  RAGStats,
  CRMStats,
  TeamStats,
  SystemStats,
  QdrantStats,
  FeedbackStats,
  AlertStats,
} from './analytics.types';

export class AnalyticsApi {
  private baseUrl: string;
  private getToken: () => string | null;

  constructor(baseUrl: string, getToken: () => string | null) {
    this.baseUrl = baseUrl;
    this.getToken = getToken;
  }

  private async fetch<T>(endpoint: string): Promise<T> {
    const token = this.getToken();
    const response = await fetch(`${this.baseUrl}/api/analytics${endpoint}`, {
      headers: {
        'Content-Type': 'application/json',
        ...(token && { Authorization: `Bearer ${token}` }),
      },
      credentials: 'include',
    });

    if (!response.ok) {
      if (response.status === 403) {
        throw new Error('Access denied: Analytics is restricted to the Founder');
      }
      throw new Error(`Analytics API error: ${response.status}`);
    }

    return response.json();
  }

  async getAll(): Promise<AllAnalytics> {
    return this.fetch<AllAnalytics>('/all');
  }

  async getOverview(): Promise<OverviewStats> {
    return this.fetch<OverviewStats>('/overview');
  }

  async getRAG(): Promise<RAGStats> {
    return this.fetch<RAGStats>('/rag');
  }

  async getCRM(): Promise<CRMStats> {
    return this.fetch<CRMStats>('/crm');
  }

  async getTeam(): Promise<TeamStats> {
    return this.fetch<TeamStats>('/team');
  }

  async getSystem(): Promise<SystemStats> {
    return this.fetch<SystemStats>('/system');
  }

  async getQdrant(): Promise<QdrantStats> {
    return this.fetch<QdrantStats>('/qdrant');
  }

  async getFeedback(): Promise<FeedbackStats> {
    return this.fetch<FeedbackStats>('/feedback');
  }

  async getAlerts(): Promise<AlertStats> {
    return this.fetch<AlertStats>('/alerts');
  }
}
